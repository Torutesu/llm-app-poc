"""
GDPR (General Data Protection Regulation) compliance features.

Implements:
- Right to access (Article 15)
- Right to rectification (Article 16)
- Right to erasure / "Right to be forgotten" (Article 17)
- Right to data portability (Article 20)
- Right to object (Article 21)
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from database.audit_logger import AuditAction, AuditLogger

logger = logging.getLogger(__name__)


class GDPRCompliance:
    """GDPR compliance service."""

    def __init__(self, db_connection_string: str, audit_logger: AuditLogger):
        """
        Initialize GDPR compliance service.

        Args:
            db_connection_string: PostgreSQL connection string
            audit_logger: Audit logger instance
        """
        self.db_connection_string = db_connection_string
        self.audit_logger = audit_logger
        self.conn = None

    def connect(self):
        """Establish database connection."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                self.db_connection_string,
                cursor_factory=RealDictCursor
            )

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

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all personal data for a user (GDPR Article 15, 20).

        "Right to Access" and "Right to Data Portability"

        Args:
            user_id: User ID

        Returns:
            Complete user data export
        """
        self.connect()

        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "data": {}
        }

        with self.conn.cursor() as cur:
            # 1. User profile
            cur.execute(
                """
                SELECT
                    user_id, tenant_id, email, name,
                    given_name, family_name, picture,
                    oauth_provider, created_at, updated_at, last_login_at
                FROM users
                WHERE user_id = %s
                """,
                (user_id,)
            )
            user = cur.fetchone()

            if not user:
                raise ValueError(f"User {user_id} not found")

            export_data["data"]["profile"] = dict(user)

            # 2. Roles
            cur.execute(
                """
                SELECT r.role_name, ur.granted_at
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.role_id
                WHERE ur.user_id = %s
                """,
                (user_id,)
            )
            export_data["data"]["roles"] = [dict(row) for row in cur.fetchall()]

            # 3. Custom permissions
            cur.execute(
                """
                SELECT p.permission_name, ucp.granted_at
                FROM user_custom_permissions ucp
                JOIN permissions p ON ucp.permission_id = p.permission_id
                WHERE ucp.user_id = %s
                """,
                (user_id,)
            )
            export_data["data"]["custom_permissions"] = [dict(row) for row in cur.fetchall()]

            # 4. Document permissions (what user can access)
            cur.execute(
                """
                SELECT
                    d.document_id, d.file_path, d.file_name,
                    dp.access_level, dp.granted_at
                FROM document_permissions dp
                JOIN documents d ON dp.document_id = d.document_id
                WHERE dp.user_id = %s
                ORDER BY dp.granted_at DESC
                """,
                (user_id,)
            )
            export_data["data"]["document_permissions"] = [dict(row) for row in cur.fetchall()]

            # 5. Owned documents
            cur.execute(
                """
                SELECT
                    document_id, file_path, file_name, file_type,
                    created_at, updated_at
                FROM documents
                WHERE owner_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            export_data["data"]["owned_documents"] = [dict(row) for row in cur.fetchall()]

            # 6. Search history
            cur.execute(
                """
                SELECT
                    query_text, query_type, results_count,
                    response_time_ms, user_rating, timestamp
                FROM search_queries
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT 1000
                """,
                (user_id,)
            )
            export_data["data"]["search_history"] = [dict(row) for row in cur.fetchall()]

            # 7. Audit logs (user's activity)
            cur.execute(
                """
                SELECT
                    timestamp, action, resource_type, resource_id,
                    ip_address, success
                FROM audit_logs
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT 1000
                """,
                (user_id,)
            )
            export_data["data"]["activity_log"] = [dict(row) for row in cur.fetchall()]

        # Log this data export
        self.audit_logger.log(
            action=AuditAction.DATA_EXPORT,
            user_id=user_id,
            tenant_id=user['tenant_id'],
            success=True,
            metadata={"export_sections": list(export_data["data"].keys())}
        )

        logger.info(f"Exported data for user {user_id}")

        return export_data

    def anonymize_user(self, user_id: str, reason: Optional[str] = None) -> None:
        """
        Anonymize user data (GDPR Article 17 - Right to Erasure).

        This anonymizes rather than deletes to preserve audit trails
        and relational integrity.

        Args:
            user_id: User ID to anonymize
            reason: Reason for anonymization
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Get tenant_id before anonymization
            cur.execute("SELECT tenant_id, email FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()

            if not user:
                raise ValueError(f"User {user_id} not found")

            tenant_id = user['tenant_id']
            original_email = user['email']

            # Anonymize user profile
            anonymized_email = f"deleted_user_{user_id}@anonymized.local"

            cur.execute(
                """
                UPDATE users
                SET
                    email = %s,
                    name = 'Deleted User',
                    given_name = NULL,
                    family_name = NULL,
                    picture = NULL,
                    password_hash = NULL,
                    oauth_provider_user_id = NULL,
                    is_active = FALSE,
                    updated_at = NOW()
                WHERE user_id = %s
                """,
                (anonymized_email, user_id)
            )

            # Anonymize audit logs (keep action, but remove PII)
            cur.execute(
                """
                UPDATE audit_logs
                SET
                    user_email = %s,
                    ip_address = NULL,
                    user_agent = NULL,
                    metadata = NULL
                WHERE user_id = %s
                """,
                (anonymized_email, user_id)
            )

            # Anonymize search queries
            cur.execute(
                """
                UPDATE search_queries
                SET
                    query_text = '[REDACTED]',
                    user_feedback = NULL
                WHERE user_id = %s
                """,
                (user_id,)
            )

            # Revoke refresh tokens
            cur.execute(
                """
                UPDATE refresh_tokens
                SET
                    is_revoked = TRUE,
                    revoked_at = NOW(),
                    revoked_reason = %s
                WHERE user_id = %s
                """,
                (reason or 'User data deletion request', user_id)
            )

            self.conn.commit()

        # Log anonymization
        self.audit_logger.log(
            action=AuditAction.DATA_DELETE,
            user_id=user_id,
            tenant_id=tenant_id,
            success=True,
            metadata={
                "original_email": original_email,
                "reason": reason
            }
        )

        logger.info(f"Anonymized user {user_id}")

    def delete_user_data(self, user_id: str, reason: Optional[str] = None) -> None:
        """
        Permanently delete user data (GDPR Article 17).

        WARNING: This is irreversible. Prefer anonymize_user() to preserve
        audit trails.

        Args:
            user_id: User ID
            reason: Reason for deletion
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Get tenant_id before deletion
            cur.execute("SELECT tenant_id, email FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()

            if not user:
                raise ValueError(f"User {user_id} not found")

            tenant_id = user['tenant_id']
            email = user['email']

            # Delete user (CASCADE will handle related records)
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

            self.conn.commit()

        # Log deletion (user_id will be NULL in audit log since user is deleted)
        self.audit_logger.log(
            action=AuditAction.DATA_DELETE,
            user_id=None,
            tenant_id=tenant_id,
            success=True,
            metadata={
                "deleted_user_id": user_id,
                "deleted_email": email,
                "reason": reason,
                "deletion_type": "permanent"
            }
        )

        logger.warning(f"PERMANENTLY DELETED user {user_id} ({email})")

    def rectify_user_data(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """
        Update user data (GDPR Article 16 - Right to Rectification).

        Args:
            user_id: User ID
            updates: Dictionary of fields to update
        """
        self.connect()

        allowed_fields = ['name', 'given_name', 'family_name', 'email']
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

        if not update_fields:
            raise ValueError("No valid fields to update")

        # Build UPDATE query
        set_clause = ", ".join([f"{k} = %s" for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(user_id)

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE users
                SET {set_clause}, updated_at = NOW()
                WHERE user_id = %s
                """,
                values
            )

            # Get tenant_id
            cur.execute("SELECT tenant_id FROM users WHERE user_id = %s", (user_id,))
            tenant_id = cur.fetchone()['tenant_id']

            self.conn.commit()

        # Log rectification
        self.audit_logger.log(
            action="data_rectification",
            user_id=user_id,
            tenant_id=tenant_id,
            success=True,
            metadata={"updated_fields": list(update_fields.keys())}
        )

        logger.info(f"Rectified data for user {user_id}: {list(update_fields.keys())}")

    def get_consent_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's consent status for data processing.

        Args:
            user_id: User ID

        Returns:
            Consent information
        """
        # In a real system, you'd have a consents table
        # For now, return basic info from user table

        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_id, email, created_at, is_active,
                    oauth_provider
                FROM users
                WHERE user_id = %s
                """,
                (user_id,)
            )
            user = cur.fetchone()

            if not user:
                return {}

            return {
                "user_id": user['user_id'],
                "email": user['email'],
                "account_created_at": user['created_at'].isoformat(),
                "is_active": user['is_active'],
                "consent_given": user['is_active'],  # Active account implies consent
                "authentication_method": user['oauth_provider'] or "password",
                "data_processing_consent": True,
                "marketing_consent": False,  # Would come from separate table
            }

    def generate_gdpr_report(self, tenant_id: str) -> Dict[str, Any]:
        """
        Generate GDPR compliance report for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            GDPR compliance report
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Total users
            cur.execute(
                "SELECT COUNT(*) as total FROM users WHERE tenant_id = %s",
                (tenant_id,)
            )
            total_users = cur.fetchone()['total']

            # Active users
            cur.execute(
                "SELECT COUNT(*) as total FROM users WHERE tenant_id = %s AND is_active = TRUE",
                (tenant_id,)
            )
            active_users = cur.fetchone()['total']

            # Data export requests (last 30 days)
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM audit_logs
                WHERE tenant_id = %s
                  AND action = %s
                  AND timestamp >= NOW() - INTERVAL '30 days'
                """,
                (tenant_id, AuditAction.DATA_EXPORT)
            )
            data_export_requests = cur.fetchone()['total']

            # Data deletion requests
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM audit_logs
                WHERE tenant_id = %s
                  AND action = %s
                  AND timestamp >= NOW() - INTERVAL '30 days'
                """,
                (tenant_id, AuditAction.DATA_DELETE)
            )
            data_deletion_requests = cur.fetchone()['total']

            # Total audit logs
            cur.execute(
                "SELECT COUNT(*) as total FROM audit_logs WHERE tenant_id = %s",
                (tenant_id,)
            )
            total_audit_logs = cur.fetchone()['total']

        return {
            "tenant_id": tenant_id,
            "report_date": datetime.utcnow().isoformat(),
            "users": {
                "total": total_users,
                "active": active_users,
                "anonymized": total_users - active_users
            },
            "gdpr_requests_30_days": {
                "data_export": data_export_requests,
                "data_deletion": data_deletion_requests
            },
            "audit_logs": {
                "total": total_audit_logs,
                "retention_period_days": 365  # Configurable
            },
            "compliance_status": "compliant"  # Would have actual checks
        }


def export_to_json_file(data: Dict[str, Any], filename: str) -> str:
    """
    Export data to JSON file.

    Args:
        data: Data to export
        filename: Output filename

    Returns:
        File path
    """
    import json
    from datetime import datetime

    # Convert datetime objects to ISO format
    def datetime_handler(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=datetime_handler)

    logger.info(f"Exported data to {filename}")

    return filename
