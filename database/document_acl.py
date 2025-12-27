"""
Document-level Access Control List (ACL) management.

Implements fine-grained permissions for documents and folders.
"""
import logging
from enum import Enum
from typing import List, Optional, Set
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AccessLevel(str, Enum):
    """Document access levels."""
    NONE = "none"  # No access
    READ = "read"  # View document
    WRITE = "write"  # Edit document
    ADMIN = "admin"  # Manage permissions


class DocumentACL:
    """Document Access Control List manager."""

    def __init__(self, db_connection_string: str):
        """
        Initialize Document ACL manager.

        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db_connection_string = db_connection_string
        self.conn = None

    def connect(self):
        """Establish database connection."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                self.db_connection_string,
                cursor_factory=RealDictCursor
            )
            logger.debug("Connected to PostgreSQL for ACL operations")

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def grant_user_access(
        self,
        document_id: UUID,
        tenant_id: str,
        user_id: str,
        access_level: AccessLevel,
        granted_by: Optional[str] = None
    ) -> None:
        """
        Grant access to a user for a document.

        Args:
            document_id: Document UUID
            tenant_id: Tenant ID
            user_id: User ID to grant access to
            access_level: Level of access (read, write, admin)
            granted_by: User ID who granted the permission
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Check if permission already exists
            cur.execute(
                """
                SELECT permission_id, access_level
                FROM document_permissions
                WHERE document_id = %s AND user_id = %s
                """,
                (str(document_id), user_id)
            )
            existing = cur.fetchone()

            if existing:
                # Update existing permission
                cur.execute(
                    """
                    UPDATE document_permissions
                    SET access_level = %s, granted_at = NOW(), granted_by = %s
                    WHERE permission_id = %s
                    """,
                    (access_level.value, granted_by, existing['permission_id'])
                )
                logger.info(
                    f"Updated user access: doc={document_id}, user={user_id}, "
                    f"level={access_level.value}"
                )
            else:
                # Insert new permission
                cur.execute(
                    """
                    INSERT INTO document_permissions (
                        document_id, tenant_id, user_id, access_level, granted_by
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(document_id), tenant_id, user_id, access_level.value, granted_by)
                )
                logger.info(
                    f"Granted user access: doc={document_id}, user={user_id}, "
                    f"level={access_level.value}"
                )

            self.conn.commit()

    def grant_role_access(
        self,
        document_id: UUID,
        tenant_id: str,
        role_id: int,
        access_level: AccessLevel,
        granted_by: Optional[str] = None
    ) -> None:
        """
        Grant access to a role for a document.

        Args:
            document_id: Document UUID
            tenant_id: Tenant ID
            role_id: Role ID to grant access to
            access_level: Level of access
            granted_by: User ID who granted the permission
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Check if permission already exists
            cur.execute(
                """
                SELECT permission_id, access_level
                FROM document_permissions
                WHERE document_id = %s AND role_id = %s
                """,
                (str(document_id), role_id)
            )
            existing = cur.fetchone()

            if existing:
                # Update existing permission
                cur.execute(
                    """
                    UPDATE document_permissions
                    SET access_level = %s, granted_at = NOW(), granted_by = %s
                    WHERE permission_id = %s
                    """,
                    (access_level.value, granted_by, existing['permission_id'])
                )
                logger.info(
                    f"Updated role access: doc={document_id}, role={role_id}, "
                    f"level={access_level.value}"
                )
            else:
                # Insert new permission
                cur.execute(
                    """
                    INSERT INTO document_permissions (
                        document_id, tenant_id, role_id, access_level, granted_by
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(document_id), tenant_id, role_id, access_level.value, granted_by)
                )
                logger.info(
                    f"Granted role access: doc={document_id}, role={role_id}, "
                    f"level={access_level.value}"
                )

            self.conn.commit()

    def revoke_user_access(self, document_id: UUID, user_id: str) -> None:
        """
        Revoke user access to a document.

        Args:
            document_id: Document UUID
            user_id: User ID to revoke access from
        """
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM document_permissions
                WHERE document_id = %s AND user_id = %s
                """,
                (str(document_id), user_id)
            )
            self.conn.commit()

        logger.info(f"Revoked user access: doc={document_id}, user={user_id}")

    def revoke_role_access(self, document_id: UUID, role_id: int) -> None:
        """
        Revoke role access to a document.

        Args:
            document_id: Document UUID
            role_id: Role ID to revoke access from
        """
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM document_permissions
                WHERE document_id = %s AND role_id = %s
                """,
                (str(document_id), role_id)
            )
            self.conn.commit()

        logger.info(f"Revoked role access: doc={document_id}, role={role_id}")

    def check_user_access(
        self,
        document_id: UUID,
        user_id: str,
        required_access: AccessLevel = AccessLevel.READ
    ) -> bool:
        """
        Check if user has required access level to a document.

        Args:
            document_id: Document UUID
            user_id: User ID
            required_access: Required access level

        Returns:
            True if user has access, False otherwise
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Use the pre-defined PostgreSQL function
            cur.execute(
                "SELECT user_can_access_document(%s, %s, %s) as has_access",
                (user_id, str(document_id), required_access.value)
            )
            result = cur.fetchone()

            has_access = result['has_access'] if result else False

            logger.debug(
                f"Access check: doc={document_id}, user={user_id}, "
                f"required={required_access.value}, result={has_access}"
            )

            return has_access

    def get_user_accessible_documents(
        self,
        user_id: str,
        tenant_id: str,
        access_level: AccessLevel = AccessLevel.READ
    ) -> List[UUID]:
        """
        Get list of document IDs accessible by user.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            access_level: Minimum access level

        Returns:
            List of document UUIDs
        """
        self.connect()

        access_levels = {
            AccessLevel.READ: ['read', 'write', 'admin'],
            AccessLevel.WRITE: ['write', 'admin'],
            AccessLevel.ADMIN: ['admin']
        }

        allowed_levels = access_levels[access_level]

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT document_id
                FROM document_access
                WHERE user_id = %s
                  AND tenant_id = %s
                  AND access_level = ANY(%s)
                """,
                (user_id, tenant_id, allowed_levels)
            )

            document_ids = [UUID(row['document_id']) for row in cur.fetchall()]

            logger.debug(
                f"User {user_id} has {access_level.value} access to "
                f"{len(document_ids)} documents in tenant {tenant_id}"
            )

            return document_ids

    def get_document_permissions(self, document_id: UUID) -> dict:
        """
        Get all permissions for a document.

        Args:
            document_id: Document UUID

        Returns:
            Dictionary with 'users' and 'roles' permissions
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Get user permissions
            cur.execute(
                """
                SELECT
                    dp.user_id,
                    u.email,
                    u.name,
                    dp.access_level,
                    dp.granted_at,
                    dp.granted_by
                FROM document_permissions dp
                JOIN users u ON dp.user_id = u.user_id
                WHERE dp.document_id = %s AND dp.user_id IS NOT NULL
                ORDER BY u.email
                """,
                (str(document_id),)
            )
            user_perms = cur.fetchall()

            # Get role permissions
            cur.execute(
                """
                SELECT
                    dp.role_id,
                    r.role_name,
                    dp.access_level,
                    dp.granted_at,
                    dp.granted_by
                FROM document_permissions dp
                JOIN roles r ON dp.role_id = r.role_id
                WHERE dp.document_id = %s AND dp.role_id IS NOT NULL
                ORDER BY r.role_name
                """,
                (str(document_id),)
            )
            role_perms = cur.fetchall()

        return {
            "users": [dict(p) for p in user_perms],
            "roles": [dict(p) for p in role_perms]
        }

    def inherit_folder_permissions(
        self,
        folder_id: UUID,
        document_id: UUID,
        tenant_id: str
    ) -> None:
        """
        Inherit permissions from parent folder to document.

        Args:
            folder_id: Parent folder UUID
            document_id: Document UUID
            tenant_id: Tenant ID
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Copy user permissions
            cur.execute(
                """
                INSERT INTO document_permissions (
                    document_id, tenant_id, user_id, access_level,
                    inherited_from, is_inherited, granted_by
                )
                SELECT
                    %s, tenant_id, user_id, access_level,
                    %s, TRUE, granted_by
                FROM document_permissions
                WHERE document_id = %s AND user_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """,
                (str(document_id), str(folder_id), str(folder_id))
            )

            # Copy role permissions
            cur.execute(
                """
                INSERT INTO document_permissions (
                    document_id, tenant_id, role_id, access_level,
                    inherited_from, is_inherited, granted_by
                )
                SELECT
                    %s, tenant_id, role_id, access_level,
                    %s, TRUE, granted_by
                FROM document_permissions
                WHERE document_id = %s AND role_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """,
                (str(document_id), str(folder_id), str(folder_id))
            )

            self.conn.commit()

        logger.info(
            f"Inherited permissions from folder {folder_id} to document {document_id}"
        )

    def set_default_permissions(
        self,
        document_id: UUID,
        tenant_id: str,
        owner_id: str
    ) -> None:
        """
        Set default permissions for a new document.

        - Owner gets admin access
        - Admin role gets admin access
        - Editor role gets write access
        - Viewer role gets read access

        Args:
            document_id: Document UUID
            tenant_id: Tenant ID
            owner_id: Document owner user ID
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Grant owner admin access
            cur.execute(
                """
                INSERT INTO document_permissions (
                    document_id, tenant_id, user_id, access_level, granted_by
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(document_id), tenant_id, owner_id, AccessLevel.ADMIN.value, owner_id)
            )

            # Grant role-based access
            role_access = [
                ('admin', AccessLevel.ADMIN.value),
                ('editor', AccessLevel.WRITE.value),
                ('viewer', AccessLevel.READ.value)
            ]

            for role_name, access_level in role_access:
                cur.execute(
                    """
                    INSERT INTO document_permissions (
                        document_id, tenant_id, role_id, access_level, granted_by
                    )
                    SELECT %s, %s, role_id, %s, %s
                    FROM roles
                    WHERE role_name = %s
                    """,
                    (str(document_id), tenant_id, access_level, owner_id, role_name)
                )

            self.conn.commit()

        logger.info(f"Set default permissions for document {document_id}")

    def bulk_filter_documents_by_access(
        self,
        document_ids: List[UUID],
        user_id: str,
        required_access: AccessLevel = AccessLevel.READ
    ) -> List[UUID]:
        """
        Filter a list of documents by user access.

        Args:
            document_ids: List of document UUIDs
            user_id: User ID
            required_access: Required access level

        Returns:
            Filtered list of document UUIDs that user can access
        """
        if not document_ids:
            return []

        self.connect()

        access_levels = {
            AccessLevel.READ: ['read', 'write', 'admin'],
            AccessLevel.WRITE: ['write', 'admin'],
            AccessLevel.ADMIN: ['admin']
        }

        allowed_levels = access_levels[required_access]

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT document_id
                FROM document_access
                WHERE user_id = %s
                  AND document_id = ANY(%s)
                  AND access_level = ANY(%s)
                """,
                (user_id, [str(doc_id) for doc_id in document_ids], allowed_levels)
            )

            accessible_ids = [UUID(row['document_id']) for row in cur.fetchall()]

            logger.debug(
                f"Filtered {len(document_ids)} documents to {len(accessible_ids)} "
                f"accessible by user {user_id}"
            )

            return accessible_ids
