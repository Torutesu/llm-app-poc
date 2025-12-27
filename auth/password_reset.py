"""
Password reset functionality via email.

Features:
- Generate secure password reset tokens
- Send reset emails with expiring links
- Validate reset tokens
- Update passwords securely
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)


class PasswordResetToken(BaseModel):
    """Password reset token data."""

    token_hash: str = Field(description="Hashed reset token")
    user_id: str = Field(description="User requesting reset")
    email: EmailStr = Field(description="User email")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(description="Token expiration time")
    used: bool = Field(default=False, description="Whether token has been used")
    used_at: Optional[datetime] = Field(default=None)


class EmailProvider:
    """Email provider interface for sending password reset emails."""

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)

        Returns:
            True if sent successfully
        """
        # In production, integrate with SendGrid, AWS SES, Mailgun, etc.
        logger.info(f"[Email Mock] Sending to {to_email}")
        print(f"\n=== EMAIL SENT ===")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        if html_body:
            print(f"\nHTML Body:\n{html_body}")
        print(f"==================\n")
        return True


class PasswordResetManager:
    """Manage password reset flow."""

    def __init__(
        self,
        email_provider: Optional[EmailProvider] = None,
        base_url: str = "http://localhost:3000"
    ):
        """
        Initialize password reset manager.

        Args:
            email_provider: Email provider for sending reset emails
            base_url: Base URL for reset links (e.g., "https://app.example.com")
        """
        self.email_provider = email_provider or EmailProvider()
        self.base_url = base_url.rstrip('/')

        # In-memory token storage (in production: use database)
        # token_hash -> PasswordResetToken
        self._tokens: Dict[str, PasswordResetToken] = {}

        # user_id -> token_hash (to find active tokens)
        self._user_tokens: Dict[str, str] = {}

        # Settings
        self.token_expire_hours = 24  # Reset tokens valid for 24 hours
        self.token_length = 32  # bytes

    def request_password_reset(self, user_id: str, email: str) -> bool:
        """
        Initiate password reset flow.

        Args:
            user_id: User identifier
            email: User email address

        Returns:
            True if reset email sent successfully
        """
        # Invalidate any existing reset tokens for this user
        self._invalidate_user_tokens(user_id)

        # Generate secure random token
        raw_token = secrets.token_urlsafe(self.token_length)

        # Hash token for storage
        token_hash = self._hash_token(raw_token)

        # Create token record
        expires_at = datetime.utcnow() + timedelta(hours=self.token_expire_hours)

        token_data = PasswordResetToken(
            token_hash=token_hash,
            user_id=user_id,
            email=email,
            expires_at=expires_at
        )

        # Store token
        self._tokens[token_hash] = token_data
        self._user_tokens[user_id] = token_hash

        # Generate reset link
        reset_link = f"{self.base_url}/reset-password?token={raw_token}"

        # Send email
        success = self._send_reset_email(email, reset_link, expires_at)

        if success:
            logger.info(f"Password reset requested for user {user_id} ({email})")
        else:
            logger.error(f"Failed to send password reset email to {email}")

        return success

    def validate_reset_token(self, token: str) -> Optional[PasswordResetToken]:
        """
        Validate password reset token.

        Args:
            token: Raw reset token from URL

        Returns:
            Token data if valid, None otherwise
        """
        # Hash token to look up
        token_hash = self._hash_token(token)

        token_data = self._tokens.get(token_hash)

        if not token_data:
            logger.warning("Invalid reset token: not found")
            return None

        # Check if already used
        if token_data.used:
            logger.warning(f"Reset token already used for user {token_data.user_id}")
            return None

        # Check expiration
        if datetime.utcnow() > token_data.expires_at:
            logger.warning(f"Reset token expired for user {token_data.user_id}")
            return None

        logger.info(f"Reset token validated for user {token_data.user_id}")

        return token_data

    def reset_password(
        self,
        token: str,
        new_password: str,
        password_hash_func
    ) -> Optional[str]:
        """
        Reset password using valid token.

        Args:
            token: Raw reset token from URL
            new_password: New password (plain text)
            password_hash_func: Function to hash password

        Returns:
            User ID if successful, None otherwise
        """
        # Validate token
        token_data = self.validate_reset_token(token)

        if not token_data:
            return None

        # Hash new password
        new_password_hash = password_hash_func(new_password)

        # Mark token as used
        token_hash = self._hash_token(token)
        token_data.used = True
        token_data.used_at = datetime.utcnow()

        # Remove from user_tokens mapping
        if token_data.user_id in self._user_tokens:
            del self._user_tokens[token_data.user_id]

        logger.info(f"Password reset completed for user {token_data.user_id}")

        # Send confirmation email
        self._send_reset_confirmation_email(token_data.email)

        return token_data.user_id

    def cancel_reset_request(self, user_id: str) -> bool:
        """
        Cancel pending password reset request.

        Args:
            user_id: User identifier

        Returns:
            True if cancelled
        """
        return self._invalidate_user_tokens(user_id)

    def _invalidate_user_tokens(self, user_id: str) -> bool:
        """Invalidate all reset tokens for a user."""
        if user_id not in self._user_tokens:
            return False

        token_hash = self._user_tokens[user_id]

        if token_hash in self._tokens:
            self._tokens[token_hash].used = True
            self._tokens[token_hash].used_at = datetime.utcnow()

        del self._user_tokens[user_id]

        logger.info(f"Invalidated reset tokens for user {user_id}")

        return True

    def _send_reset_email(
        self,
        email: str,
        reset_link: str,
        expires_at: datetime
    ) -> bool:
        """Send password reset email."""
        subject = "Password Reset Request"

        # Plain text body
        body = f"""
You have requested to reset your password.

Click the link below to reset your password:
{reset_link}

This link will expire at {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC.

If you did not request this reset, please ignore this email.
Your password will remain unchanged.
"""

        # HTML body
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .footer {{ color: #666; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Password Reset Request</h2>
        <p>You have requested to reset your password.</p>
        <p>Click the button below to reset your password:</p>
        <a href="{reset_link}" class="button">Reset Password</a>
        <p>Or copy and paste this link into your browser:</p>
        <p>{reset_link}</p>
        <p>This link will expire at <strong>{expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC</strong>.</p>
        <div class="footer">
            <p>If you did not request this reset, please ignore this email. Your password will remain unchanged.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.email_provider.send_email(
            to_email=email,
            subject=subject,
            body=body.strip(),
            html_body=html_body
        )

    def _send_reset_confirmation_email(self, email: str) -> bool:
        """Send confirmation email after password reset."""
        subject = "Password Reset Successful"

        body = f"""
Your password has been successfully reset.

If you did not perform this action, please contact support immediately.
"""

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .alert {{
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .warning {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Password Reset Successful</h2>
        <div class="alert">
            <strong>Success!</strong> Your password has been successfully reset.
        </div>
        <div class="warning">
            <strong>Security Notice:</strong> If you did not perform this action, please contact support immediately.
        </div>
    </div>
</body>
</html>
"""

        return self.email_provider.send_email(
            to_email=email,
            subject=subject,
            body=body.strip(),
            html_body=html_body
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from storage.

        Returns:
            Number of tokens removed
        """
        now = datetime.utcnow()
        expired_hashes = []

        for token_hash, token_data in self._tokens.items():
            if now > token_data.expires_at:
                expired_hashes.append(token_hash)

                # Remove from user mapping
                if token_data.user_id in self._user_tokens:
                    if self._user_tokens[token_data.user_id] == token_hash:
                        del self._user_tokens[token_data.user_id]

        # Remove expired tokens
        for token_hash in expired_hashes:
            del self._tokens[token_hash]

        if expired_hashes:
            logger.info(f"Cleaned up {len(expired_hashes)} expired reset tokens")

        return len(expired_hashes)

    def get_user_active_token(self, user_id: str) -> Optional[PasswordResetToken]:
        """
        Get active reset token for user.

        Args:
            user_id: User identifier

        Returns:
            Active token data or None
        """
        token_hash = self._user_tokens.get(user_id)

        if not token_hash:
            return None

        token_data = self._tokens.get(token_hash)

        if not token_data or token_data.used or datetime.utcnow() > token_data.expires_at:
            return None

        return token_data
