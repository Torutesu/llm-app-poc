"""
FastAPI endpoints for authentication system.

Provides REST API for:
- User authentication (login/logout)
- Two-factor authentication (TOTP/SMS)
- Password reset
- Session management
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from auth.jwt_handler import JWTConfig, JWTHandler
from auth.password_reset import PasswordResetManager
from auth.session_manager import DeviceInfo, SessionManager, parse_user_agent
from auth.two_factor import TwoFactorManager
from auth.user_manager import User, UserManager

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Security scheme
security = HTTPBearer()

# Initialize managers (in production: use dependency injection)
jwt_config = JWTConfig(secret_key="your-secret-key-change-in-production")
jwt_handler = JWTHandler(jwt_config)
password_reset_manager = PasswordResetManager()
user_manager = UserManager(jwt_handler, password_reset_manager)
tfa_manager = TwoFactorManager()
session_manager = SessionManager()


# ============================================================
# Request/Response Models
# ============================================================

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None
    tenant_id: str


class RegisterResponse(BaseModel):
    """User registration response."""
    user_id: str
    email: str
    message: str


class LoginRequest(BaseModel):
    """Login request."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    requires_2fa: bool = False
    session_id: Optional[str] = None


class TwoFactorVerifyRequest(BaseModel):
    """2FA verification request."""
    user_id: str
    code: str
    method: Optional[str] = None  # totp, sms, or auto-detect


class TOTPSetupResponse(BaseModel):
    """TOTP setup response."""
    secret: str
    provisioning_uri: str
    qr_code_url: str
    backup_codes: list[str] = []


class TOTPVerifyRequest(BaseModel):
    """TOTP verification request."""
    code: str


class SMSSetupRequest(BaseModel):
    """SMS setup request."""
    phone_number: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str = Field(min_length=8)


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    old_password: str
    new_password: str = Field(min_length=8)


class SessionResponse(BaseModel):
    """Session information response."""
    session_id: str
    device_name: Optional[str]
    device_type: Optional[str]
    os: Optional[str]
    browser: Optional[str]
    ip_address: Optional[str]
    location: Optional[str]
    created_at: datetime
    last_activity_at: datetime
    is_current: bool


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    status: str = "success"


# ============================================================
# Dependency Functions
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    logger.debug(f"Authenticating with token: {token[:50]}...")

    try:
        claims = jwt_handler.verify_token(token)
        logger.debug(f"Token verified for user_id: {claims.sub}")
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_manager.get_user(claims.sub)

    if not user:
        logger.warning(f"User not found: {claims.sub}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"User account inactive: {claims.sub}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    logger.debug(f"Authentication successful for user: {claims.sub}")
    return user


async def get_session_id(
    x_session_id: Optional[str] = Header(None)
) -> Optional[str]:
    """Get session ID from header."""
    return x_session_id


def create_device_info(request: Request) -> DeviceInfo:
    """
    Create device info from request.

    Args:
        request: FastAPI request

    Returns:
        Device information
    """
    user_agent = request.headers.get("user-agent", "")
    parsed = parse_user_agent(user_agent)

    # Get client IP (handle proxy headers)
    ip_address = request.headers.get("x-forwarded-for")
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None

    return DeviceInfo(
        user_agent=user_agent,
        ip_address=ip_address,
        device_type=parsed["device_type"],
        os=parsed["os"],
        browser=parsed["browser"]
    )


# ============================================================
# Authentication Endpoints
# ============================================================

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register a new user.

    Creates a new user account with email and password.
    """
    try:
        user = user_manager.create_user(
            email=request.email,
            tenant_id=request.tenant_id,
            password=request.password,
            name=request.name,
            roles=["viewer"]  # Default role
        )

        return RegisterResponse(
            user_id=user.user_id,
            email=user.email,
            message="User registered successfully"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    http_request: Request
):
    """
    Authenticate user with email and password.

    Returns JWT tokens if authentication succeeds.
    If 2FA is enabled, returns requires_2fa=True.
    """
    # Authenticate with password
    user = user_manager.authenticate_password(
        email=request_data.email,
        password=request_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if 2FA is required
    if tfa_manager.is_2fa_enabled(user.user_id):
        return LoginResponse(
            access_token="",
            refresh_token="",
            token_type="Bearer",
            expires_in=0,
            requires_2fa=True
        )

    # Create session
    device_info = create_device_info(http_request)
    session = session_manager.create_session(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        device_info=device_info,
        is_current=True
    )

    # Generate tokens
    tokens = user_manager.create_tokens_for_user(user)

    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
        requires_2fa=False,
        session_id=session.session_id
    )


@router.post("/login/2fa", response_model=LoginResponse)
async def login_with_2fa(
    request_data: TwoFactorVerifyRequest,
    http_request: Request
):
    """
    Complete login with 2FA code.

    Verifies 2FA code and returns JWT tokens if valid.
    """
    # Verify 2FA code
    is_valid = tfa_manager.verify_2fa(
        user_id=request_data.user_id,
        code=request_data.code,
        method=request_data.method
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code"
        )

    # Get user
    user = user_manager.get_user(request_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Create session
    device_info = create_device_info(http_request)
    session = session_manager.create_session(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        device_info=device_info,
        is_current=True
    )

    # Generate tokens
    tokens = user_manager.create_tokens_for_user(user)

    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
        requires_2fa=False,
        session_id=session.session_id
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id)
):
    """
    Logout current user.

    Invalidates the current session.
    """
    if session_id:
        session_manager.invalidate_session(session_id, reason="user_logout")

    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all")
async def logout_all_devices(
    current_user: User = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id)
):
    """
    Logout from all devices.

    Invalidates all sessions except the current one.
    """
    count = session_manager.invalidate_all_user_sessions(
        user_id=current_user.user_id,
        except_session_id=session_id,
        reason="logout_all_devices"
    )

    return MessageResponse(
        message=f"Logged out from {count} device(s)"
    )


# ============================================================
# Two-Factor Authentication Endpoints
# ============================================================

@router.post("/2fa/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(current_user: User = Depends(get_current_user)):
    """
    Setup TOTP (authenticator app) 2FA.

    Returns QR code URL and secret for authenticator app.
    """
    setup_data = tfa_manager.setup_totp(
        user_id=current_user.user_id,
        user_email=current_user.email
    )

    return TOTPSetupResponse(**setup_data)


@router.post("/2fa/totp/verify-setup")
async def verify_totp_setup(
    request_data: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Verify TOTP setup and enable 2FA.

    User must provide code from authenticator app to confirm setup.
    """
    is_valid = tfa_manager.verify_totp_setup(
        user_id=current_user.user_id,
        code=request_data.code
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code"
        )

    # Get backup codes
    config = tfa_manager.get_config(current_user.user_id)

    return {
        "message": "TOTP 2FA enabled successfully",
        "backup_codes_count": len(config.backup_codes) if config else 0
    }


@router.delete("/2fa/totp")
async def disable_totp(current_user: User = Depends(get_current_user)):
    """Disable TOTP 2FA."""
    tfa_manager.disable_totp(current_user.user_id)

    return MessageResponse(message="TOTP 2FA disabled")


@router.post("/2fa/sms/setup")
async def setup_sms(
    request_data: SMSSetupRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Setup SMS 2FA.

    Sends verification code to phone number.
    """
    success = tfa_manager.setup_sms(
        user_id=current_user.user_id,
        phone_number=request_data.phone_number
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send SMS"
        )

    return MessageResponse(message="Verification code sent to phone")


@router.post("/2fa/sms/verify-setup")
async def verify_sms_setup(
    request_data: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Verify SMS setup and enable SMS 2FA.

    User must provide code received via SMS.
    """
    is_valid = tfa_manager.verify_sms_setup(
        user_id=current_user.user_id,
        code=request_data.code
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid SMS code"
        )

    return MessageResponse(message="SMS 2FA enabled successfully")


@router.delete("/2fa/sms")
async def disable_sms(current_user: User = Depends(get_current_user)):
    """Disable SMS 2FA."""
    tfa_manager.disable_sms(current_user.user_id)

    return MessageResponse(message="SMS 2FA disabled")


@router.get("/2fa/status")
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    """Get 2FA status for current user."""
    config = tfa_manager.get_config(current_user.user_id)

    if not config:
        return {
            "enabled": False,
            "methods": []
        }

    return {
        "enabled": config.is_enabled(),
        "methods": tfa_manager.get_enabled_methods(current_user.user_id),
        "preferred_method": config.preferred_method
    }


# ============================================================
# Password Management Endpoints
# ============================================================

@router.post("/password-reset/request")
async def request_password_reset(request_data: PasswordResetRequest):
    """
    Request password reset.

    Sends reset link to email if user exists.
    Always returns success for security (don't reveal if email exists).
    """
    user_manager.request_password_reset(email=request_data.email)

    return MessageResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/password-reset/confirm")
async def confirm_password_reset(request_data: PasswordResetConfirmRequest):
    """
    Confirm password reset with token.

    Resets password using token from email.
    """
    success = user_manager.reset_password_with_token(
        token=request_data.token,
        new_password=request_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    return MessageResponse(message="Password reset successfully")


@router.post("/password/change")
async def change_password(
    request_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Change password (requires current password).

    Changes password for authenticated user.
    """
    success = user_manager.change_password(
        user_id=current_user.user_id,
        old_password=request_data.old_password,
        new_password=request_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password"
        )

    return MessageResponse(message="Password changed successfully")


# ============================================================
# Session Management Endpoints
# ============================================================

@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(current_user: User = Depends(get_current_user)):
    """
    List all active sessions for current user.

    Returns list of active sessions with device information.
    """
    sessions = session_manager.list_user_sessions(
        user_id=current_user.user_id,
        include_inactive=False
    )

    return [
        SessionResponse(
            session_id=s.session_id,
            device_name=s.device_name,
            device_type=s.device_type,
            os=s.os,
            browser=s.browser,
            ip_address=s.ip_address,
            location=s.location,
            created_at=s.created_at,
            last_activity_at=s.last_activity_at,
            is_current=s.is_current
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Logout from specific session.

    Invalidates a specific session (logout from specific device).
    """
    session = session_manager.get_session(session_id)

    if not session or session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    session_manager.invalidate_session(session_id, reason="user_logout")

    return MessageResponse(message="Session invalidated")


@router.get("/sessions/statistics")
async def get_session_statistics(current_user: User = Depends(get_current_user)):
    """Get session statistics for current user."""
    stats = session_manager.get_session_statistics(current_user.user_id)

    return stats


# ============================================================
# User Profile Endpoints
# ============================================================

@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "name": current_user.name,
        "roles": current_user.roles,
        "permissions": current_user.get_all_permissions(),
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
        "last_login_at": current_user.last_login_at
    }
