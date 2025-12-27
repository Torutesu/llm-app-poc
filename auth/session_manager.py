"""
Session management system.

Features:
- Track active user sessions
- Store session metadata (device, IP, location)
- Session invalidation (logout)
- Logout from all devices
- Session expiration and cleanup
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionInfo(BaseModel):
    """User session information."""

    session_id: str = Field(description="Unique session identifier")
    user_id: str = Field(description="User identifier")
    tenant_id: str = Field(description="Tenant identifier")

    # Session metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(description="Session expiration time")

    # Device/client information
    device_type: Optional[str] = Field(
        default=None,
        description="Device type (mobile, desktop, tablet)"
    )
    device_name: Optional[str] = Field(
        default=None,
        description="Device name or model"
    )
    os: Optional[str] = Field(default=None, description="Operating system")
    browser: Optional[str] = Field(default=None, description="Browser name")
    user_agent: Optional[str] = Field(default=None, description="Full user agent string")

    # Network information
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    location: Optional[str] = Field(
        default=None,
        description="Geographic location (city, country)"
    )

    # Status
    is_active: bool = Field(default=True, description="Session is active")
    is_current: bool = Field(
        default=False,
        description="Whether this is the current session"
    )
    invalidated_at: Optional[datetime] = Field(
        default=None,
        description="When session was invalidated"
    )
    invalidation_reason: Optional[str] = Field(
        default=None,
        description="Reason for invalidation (logout, timeout, security)"
    )

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()

    def get_duration(self) -> timedelta:
        """Get session duration."""
        return self.last_activity_at - self.created_at


class DeviceInfo(BaseModel):
    """Device/client information for session creation."""

    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    device_type: Optional[str] = None  # mobile, desktop, tablet
    device_name: Optional[str] = None
    os: Optional[str] = None
    browser: Optional[str] = None
    location: Optional[str] = None


class SessionManager:
    """Manage user sessions."""

    def __init__(self, session_expire_hours: int = 168):  # 7 days default
        """
        Initialize session manager.

        Args:
            session_expire_hours: Hours until session expires (default: 168 = 7 days)
        """
        self.session_expire_hours = session_expire_hours

        # In-memory session storage (in production: use Redis or database)
        # session_id -> SessionInfo
        self._sessions: Dict[str, SessionInfo] = {}

        # user_id -> list of session_ids
        self._user_sessions: Dict[str, List[str]] = {}

        # Settings
        self.max_sessions_per_user = 10  # Limit concurrent sessions
        self.activity_timeout_minutes = 30  # Mark as inactive after 30 min

    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        device_info: Optional[DeviceInfo] = None,
        is_current: bool = True
    ) -> SessionInfo:
        """
        Create a new session for user.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            device_info: Device/client information
            is_current: Whether this is the current active session

        Returns:
            Created session information
        """
        # Generate unique session ID
        session_id = self._generate_session_id(user_id)

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(hours=self.session_expire_hours)

        # Create session
        session = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=expires_at,
            is_current=is_current
        )

        # Add device info if provided
        if device_info:
            session.device_type = device_info.device_type
            session.device_name = device_info.device_name
            session.os = device_info.os
            session.browser = device_info.browser
            session.user_agent = device_info.user_agent
            session.ip_address = device_info.ip_address
            session.location = device_info.location

        # Store session
        self._sessions[session_id] = session

        # Track user sessions
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []

        self._user_sessions[user_id].append(session_id)

        # Enforce max sessions limit
        self._enforce_session_limit(user_id)

        logger.info(
            f"Session created for user {user_id}: {session_id}, "
            f"expires at {expires_at.isoformat()}"
        )

        return session

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session info or None if not found
        """
        return self._sessions.get(session_id)

    def validate_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Validate session and update activity.

        Args:
            session_id: Session identifier

        Returns:
            Session info if valid, None otherwise
        """
        session = self._sessions.get(session_id)

        if not session:
            logger.warning(f"Session not found: {session_id}")
            return None

        if not session.is_active:
            logger.warning(f"Session inactive: {session_id}")
            return None

        if session.is_expired():
            logger.warning(f"Session expired: {session_id}")
            self.invalidate_session(
                session_id,
                reason="expired"
            )
            return None

        # Update activity
        session.update_activity()

        logger.debug(f"Session validated: {session_id}")

        return session

    def invalidate_session(
        self,
        session_id: str,
        reason: str = "logout"
    ) -> bool:
        """
        Invalidate a specific session.

        Args:
            session_id: Session to invalidate
            reason: Reason for invalidation (logout, timeout, security, expired)

        Returns:
            True if session was invalidated
        """
        session = self._sessions.get(session_id)

        if not session:
            logger.warning(f"Cannot invalidate session: not found {session_id}")
            return False

        if not session.is_active:
            logger.debug(f"Session already inactive: {session_id}")
            return False

        # Mark as inactive
        session.is_active = False
        session.invalidated_at = datetime.utcnow()
        session.invalidation_reason = reason

        logger.info(
            f"Session invalidated: {session_id} for user {session.user_id}, "
            f"reason: {reason}"
        )

        return True

    def invalidate_all_user_sessions(
        self,
        user_id: str,
        except_session_id: Optional[str] = None,
        reason: str = "logout_all"
    ) -> int:
        """
        Invalidate all sessions for a user (logout from all devices).

        Args:
            user_id: User identifier
            except_session_id: Optional session to keep active (current session)
            reason: Reason for invalidation

        Returns:
            Number of sessions invalidated
        """
        session_ids = self._user_sessions.get(user_id, [])

        count = 0
        for session_id in session_ids:
            if session_id == except_session_id:
                continue

            if self.invalidate_session(session_id, reason):
                count += 1

        logger.info(
            f"Invalidated {count} sessions for user {user_id}, "
            f"reason: {reason}"
        )

        return count

    def list_user_sessions(
        self,
        user_id: str,
        include_inactive: bool = False
    ) -> List[SessionInfo]:
        """
        List all sessions for a user.

        Args:
            user_id: User identifier
            include_inactive: Include invalidated/expired sessions

        Returns:
            List of session information
        """
        session_ids = self._user_sessions.get(user_id, [])

        sessions = []
        for session_id in session_ids:
            session = self._sessions.get(session_id)

            if not session:
                continue

            # Filter by active status
            if not include_inactive and not session.is_active:
                continue

            sessions.append(session)

        # Sort by last activity (most recent first)
        sessions.sort(key=lambda s: s.last_activity_at, reverse=True)

        return sessions

    def get_active_session_count(self, user_id: str) -> int:
        """
        Get count of active sessions for user.

        Args:
            user_id: User identifier

        Returns:
            Number of active sessions
        """
        sessions = self.list_user_sessions(user_id, include_inactive=False)
        return len([s for s in sessions if not s.is_expired()])

    def refresh_session(self, session_id: str, extend_hours: Optional[int] = None) -> bool:
        """
        Refresh session expiration time.

        Args:
            session_id: Session to refresh
            extend_hours: Hours to extend (default: reset to full session_expire_hours)

        Returns:
            True if refreshed successfully
        """
        session = self._sessions.get(session_id)

        if not session or not session.is_active:
            return False

        # Update expiration
        if extend_hours:
            session.expires_at = datetime.utcnow() + timedelta(hours=extend_hours)
        else:
            session.expires_at = datetime.utcnow() + timedelta(hours=self.session_expire_hours)

        session.update_activity()

        logger.info(f"Session refreshed: {session_id}")

        return True

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired and inactive sessions from storage.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.utcnow()
        cleanup_threshold = now - timedelta(days=30)  # Remove sessions older than 30 days

        session_ids_to_remove = []

        for session_id, session in self._sessions.items():
            # Remove if expired and old, or inactive and very old
            should_remove = (
                (session.is_expired() and session.created_at < cleanup_threshold) or
                (not session.is_active and session.invalidated_at and
                 session.invalidated_at < cleanup_threshold)
            )

            if should_remove:
                session_ids_to_remove.append(session_id)

        # Remove sessions
        for session_id in session_ids_to_remove:
            session = self._sessions[session_id]

            # Remove from user sessions list
            if session.user_id in self._user_sessions:
                try:
                    self._user_sessions[session.user_id].remove(session_id)

                    # Clean up empty user session lists
                    if not self._user_sessions[session.user_id]:
                        del self._user_sessions[session.user_id]
                except ValueError:
                    pass

            # Remove session
            del self._sessions[session_id]

        if session_ids_to_remove:
            logger.info(f"Cleaned up {len(session_ids_to_remove)} expired/inactive sessions")

        return len(session_ids_to_remove)

    def _enforce_session_limit(self, user_id: str) -> None:
        """Enforce maximum session limit per user."""
        session_ids = self._user_sessions.get(user_id, [])

        if len(session_ids) <= self.max_sessions_per_user:
            return

        # Get sessions and sort by last activity
        sessions = []
        for session_id in session_ids:
            session = self._sessions.get(session_id)
            if session and session.is_active:
                sessions.append(session)

        sessions.sort(key=lambda s: s.last_activity_at)

        # Invalidate oldest sessions
        excess_count = len(sessions) - self.max_sessions_per_user
        for i in range(excess_count):
            self.invalidate_session(
                sessions[i].session_id,
                reason="session_limit_exceeded"
            )

        logger.info(
            f"Enforced session limit for user {user_id}: "
            f"invalidated {excess_count} oldest sessions"
        )

    @staticmethod
    def _generate_session_id(user_id: str) -> str:
        """Generate unique session ID."""
        random_part = secrets.token_urlsafe(32)
        timestamp = datetime.utcnow().isoformat()

        # Create session ID with user context
        raw = f"{user_id}:{timestamp}:{random_part}"
        session_hash = hashlib.sha256(raw.encode()).hexdigest()

        return f"sess_{session_hash[:16]}"

    def get_session_statistics(self, user_id: str) -> Dict:
        """
        Get session statistics for user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with session statistics
        """
        sessions = self.list_user_sessions(user_id, include_inactive=True)

        active_sessions = [s for s in sessions if s.is_active and not s.is_expired()]
        expired_sessions = [s for s in sessions if s.is_expired()]
        invalidated_sessions = [s for s in sessions if not s.is_active and not s.is_expired()]

        # Calculate average session duration
        total_duration = sum(
            (s.get_duration().total_seconds() for s in sessions),
            0
        )
        avg_duration_hours = (total_duration / 3600 / len(sessions)) if sessions else 0

        return {
            "total_sessions": len(sessions),
            "active_sessions": len(active_sessions),
            "expired_sessions": len(expired_sessions),
            "invalidated_sessions": len(invalidated_sessions),
            "average_duration_hours": round(avg_duration_hours, 2),
            "devices": list({s.device_type for s in sessions if s.device_type}),
            "locations": list({s.location for s in sessions if s.location})
        }


def parse_user_agent(user_agent: str) -> Dict[str, Optional[str]]:
    """
    Parse user agent string to extract device info.

    Args:
        user_agent: User agent string

    Returns:
        Dictionary with device_type, os, browser
    """
    # Simple parsing (in production: use user-agents library)
    ua_lower = user_agent.lower()

    # Detect device type
    device_type = "desktop"
    if "mobile" in ua_lower or "android" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_type = "tablet"

    # Detect OS
    os = None
    if "windows" in ua_lower:
        os = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        os = "macOS"
    elif "linux" in ua_lower:
        os = "Linux"
    elif "android" in ua_lower:
        os = "Android"
    elif "ios" in ua_lower or "iphone" in ua_lower or "ipad" in ua_lower:
        os = "iOS"

    # Detect browser
    browser = None
    if "chrome" in ua_lower and "edg" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "edg" in ua_lower:
        browser = "Edge"

    return {
        "device_type": device_type,
        "os": os,
        "browser": browser
    }
