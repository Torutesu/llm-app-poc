"""
Audit logging system for GDPR compliance and security monitoring.

Logs all user actions, API calls, and data access.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from middleware.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class AuditAction:
    """Standard audit action types."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    TOKEN_REFRESH = "token_refresh"

    # Documents
    DOCUMENT_READ = "document_read"
    DOCUMENT_WRITE = "document_write"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_DOWNLOAD = "document_download"

    # Search
    SEARCH = "search"
    SEARCH_ADVANCED = "search_advanced"

    # Users
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_DEACTIVATE = "user_deactivate"

    # Permissions
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ROLE_ASSIGN = "role_assign"
    ROLE_REVOKE = "role_revoke"

    # Settings
    SETTINGS_READ = "settings_read"
    SETTINGS_UPDATE = "settings_update"

    # Analytics
    ANALYTICS_VIEW = "analytics_view"
    REPORT_GENERATE = "report_generate"

    # Data export (GDPR)
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"


class AuditLogger:
    """
    Audit logging service.

    Records all significant actions for compliance and security.
    """

    def __init__(self, db_connection_string: str):
        """
        Initialize audit logger.

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

    def log(
        self,
        action: str,
        success: bool = True,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event.

        Args:
            action: Action name (use AuditAction constants)
            success: Whether action succeeded
            user_id: User who performed the action
            tenant_id: Tenant ID
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            ip_address: Client IP address
            user_agent: User agent string
            request_method: HTTP method (GET, POST, etc.)
            request_path: Request path
            status_code: HTTP status code
            error_message: Error message if action failed
            metadata: Additional metadata (stored as JSONB)
        """
        self.connect()

        # Get user context if not provided
        if not user_id:
            user_id = TenantContext.get_user()

        if not tenant_id:
            tenant_id = TenantContext.get_tenant()

        # Get user email
        user_email = None
        if user_id:
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "SELECT email FROM users WHERE user_id = %s",
                        (user_id,)
                    )
                    result = cur.fetchone()
                    if result:
                        user_email = result['email']
            except Exception as e:
                logger.warning(f"Could not fetch user email: {e}")

        # Insert audit log
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (
                        tenant_id, user_id, user_email,
                        action, resource_type, resource_id,
                        ip_address, user_agent,
                        request_method, request_path,
                        status_code, success, error_message,
                        metadata, timestamp
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        tenant_id, user_id, user_email,
                        action, resource_type, resource_id,
                        ip_address, user_agent,
                        request_method, request_path,
                        status_code, success, error_message,
                        Json(metadata) if metadata else None,
                        datetime.utcnow()
                    )
                )
                self.conn.commit()

            logger.debug(
                f"Audit log: action={action}, user={user_id}, "
                f"resource={resource_type}:{resource_id}, success={success}"
            )

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}", exc_info=True)
            # Don't raise - audit logging should not break application flow

    def log_login(
        self,
        user_id: str,
        tenant_id: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log login attempt.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            success: Whether login succeeded
            ip_address: Client IP
            user_agent: User agent
            error_message: Error message if failed
        """
        self.log(
            action=AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED,
            success=success,
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message,
            status_code=200 if success else 401
        )

    def log_document_access(
        self,
        document_id: str,
        action: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Log document access.

        Args:
            document_id: Document UUID
            action: Action (read, write, delete, download)
            user_id: User ID
            tenant_id: Tenant ID
            metadata: Additional metadata
        """
        self.log(
            action=action,
            success=True,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="document",
            resource_id=document_id,
            metadata=metadata
        )

    def log_search(
        self,
        query: str,
        results_count: int,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        response_time_ms: Optional[int] = None
    ) -> None:
        """
        Log search query.

        Args:
            query: Search query text
            results_count: Number of results returned
            user_id: User ID
            tenant_id: Tenant ID
            response_time_ms: Response time in milliseconds
        """
        self.log(
            action=AuditAction.SEARCH,
            success=True,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="search",
            metadata={
                "query": query,
                "results_count": results_count,
                "response_time_ms": response_time_ms
            }
        )

    def log_permission_change(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        target_user_id: Optional[str] = None,
        target_role_id: Optional[int] = None,
        access_level: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> None:
        """
        Log permission/role change.

        Args:
            action: grant or revoke
            resource_type: Type of resource
            resource_id: Resource ID
            target_user_id: User receiving permission
            target_role_id: Role receiving permission
            access_level: Access level granted
            user_id: User making the change
            tenant_id: Tenant ID
        """
        self.log(
            action=action,
            success=True,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "target_user_id": target_user_id,
                "target_role_id": target_role_id,
                "access_level": access_level
            }
        )

    def get_user_activity(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """
        Get audit logs for a specific user.

        Args:
            user_id: User ID
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records

        Returns:
            List of audit log records
        """
        self.connect()

        query = """
            SELECT
                log_id, timestamp, action, resource_type, resource_id,
                ip_address, success, error_message, metadata
            FROM audit_logs
            WHERE user_id = %s
        """
        params = [user_id]

        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)

        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def get_tenant_activity(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """
        Get audit logs for a tenant.

        Args:
            tenant_id: Tenant ID
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records

        Returns:
            List of audit log records
        """
        self.connect()

        query = """
            SELECT
                log_id, timestamp, user_id, user_email,
                action, resource_type, resource_id,
                ip_address, success, error_message
            FROM audit_logs
            WHERE tenant_id = %s
        """
        params = [tenant_id]

        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)

        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def get_document_access_history(
        self,
        document_id: str,
        limit: int = 50
    ) -> list:
        """
        Get access history for a document.

        Args:
            document_id: Document UUID
            limit: Maximum number of records

        Returns:
            List of audit log records
        """
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    log_id, timestamp, user_id, user_email,
                    action, ip_address, metadata
                FROM audit_logs
                WHERE resource_type = 'document'
                  AND resource_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (document_id, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    def generate_compliance_report(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate compliance report for a tenant.

        Useful for GDPR, SOC2, ISO27001 audits.

        Args:
            tenant_id: Tenant ID
            start_date: Report start date
            end_date: Report end date

        Returns:
            Compliance report dictionary
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Total actions
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM audit_logs
                WHERE tenant_id = %s
                  AND timestamp BETWEEN %s AND %s
                """,
                (tenant_id, start_date, end_date)
            )
            total_actions = cur.fetchone()['total']

            # Actions by type
            cur.execute(
                """
                SELECT action, COUNT(*) as count
                FROM audit_logs
                WHERE tenant_id = %s
                  AND timestamp BETWEEN %s AND %s
                GROUP BY action
                ORDER BY count DESC
                """,
                (tenant_id, start_date, end_date)
            )
            actions_by_type = {row['action']: row['count'] for row in cur.fetchall()}

            # Failed actions
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM audit_logs
                WHERE tenant_id = %s
                  AND timestamp BETWEEN %s AND %s
                  AND success = FALSE
                """,
                (tenant_id, start_date, end_date)
            )
            failed_actions = cur.fetchone()['total']

            # Unique users
            cur.execute(
                """
                SELECT COUNT(DISTINCT user_id) as total
                FROM audit_logs
                WHERE tenant_id = %s
                  AND timestamp BETWEEN %s AND %s
                """,
                (tenant_id, start_date, end_date)
            )
            unique_users = cur.fetchone()['total']

            # Document accesses
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM audit_logs
                WHERE tenant_id = %s
                  AND timestamp BETWEEN %s AND %s
                  AND resource_type = 'document'
                """,
                (tenant_id, start_date, end_date)
            )
            document_accesses = cur.fetchone()['total']

        return {
            "tenant_id": tenant_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_actions": total_actions,
                "failed_actions": failed_actions,
                "unique_users": unique_users,
                "document_accesses": document_accesses
            },
            "actions_by_type": actions_by_type
        }


# Decorator for automatic audit logging
def audit_log(action: str, resource_type: Optional[str] = None):
    """
    Decorator to automatically log function calls.

    Args:
        action: Audit action name
        resource_type: Resource type

    Example:
        >>> @audit_log(AuditAction.DOCUMENT_READ, resource_type="document")
        ... def read_document(document_id: str):
        ...     # Function implementation
        ...     pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            audit_logger = kwargs.get('audit_logger')
            if not audit_logger:
                # No audit logger provided, skip logging
                return func(*args, **kwargs)

            # Extract resource_id if present
            resource_id = kwargs.get('document_id') or kwargs.get('resource_id')

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Log success
                audit_logger.log(
                    action=action,
                    success=True,
                    resource_type=resource_type,
                    resource_id=resource_id
                )

                return result

            except Exception as e:
                # Log failure
                audit_logger.log(
                    action=action,
                    success=False,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    error_message=str(e)
                )

                raise

        return wrapper

    return decorator
