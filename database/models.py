"""
SQLAlchemy database models for authentication system.

Tables:
- users: User accounts
- user_2fa_config: Two-factor authentication configuration
- sessions: Active user sessions
- password_reset_tokens: Password reset tokens
- audit_logs: Security audit trail
"""
from datetime import datetime
from typing import List

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class UserModel(Base):
    """User account model."""

    __tablename__ = "users"

    # Primary key
    user_id = Column(String(100), primary_key=True, index=True)

    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Null for OAuth-only users

    # OAuth
    oauth_provider = Column(String(50), nullable=True)
    oauth_provider_user_id = Column(String(255), nullable=True, index=True)

    # Profile
    name = Column(String(255), nullable=True)
    given_name = Column(String(255), nullable=True)
    family_name = Column(String(255), nullable=True)
    picture = Column(Text, nullable=True)

    # Multi-tenancy
    tenant_id = Column(String(100), nullable=False, index=True)

    # Authorization
    roles = Column(JSON, nullable=False, default=list)  # List of role names
    custom_permissions = Column(JSON, nullable=False, default=list)  # Additional permissions

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    tfa_config = relationship("TwoFactorConfigModel", back_populates="user", uselist=False)
    sessions = relationship("SessionModel", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogModel", back_populates="user", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_user_tenant_email', 'tenant_id', 'email'),
        Index('idx_user_oauth', 'oauth_provider', 'oauth_provider_user_id'),
    )


class TwoFactorConfigModel(Base):
    """Two-factor authentication configuration."""

    __tablename__ = "user_2fa_config"

    # Primary key
    config_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    user_id = Column(String(100), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)

    # TOTP configuration
    is_totp_enabled = Column(Boolean, default=False, nullable=False)
    totp_secret = Column(String(255), nullable=True)  # Encrypted in production
    totp_verified_at = Column(DateTime, nullable=True)

    # SMS configuration
    is_sms_enabled = Column(Boolean, default=False, nullable=False)
    phone_number = Column(String(20), nullable=True)
    sms_verified_at = Column(DateTime, nullable=True)

    # Backup codes
    backup_codes = Column(JSON, nullable=False, default=list)  # Hashed codes

    # Settings
    preferred_method = Column(Enum('totp', 'sms', name='tfa_method'), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel", back_populates="tfa_config")


class SessionModel(Base):
    """User session model."""

    __tablename__ = "sessions"

    # Primary key
    session_id = Column(String(100), primary_key=True, index=True)

    # Foreign key
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)

    # Device information
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    device_name = Column(String(255), nullable=True)
    os = Column(String(100), nullable=True)
    browser = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Network information
    ip_address = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_current = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    invalidated_at = Column(DateTime, nullable=True)
    invalidation_reason = Column(String(100), nullable=True)

    # Relationships
    user = relationship("UserModel", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'is_active'),
        Index('idx_session_expires', 'expires_at'),
    )


class PasswordResetTokenModel(Base):
    """Password reset token model."""

    __tablename__ = "password_reset_tokens"

    # Primary key
    token_id = Column(Integer, primary_key=True, autoincrement=True)

    # Token
    token_hash = Column(String(255), unique=True, nullable=False, index=True)

    # User information
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True)
    email = Column(String(255), nullable=False)

    # Status
    used = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_reset_token_expires', 'expires_at', 'used'),
    )


class AuditLogModel(Base):
    """Security audit log model."""

    __tablename__ = "audit_logs"

    # Primary key
    log_id = Column(Integer, primary_key=True, autoincrement=True)

    # User information
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=True, index=True)

    # Event information
    event_type = Column(String(100), nullable=False, index=True)  # login, logout, 2fa_enable, etc.
    event_category = Column(String(50), nullable=False)  # authentication, authorization, security
    action = Column(String(255), nullable=False)
    resource = Column(String(255), nullable=True)

    # Result
    success = Column(Boolean, nullable=False)
    failure_reason = Column(Text, nullable=True)

    # Context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)

    # Additional data
    metadata = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("UserModel", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index('idx_audit_user_created', 'user_id', 'created_at'),
        Index('idx_audit_event_created', 'event_type', 'created_at'),
        Index('idx_audit_tenant_created', 'tenant_id', 'created_at'),
    )


class RateLimitModel(Base):
    """Rate limiting model."""

    __tablename__ = "rate_limits"

    # Primary key
    limit_id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifier (IP address, user_id, etc.)
    identifier = Column(String(255), nullable=False, index=True)

    # Limit type
    limit_type = Column(String(100), nullable=False)  # login_attempt, otp_request, etc.

    # Count
    attempt_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    first_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reset_at = Column(DateTime, nullable=False)

    # Status
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_until = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_ratelimit_identifier_type', 'identifier', 'limit_type'),
        Index('idx_ratelimit_blocked_until', 'blocked_until'),
    )
