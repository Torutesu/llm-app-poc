"""
Document filtering by ACL permissions in Pathway pipelines.

Integrates ACL checks into document retrieval and search.
"""
import logging
from typing import List
from uuid import UUID

import pathway as pw

from database.document_acl import AccessLevel, DocumentACL
from middleware.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class ACLDocumentFilter:
    """
    Filter documents based on user permissions.

    Integrates with Pathway to ensure users only access documents
    they have permission to view.
    """

    def __init__(self, document_acl: DocumentACL):
        """
        Initialize ACL document filter.

        Args:
            document_acl: DocumentACL instance
        """
        self.document_acl = document_acl

    @pw.udf
    def filter_documents_by_user_permission(
        self,
        document_ids: List[str],
        user_id: str,
        required_access: str = "read"
    ) -> List[str]:
        """
        Pathway UDF to filter documents by user permissions.

        Args:
            document_ids: List of document ID strings
            user_id: User ID
            required_access: Required access level (read, write, admin)

        Returns:
            Filtered list of document IDs
        """
        if not document_ids or not user_id:
            return []

        # Convert to UUIDs
        try:
            uuid_list = [UUID(doc_id) for doc_id in document_ids]
        except ValueError as e:
            logger.error(f"Invalid document UUID: {e}")
            return []

        # Get access level enum
        access_level = AccessLevel(required_access)

        # Filter by ACL
        accessible_uuids = self.document_acl.bulk_filter_documents_by_access(
            uuid_list,
            user_id,
            access_level
        )

        # Convert back to strings
        return [str(uuid) for uuid in accessible_uuids]

    def apply_acl_filter_to_table(
        self,
        table: pw.Table,
        document_id_column: str = "document_id"
    ) -> pw.Table:
        """
        Apply ACL filtering to a Pathway table.

        Args:
            table: Input Pathway table with document_id column
            document_id_column: Name of document ID column

        Returns:
            Filtered table with only accessible documents
        """
        # Get current user context
        user_id = TenantContext.get_user()

        if not user_id:
            logger.warning("No user context set, skipping ACL filter")
            return table

        # Filter table using UDF
        @pw.udf
        def check_document_access(doc_id: str) -> bool:
            """Check if current user can access document."""
            try:
                doc_uuid = UUID(doc_id)
                return self.document_acl.check_user_access(
                    doc_uuid,
                    user_id,
                    AccessLevel.READ
                )
            except ValueError:
                logger.error(f"Invalid document UUID: {doc_id}")
                return False

        # Apply filter
        filtered_table = table.filter(
            check_document_access(pw.this[document_id_column])
        )

        logger.debug(f"Applied ACL filter for user {user_id}")

        return filtered_table

    def get_user_accessible_documents(
        self,
        tenant_id: str,
        user_id: str,
        access_level: AccessLevel = AccessLevel.READ
    ) -> List[UUID]:
        """
        Get list of documents accessible by user.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            access_level: Minimum access level

        Returns:
            List of accessible document UUIDs
        """
        return self.document_acl.get_user_accessible_documents(
            user_id,
            tenant_id,
            access_level
        )


# Pre-retrieval filter
def create_acl_pre_filter(document_acl: DocumentACL):
    """
    Create a pre-retrieval ACL filter for search queries.

    This filters documents BEFORE sending to the vector index,
    reducing computation and ensuring security.

    Args:
        document_acl: DocumentACL instance

    Returns:
        Filter function
    """
    def pre_filter(query: str, k: int = 10, **kwargs) -> dict:
        """
        Pre-filter documents before retrieval.

        Args:
            query: Search query
            k: Number of results
            **kwargs: Additional parameters

        Returns:
            Filter metadata for retrieval
        """
        user_id = TenantContext.get_user()
        tenant_id = TenantContext.get_tenant()

        if not user_id or not tenant_id:
            logger.warning("No user/tenant context, returning empty filter")
            return {"allowed_document_ids": []}

        # Get accessible documents
        accessible_docs = document_acl.get_user_accessible_documents(
            user_id,
            tenant_id,
            AccessLevel.READ
        )

        logger.debug(
            f"Pre-filter: user {user_id} can access {len(accessible_docs)} documents"
        )

        return {
            "allowed_document_ids": [str(doc_id) for doc_id in accessible_docs],
            "user_id": user_id,
            "tenant_id": tenant_id
        }

    return pre_filter


# Post-retrieval filter
def create_acl_post_filter(document_acl: DocumentACL):
    """
    Create a post-retrieval ACL filter.

    This filters results AFTER retrieval from vector index,
    as a safety net.

    Args:
        document_acl: DocumentACL instance

    Returns:
        Filter function
    """
    def post_filter(results: List[dict]) -> List[dict]:
        """
        Post-filter search results.

        Args:
            results: List of search result dictionaries with 'document_id' key

        Returns:
            Filtered results
        """
        user_id = TenantContext.get_user()

        if not user_id:
            logger.warning("No user context, returning empty results")
            return []

        if not results:
            return []

        # Extract document IDs
        doc_ids = []
        for result in results:
            try:
                doc_id = UUID(result.get('document_id'))
                doc_ids.append(doc_id)
            except (ValueError, TypeError):
                continue

        # Filter by ACL
        accessible_ids = document_acl.bulk_filter_documents_by_access(
            doc_ids,
            user_id,
            AccessLevel.READ
        )

        accessible_ids_set = set(str(uid) for uid in accessible_ids)

        # Filter results
        filtered_results = [
            result for result in results
            if result.get('document_id') in accessible_ids_set
        ]

        logger.debug(
            f"Post-filter: {len(results)} results → {len(filtered_results)} "
            f"after ACL check"
        )

        return filtered_results

    return post_filter


# Example integration with Pathway
class ACLAwareRetriever:
    """
    Retriever that enforces ACL permissions.

    Wraps a standard retriever with ACL filtering.
    """

    def __init__(self, base_retriever, document_acl: DocumentACL):
        """
        Initialize ACL-aware retriever.

        Args:
            base_retriever: Base retriever (e.g., UsearchKNN, TantivyBM25)
            document_acl: DocumentACL instance
        """
        self.base_retriever = base_retriever
        self.document_acl = document_acl
        self.pre_filter = create_acl_pre_filter(document_acl)
        self.post_filter = create_acl_post_filter(document_acl)

    def retrieve(self, query: str, k: int = 10, **kwargs):
        """
        Retrieve documents with ACL filtering.

        Args:
            query: Search query
            k: Number of results to return
            **kwargs: Additional retrieval parameters

        Returns:
            Filtered search results
        """
        # Pre-filter: get allowed document IDs
        filter_metadata = self.pre_filter(query, k, **kwargs)
        allowed_doc_ids = filter_metadata.get("allowed_document_ids", [])

        if not allowed_doc_ids:
            logger.info("User has no accessible documents")
            return []

        # Add to retrieval kwargs
        kwargs["filter_document_ids"] = allowed_doc_ids

        # Retrieve from base retriever
        results = self.base_retriever.retrieve(query, k=k, **kwargs)

        # Post-filter: safety check
        filtered_results = self.post_filter(results)

        return filtered_results
