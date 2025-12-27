"""
Database repositories for CRUD operations.

Implements repository pattern for clean data access.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from database.models import (
    AuditLogModel,
    PasswordResetTokenModel,
    RateLimitModel,
    SessionModel,
    TwoFactorConfigModel,
    UserModel,
)


class UserRepository:
    """User repository for database operations."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create(self, user_data: dict) -> UserModel:
        """Create new user."""
        user = UserModel(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: str) -> Optional[UserModel]:
        """Get user by ID."""
        return self.db.query(UserModel).filter(UserModel.user_id == user_id).first()

    def get_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email."""
        return self.db.query(UserModel).filter(UserModel.email == email).first()

    def get_by_oauth(self, provider: str, provider_user_id: str) -> Optional[UserModel]:
        """Get user by OAuth provider credentials."""
        return self.db.query(UserModel).filter(
            and_(
                UserModel.oauth_provider == provider,
                UserModel.oauth_provider_user_id == provider_user_id
            )
        ).first()

    def get_by_tenant(self, tenant_id: str) -> List[UserModel]:
        """Get all users in a tenant."""
        return self.db.query(UserModel).filter(
            UserModel.tenant_id == tenant_id
        ).all()

    def update(self, user_id: str, update_data: dict) -> Optional[UserModel]:
        """Update user."""
        user = self.get_by_id(user_id)
        if not user:
            return None

        for key, value in update_data.items():
            setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id: str) -> bool:
        """Delete user (hard delete)."""
        user = self.get_by_id(user_id)
        if not user:
            return False

        self.db.delete(user)
        self.db.commit()
        return True

    def deactivate(self, user_id: str) -> Optional[UserModel]:
        """Deactivate user (soft delete)."""
        return self.update(user_id, {"is_active": False})


class TwoFactorConfigRepository:
    """Two-factor authentication configuration repository."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create(self, config_data: dict) -> TwoFactorConfigModel:
        """Create 2FA configuration."""
        config = TwoFactorConfigModel(**config_data)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_by_user_id(self, user_id: str) -> Optional[TwoFactorConfigModel]:
        """Get 2FA config for user."""
        return self.db.query(TwoFactorConfigModel).filter(
            TwoFactorConfigModel.user_id == user_id
        ).first()

    def update(self, user_id: str, update_data: dict) -> Optional[TwoFactorConfigModel]:
        """Update 2FA configuration."""
        config = self.get_by_user_id(user_id)
        if not config:
            return None

        for key, value in update_data.items():
            setattr(config, key, value)

        config.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(config)
        return config

    def delete(self, user_id: str) -> bool:
        """Delete 2FA configuration."""
        config = self.get_by_user_id(user_id)
        if not config:
            return False

        self.db.delete(config)
        self.db.commit()
        return True


class SessionRepository:
    """Session repository."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create(self, session_data: dict) -> SessionModel:
        """Create new session."""
        session = SessionModel(**session_data)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_id(self, session_id: str) -> Optional[SessionModel]:
        """Get session by ID."""
        return self.db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()

    def get_user_sessions(
        self,
        user_id: str,
        include_inactive: bool = False
    ) -> List[SessionModel]:
        """Get all sessions for user."""
        query = self.db.query(SessionModel).filter(
            SessionModel.user_id == user_id
        )

        if not include_inactive:
            query = query.filter(SessionModel.is_active == True)

        return query.order_by(SessionModel.last_activity_at.desc()).all()

    def get_active_sessions(self, user_id: str) -> List[SessionModel]:
        """Get active sessions for user."""
        now = datetime.utcnow()
        return self.db.query(SessionModel).filter(
            and_(
                SessionModel.user_id == user_id,
                SessionModel.is_active == True,
                SessionModel.expires_at > now
            )
        ).all()

    def update(self, session_id: str, update_data: dict) -> Optional[SessionModel]:
        """Update session."""
        session = self.get_by_id(session_id)
        if not session:
            return None

        for key, value in update_data.items():
            setattr(session, key, value)

        self.db.commit()
        self.db.refresh(session)
        return session

    def invalidate(self, session_id: str, reason: str) -> bool:
        """Invalidate session."""
        return self.update(session_id, {
            "is_active": False,
            "invalidated_at": datetime.utcnow(),
            "invalidation_reason": reason
        }) is not None

    def invalidate_user_sessions(
        self,
        user_id: str,
        except_session_id: Optional[str] = None
    ) -> int:
        """Invalidate all sessions for user."""
        query = self.db.query(SessionModel).filter(
            and_(
                SessionModel.user_id == user_id,
                SessionModel.is_active == True
            )
        )

        if except_session_id:
            query = query.filter(SessionModel.session_id != except_session_id)

        count = query.count()

        query.update({
            "is_active": False,
            "invalidated_at": datetime.utcnow(),
            "invalidation_reason": "user_action"
        })

        self.db.commit()
        return count

    def cleanup_expired(self, days_old: int = 30) -> int:
        """Remove old expired sessions."""
        threshold = datetime.utcnow() - timedelta(days=days_old)

        count = self.db.query(SessionModel).filter(
            or_(
                SessionModel.expires_at < threshold,
                and_(
                    SessionModel.is_active == False,
                    SessionModel.invalidated_at < threshold
                )
            )
        ).delete()

        self.db.commit()
        return count


class PasswordResetTokenRepository:
    """Password reset token repository."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create(self, token_data: dict) -> PasswordResetTokenModel:
        """Create password reset token."""
        token = PasswordResetTokenModel(**token_data)
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_by_token_hash(self, token_hash: str) -> Optional[PasswordResetTokenModel]:
        """Get token by hash."""
        return self.db.query(PasswordResetTokenModel).filter(
            PasswordResetTokenModel.token_hash == token_hash
        ).first()

    def get_user_active_token(self, user_id: str) -> Optional[PasswordResetTokenModel]:
        """Get active reset token for user."""
        now = datetime.utcnow()
        return self.db.query(PasswordResetTokenModel).filter(
            and_(
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.used == False,
                PasswordResetTokenModel.expires_at > now
            )
        ).first()

    def mark_as_used(self, token_hash: str) -> bool:
        """Mark token as used."""
        token = self.get_by_token_hash(token_hash)
        if not token:
            return False

        token.used = True
        token.used_at = datetime.utcnow()
        self.db.commit()
        return True

    def invalidate_user_tokens(self, user_id: str) -> int:
        """Invalidate all tokens for user."""
        count = self.db.query(PasswordResetTokenModel).filter(
            and_(
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.used == False
            )
        ).update({
            "used": True,
            "used_at": datetime.utcnow()
        })

        self.db.commit()
        return count

    def cleanup_expired(self) -> int:
        """Remove expired tokens."""
        now = datetime.utcnow()
        count = self.db.query(PasswordResetTokenModel).filter(
            PasswordResetTokenModel.expires_at < now
        ).delete()

        self.db.commit()
        return count


class AuditLogRepository:
    """Audit log repository."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create(self, log_data: dict) -> AuditLogModel:
        """Create audit log entry."""
        log = AuditLogModel(**log_data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_user_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogModel]:
        """Get audit logs for user."""
        return self.db.query(AuditLogModel).filter(
            AuditLogModel.user_id == user_id
        ).order_by(
            AuditLogModel.created_at.desc()
        ).offset(offset).limit(limit).all()

    def get_tenant_logs(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogModel]:
        """Get audit logs for tenant."""
        return self.db.query(AuditLogModel).filter(
            AuditLogModel.tenant_id == tenant_id
        ).order_by(
            AuditLogModel.created_at.desc()
        ).offset(offset).limit(limit).all()

    def get_by_event_type(
        self,
        event_type: str,
        limit: int = 100
    ) -> List[AuditLogModel]:
        """Get logs by event type."""
        return self.db.query(AuditLogModel).filter(
            AuditLogModel.event_type == event_type
        ).order_by(
            AuditLogModel.created_at.desc()
        ).limit(limit).all()

    def get_failed_logins(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[AuditLogModel]:
        """Get failed login attempts in last N hours."""
        threshold = datetime.utcnow() - timedelta(hours=hours)

        return self.db.query(AuditLogModel).filter(
            and_(
                AuditLogModel.event_type == "login_attempt",
                AuditLogModel.success == False,
                AuditLogModel.created_at > threshold
            )
        ).order_by(
            AuditLogModel.created_at.desc()
        ).limit(limit).all()


class RateLimitRepository:
    """Rate limit repository."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def get_or_create(
        self,
        identifier: str,
        limit_type: str,
        window_minutes: int = 60
    ) -> RateLimitModel:
        """Get or create rate limit record."""
        record = self.db.query(RateLimitModel).filter(
            and_(
                RateLimitModel.identifier == identifier,
                RateLimitModel.limit_type == limit_type,
                RateLimitModel.reset_at > datetime.utcnow()
            )
        ).first()

        if not record:
            reset_at = datetime.utcnow() + timedelta(minutes=window_minutes)
            record = RateLimitModel(
                identifier=identifier,
                limit_type=limit_type,
                attempt_count=0,
                reset_at=reset_at
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

        return record

    def increment(
        self,
        identifier: str,
        limit_type: str,
        max_attempts: int,
        block_minutes: int = 60
    ) -> tuple[bool, int]:
        """
        Increment attempt counter.

        Returns:
            Tuple of (is_blocked, remaining_attempts)
        """
        record = self.get_or_create(identifier, limit_type)

        # Check if already blocked
        if record.is_blocked and record.blocked_until and record.blocked_until > datetime.utcnow():
            return True, 0

        # Increment counter
        record.attempt_count += 1
        record.last_attempt_at = datetime.utcnow()

        # Check if should be blocked
        if record.attempt_count >= max_attempts:
            record.is_blocked = True
            record.blocked_until = datetime.utcnow() + timedelta(minutes=block_minutes)

        self.db.commit()

        remaining = max(0, max_attempts - record.attempt_count)
        return record.is_blocked, remaining

    def is_blocked(self, identifier: str, limit_type: str) -> bool:
        """Check if identifier is blocked."""
        record = self.db.query(RateLimitModel).filter(
            and_(
                RateLimitModel.identifier == identifier,
                RateLimitModel.limit_type == limit_type,
                RateLimitModel.is_blocked == True
            )
        ).first()

        if not record:
            return False

        # Check if block expired
        if record.blocked_until and record.blocked_until < datetime.utcnow():
            record.is_blocked = False
            record.blocked_until = None
            self.db.commit()
            return False

        return True

    def reset(self, identifier: str, limit_type: str) -> bool:
        """Reset rate limit for identifier."""
        record = self.db.query(RateLimitModel).filter(
            and_(
                RateLimitModel.identifier == identifier,
                RateLimitModel.limit_type == limit_type
            )
        ).first()

        if not record:
            return False

        record.attempt_count = 0
        record.is_blocked = False
        record.blocked_until = None
        self.db.commit()
        return True

    def cleanup_expired(self) -> int:
        """Remove expired rate limit records."""
        now = datetime.utcnow()
        count = self.db.query(RateLimitModel).filter(
            RateLimitModel.reset_at < now
        ).delete()

        self.db.commit()
        return count
