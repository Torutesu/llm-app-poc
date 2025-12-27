"""
Tenant-aware data filtering for Pathway pipelines.
"""
import logging
from typing import Any, Callable, List, Optional

import pathway as pw

from middleware.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class TenantDataFilter:
    """Filter data by tenant in Pathway pipelines."""

    @staticmethod
    def add_tenant_metadata(
        table: pw.Table,
        tenant_id: Optional[str] = None
    ) -> pw.Table:
        """
        Add tenant_id column to a Pathway table.

        Args:
            table: Input Pathway table
            tenant_id: Tenant ID to add (if None, uses current context)

        Returns:
            Table with tenant_id column added
        """
        effective_tenant_id = tenant_id or TenantContext.get_tenant()

        if not effective_tenant_id:
            logger.warning("No tenant context set, using 'default'")
            effective_tenant_id = "default"

        # Add tenant_id as a constant column
        table = table.with_columns(tenant_id=pw.this.tenant_id or effective_tenant_id)

        logger.debug(f"Added tenant_id={effective_tenant_id} to table")
        return table

    @staticmethod
    def filter_by_tenant(
        table: pw.Table,
        tenant_id: Optional[str] = None
    ) -> pw.Table:
        """
        Filter table to only include rows for a specific tenant.

        Args:
            table: Input Pathway table
            tenant_id: Tenant ID to filter by (if None, uses current context)

        Returns:
            Filtered table containing only rows for the specified tenant
        """
        effective_tenant_id = tenant_id or TenantContext.require_tenant()

        # Filter rows where tenant_id matches
        filtered = table.filter(pw.this.tenant_id == effective_tenant_id)

        logger.debug(f"Filtered table for tenant_id={effective_tenant_id}")
        return filtered

    @staticmethod
    def create_tenant_aware_source(
        source_connector: Callable,
        tenant_id: Optional[str] = None,
        **connector_kwargs
    ) -> pw.Table:
        """
        Create a tenant-aware data source.

        Args:
            source_connector: Pathway source connector (e.g., pw.io.fs.read)
            tenant_id: Tenant ID for this source
            **connector_kwargs: Arguments for the source connector

        Returns:
            Table with tenant_id metadata

        Example:
            >>> # Multi-tenant: Load data from tenant-specific folders
            >>> source = TenantDataFilter.create_tenant_aware_source(
            ...     pw.io.fs.read,
            ...     tenant_id="acme_corp",
            ...     path=f"data/tenants/{tenant_id}",
            ...     format="binary"
            ... )
        """
        effective_tenant_id = tenant_id or TenantContext.get_tenant() or "default"

        # Inject tenant_id into connector path if needed
        if "path" in connector_kwargs:
            original_path = connector_kwargs["path"]
            # Replace {tenant_id} placeholder
            connector_kwargs["path"] = original_path.format(tenant_id=effective_tenant_id)

        # Create source
        table = source_connector(**connector_kwargs)

        # Add tenant metadata
        table = TenantDataFilter.add_tenant_metadata(table, effective_tenant_id)

        logger.info(
            f"Created tenant-aware source for tenant_id={effective_tenant_id}, "
            f"path={connector_kwargs.get('path')}"
        )

        return table


class TenantAwareIndex:
    """Tenant-aware vector index wrapper."""

    def __init__(self, index: Any, enforce_isolation: bool = True):
        """
        Initialize tenant-aware index.

        Args:
            index: Underlying Pathway index (UsearchKNN, TantivyBM25, etc.)
            enforce_isolation: If True, strictly filter by tenant
        """
        self.index = index
        self.enforce_isolation = enforce_isolation

    def query(
        self,
        query: str,
        tenant_id: Optional[str] = None,
        k: int = 5,
        **query_kwargs
    ) -> List[Any]:
        """
        Query index with tenant filtering.

        Args:
            query: Search query
            tenant_id: Tenant ID to filter by (if None, uses current context)
            k: Number of results
            **query_kwargs: Additional query parameters

        Returns:
            Filtered search results for the tenant

        Raises:
            ValueError: If tenant context not set and enforce_isolation=True
        """
        effective_tenant_id = tenant_id or TenantContext.get_tenant()

        if self.enforce_isolation and not effective_tenant_id:
            raise ValueError("Tenant context required for isolated index queries")

        # Query underlying index
        results = self.index.query(query, k=k, **query_kwargs)

        # Filter results by tenant_id
        if self.enforce_isolation and effective_tenant_id:
            filtered_results = [
                result for result in results
                if self._get_tenant_from_result(result) == effective_tenant_id
            ]
            logger.debug(
                f"Filtered {len(results)} results to {len(filtered_results)} "
                f"for tenant_id={effective_tenant_id}"
            )
            return filtered_results

        return results

    @staticmethod
    def _get_tenant_from_result(result: Any) -> Optional[str]:
        """Extract tenant_id from search result metadata."""
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            return result.metadata.get("tenant_id")
        if hasattr(result, "tenant_id"):
            return result.tenant_id
        return None


# Pathway UDF decorators for tenant-aware processing
def tenant_aware_udf(func: Callable) -> Callable:
    """
    Decorator for Pathway UDFs that need tenant context.

    Automatically injects tenant_id as the first argument.

    Example:
        >>> @tenant_aware_udf
        ... @pw.udf
        ... def process_document(tenant_id: str, doc: str) -> str:
        ...     # Process document with tenant context
        ...     return f"[{tenant_id}] {doc}"
    """
    def wrapper(*args, **kwargs):
        tenant_id = TenantContext.get_tenant()
        if not tenant_id:
            logger.warning("No tenant context in UDF, using 'default'")
            tenant_id = "default"

        # Inject tenant_id as first argument
        return func(tenant_id, *args, **kwargs)

    return wrapper


# Example: Tenant-aware document processor
@pw.udf
def add_tenant_prefix(doc_path: str, tenant_id: str) -> str:
    """
    Add tenant prefix to document identifier.

    Args:
        doc_path: Original document path
        tenant_id: Tenant identifier

    Returns:
        Tenant-prefixed document identifier
    """
    return f"{tenant_id}:{doc_path}"


@pw.udf
def extract_tenant_from_path(doc_path: str) -> str:
    """
    Extract tenant_id from document path.

    Expected format: /data/tenants/{tenant_id}/...

    Args:
        doc_path: Document path

    Returns:
        Extracted tenant_id or 'default'
    """
    import os
    parts = doc_path.split(os.sep)

    # Look for 'tenants' folder
    try:
        tenant_idx = parts.index("tenants") + 1
        return parts[tenant_idx]
    except (ValueError, IndexError):
        return "default"
