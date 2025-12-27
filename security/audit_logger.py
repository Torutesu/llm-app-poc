"""
Security audit logging system.

Logs all authentication and security-related events for compliance and monitoring.
"""
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Audit event types."""

    # Authentication events
    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all_devices"

    # 2FA events
    TFA_SETUP = "2fa_setup"
    TFA_ENABLED = "2fa_enabled"
    TFA_DISABLED = "2fa_disabled"
    TFA_VERIFY_SUCCESS = "2fa_verify_success"
    TFA_VERIFY_FAILURE = "2fa_verify_failure"

    # Password events
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_FAILED = "password_reset_failed"

    # Session events
    SESSION_CREATED = "session_created"
    SESSION_INVALIDATED = "session_invalidated"

    # User management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    USER_DELETED = "user_deleted"

    # Authorization events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_CHANGED = "role_changed"

    # Security events
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    ACCOUNT_LOCKED = "account_locked"


class EventCategory(str, Enum):
    """Event categories for filtering."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    USER_MANAGEMENT = "user_management"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class AuditEvent(BaseModel):
    """Audit event model."""

    # Event information
    event_type: EventType
    category: EventCategory
    action: str
    resource: Optional[str] = None

    # User information
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    user_email: Optional[str] = None

    # Result
    success: bool
    failure_reason: Optional[str] = None

    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None

    # Additional data
    metadata: Optional[Dict[str, Any]] = None

    # Timestamp
    timestamp: datetime = None

    def __init__(self, **data):
        """Initialize with timestamp."""
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


class AuditLogger:
    """Audit logger for security events."""

    def __init__(self):
        """Initialize audit logger."""
        # In-memory storage (in production: write to database or log aggregation service)
        self._events: list[AuditEvent] = []

        # Event category mapping
        self._category_map = {
            EventType.LOGIN_ATTEMPT: EventCategory.AUTHENTICATION,
            EventType.LOGIN_SUCCESS: EventCategory.AUTHENTICATION,
            EventType.LOGIN_FAILURE: EventCategory.AUTHENTICATION,
            EventType.LOGOUT: EventCategory.AUTHENTICATION,
            EventType.TFA_SETUP: EventCategory.SECURITY,
            EventType.TFA_ENABLED: EventCategory.SECURITY,
            EventType.TFA_DISABLED: EventCategory.SECURITY,
            EventType.PASSWORD_CHANGED: EventCategory.SECURITY,
            EventType.PASSWORD_RESET_REQUESTED: EventCategory.SECURITY,
            EventType.USER_CREATED: EventCategory.USER_MANAGEMENT,
            EventType.USER_UPDATED: EventCategory.USER_MANAGEMENT,
            EventType.USER_DEACTIVATED: EventCategory.USER_MANAGEMENT,
            EventType.PERMISSION_GRANTED: EventCategory.AUTHORIZATION,
            EventType.PERMISSION_DENIED: EventCategory.AUTHORIZATION,
            EventType.SUSPICIOUS_ACTIVITY: EventCategory.SECURITY,
            EventType.RATE_LIMIT_EXCEEDED: EventCategory.SECURITY,
        }

    def log_event(
        self,
        event_type: EventType,
        action: str,
        success: bool,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_email: Optional[str] = None,
        resource: Optional[str] = None,
        failure_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            action: Description of action taken
            success: Whether action succeeded
            user_id: User identifier
            tenant_id: Tenant identifier
            user_email: User email
            resource: Resource affected
            failure_reason: Reason for failure
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session identifier
            metadata: Additional event data

        Returns:
            Created audit event
        """
        category = self._category_map.get(event_type, EventCategory.SECURITY)

        event = AuditEvent(
            event_type=event_type,
            category=category,
            action=action,
            resource=resource,
            user_id=user_id,
            tenant_id=tenant_id,
            user_email=user_email,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            metadata=metadata or {}
        )

        self._events.append(event)

        # Log to standard logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"[AUDIT] {event_type.value}: {action} - "
            f"user={user_id or 'N/A'}, success={success}, ip={ip_address or 'N/A'}"
        )

        return event

    # Convenience methods for common events

    def log_login_attempt(
        self,
        email: str,
        success: bool,
        user_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log login attempt."""
        event_type = EventType.LOGIN_SUCCESS if success else EventType.LOGIN_FAILURE

        return self.log_event(
            event_type=event_type,
            action=f"User login {'successful' if success else 'failed'}",
            success=success,
            user_id=user_id,
            user_email=email,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def log_2fa_verification(
        self,
        user_id: str,
        method: str,
        success: bool,
        ip_address: Optional[str] = None
    ):
        """Log 2FA verification."""
        event_type = EventType.TFA_VERIFY_SUCCESS if success else EventType.TFA_VERIFY_FAILURE

        return self.log_event(
            event_type=event_type,
            action=f"2FA verification ({method}) {'successful' if success else 'failed'}",
            success=success,
            user_id=user_id,
            ip_address=ip_address,
            metadata={"method": method}
        )

    def log_password_reset(
        self,
        email: str,
        success: bool,
        user_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log password reset."""
        return self.log_event(
            event_type=EventType.PASSWORD_RESET_REQUESTED,
            action="Password reset requested",
            success=success,
            user_id=user_id,
            user_email=email,
            failure_reason=failure_reason,
            ip_address=ip_address
        )

    def log_suspicious_activity(
        self,
        user_id: Optional[str],
        reason: str,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log suspicious activity."""
        return self.log_event(
            event_type=EventType.SUSPICIOUS_ACTIVITY,
            action=f"Suspicious activity detected: {reason}",
            success=False,
            user_id=user_id,
            failure_reason=reason,
            ip_address=ip_address,
            metadata=metadata
        )

    def log_rate_limit_exceeded(
        self,
        identifier: str,
        limit_type: str,
        ip_address: Optional[str] = None
    ):
        """Log rate limit exceeded."""
        return self.log_event(
            event_type=EventType.RATE_LIMIT_EXCEEDED,
            action=f"Rate limit exceeded for {limit_type}",
            success=False,
            failure_reason="Too many attempts",
            ip_address=ip_address,
            metadata={"identifier": identifier, "limit_type": limit_type}
        )

    # Query methods

    def get_user_events(
        self,
        user_id: str,
        limit: int = 100
    ) -> list[AuditEvent]:
        """Get events for specific user."""
        events = [e for e in self._events if e.user_id == user_id]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_events_by_type(
        self,
        event_type: EventType,
        limit: int = 100
    ) -> list[AuditEvent]:
        """Get events by type."""
        events = [e for e in self._events if e.event_type == event_type]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_failed_events(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> list[AuditEvent]:
        """Get failed events in last N hours."""
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(hours=hours)
        events = [
            e for e in self._events
            if not e.success and e.timestamp > threshold
        ]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_security_events(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> list[AuditEvent]:
        """Get security events in last N hours."""
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(hours=hours)
        events = [
            e for e in self._events
            if e.category == EventCategory.SECURITY and e.timestamp > threshold
        ]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_statistics(self, hours: int = 24) -> Dict:
        """
        Get audit statistics for last N hours.

        Returns:
            Dictionary with event statistics
        """
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [e for e in self._events if e.timestamp > threshold]

        total = len(recent_events)
        success = sum(1 for e in recent_events if e.success)
        failed = total - success

        by_type = {}
        for event in recent_events:
            event_type = event.event_type.value
            by_type[event_type] = by_type.get(event_type, 0) + 1

        by_category = {}
        for event in recent_events:
            category = event.category.value
            by_category[category] = by_category.get(category, 0) + 1

        return {
            "total_events": total,
            "successful_events": success,
            "failed_events": failed,
            "events_by_type": by_type,
            "events_by_category": by_category,
            "time_window_hours": hours
        }


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """
    Get global audit logger instance.

    Returns:
        Audit logger instance
    """
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger()

    return _audit_logger
