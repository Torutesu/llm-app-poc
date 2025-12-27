"""
Two-factor authentication (2FA) system.

Supports:
- TOTP (Time-based One-Time Password) using authenticator apps
- SMS-based OTP
- Backup codes for account recovery
"""
import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pyotp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TwoFactorMethod(str):
    """2FA method types."""
    TOTP = "totp"  # Authenticator app (Google Authenticator, Authy, etc.)
    SMS = "sms"  # SMS-based OTP


class TwoFactorConfig(BaseModel):
    """2FA configuration for a user."""

    user_id: str = Field(description="User identifier")

    # TOTP settings
    is_totp_enabled: bool = Field(default=False)
    totp_secret: Optional[str] = Field(
        default=None,
        description="Base32-encoded TOTP secret"
    )
    totp_verified_at: Optional[str] = Field(
        default=None,
        description="When TOTP was first verified"
    )

    # SMS settings
    is_sms_enabled: bool = Field(default=False)
    phone_number: Optional[str] = Field(
        default=None,
        description="Phone number for SMS OTP"
    )
    sms_verified_at: Optional[str] = Field(
        default=None,
        description="When phone number was verified"
    )

    # Backup codes
    backup_codes: List[str] = Field(
        default_factory=list,
        description="Hashed backup codes for recovery"
    )

    # Settings
    preferred_method: Optional[str] = Field(
        default=None,
        description="Preferred 2FA method"
    )

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def is_enabled(self) -> bool:
        """Check if any 2FA method is enabled."""
        return self.is_totp_enabled or self.is_sms_enabled


class SMSProvider:
    """SMS provider interface for sending OTP codes."""

    def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send SMS message.

        Args:
            phone_number: Recipient phone number
            message: Message content

        Returns:
            True if sent successfully
        """
        # In production, integrate with Twilio, AWS SNS, or similar service
        logger.info(f"[SMS Mock] Sending to {phone_number}: {message}")
        print(f"\n=== SMS SENT ===")
        print(f"To: {phone_number}")
        print(f"Message: {message}")
        print(f"================\n")
        return True


class TwoFactorManager:
    """Manage two-factor authentication."""

    def __init__(self, sms_provider: Optional[SMSProvider] = None):
        """
        Initialize 2FA manager.

        Args:
            sms_provider: SMS provider for sending OTP codes
        """
        self.sms_provider = sms_provider or SMSProvider()

        # In-memory storage (in production: use database)
        self._configs: Dict[str, TwoFactorConfig] = {}

        # Temporary SMS OTP storage (user_id -> (code, expiry))
        self._sms_otps: Dict[str, Tuple[str, datetime]] = {}

        # TOTP settings
        self.totp_issuer = "LLM-App-SaaS"
        self.totp_digits = 6
        self.totp_interval = 30  # seconds

        # SMS OTP settings
        self.sms_otp_length = 6
        self.sms_otp_expire_minutes = 5

    # ========== TOTP Methods ==========

    def setup_totp(self, user_id: str, user_email: str) -> Dict:
        """
        Setup TOTP for user.

        Args:
            user_id: User identifier
            user_email: User email (used in authenticator app)

        Returns:
            Dictionary with secret and provisioning URI
        """
        # Generate random secret
        secret = pyotp.random_base32()

        # Create provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=self.totp_issuer
        )

        # Get or create config
        config = self._get_or_create_config(user_id)
        config.totp_secret = secret
        config.updated_at = datetime.utcnow().isoformat()

        logger.info(f"TOTP setup initiated for user {user_id}")

        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?data={provisioning_uri}&size=200x200"
        }

    def verify_totp_setup(self, user_id: str, code: str) -> bool:
        """
        Verify TOTP code during setup to enable TOTP.

        Args:
            user_id: User identifier
            code: 6-digit TOTP code from authenticator app

        Returns:
            True if code is valid and TOTP is enabled
        """
        config = self._configs.get(user_id)

        if not config or not config.totp_secret:
            logger.warning(f"TOTP not setup for user {user_id}")
            return False

        # Verify code
        if not self._verify_totp_code(config.totp_secret, code):
            logger.warning(f"Invalid TOTP code during setup for user {user_id}")
            return False

        # Enable TOTP
        config.is_totp_enabled = True
        config.totp_verified_at = datetime.utcnow().isoformat()
        config.preferred_method = TwoFactorMethod.TOTP
        config.updated_at = datetime.utcnow().isoformat()

        # Generate backup codes
        config.backup_codes = self._generate_backup_codes()

        logger.info(f"TOTP enabled for user {user_id}")

        return True

    def verify_totp(self, user_id: str, code: str) -> bool:
        """
        Verify TOTP code during login.

        Args:
            user_id: User identifier
            code: 6-digit TOTP code

        Returns:
            True if valid
        """
        config = self._configs.get(user_id)

        if not config or not config.is_totp_enabled or not config.totp_secret:
            logger.warning(f"TOTP not enabled for user {user_id}")
            return False

        is_valid = self._verify_totp_code(config.totp_secret, code)

        if is_valid:
            logger.info(f"TOTP verified for user {user_id}")
        else:
            logger.warning(f"Invalid TOTP code for user {user_id}")

        return is_valid

    def _verify_totp_code(self, secret: str, code: str) -> bool:
        """Verify TOTP code against secret."""
        totp = pyotp.TOTP(secret)
        # Allow 1 interval before/after for clock skew
        return totp.verify(code, valid_window=1)

    def disable_totp(self, user_id: str) -> bool:
        """
        Disable TOTP for user.

        Args:
            user_id: User identifier

        Returns:
            True if disabled successfully
        """
        config = self._configs.get(user_id)

        if not config:
            return False

        config.is_totp_enabled = False
        config.totp_secret = None
        config.totp_verified_at = None
        config.updated_at = datetime.utcnow().isoformat()

        # Update preferred method if needed
        if config.preferred_method == TwoFactorMethod.TOTP:
            config.preferred_method = TwoFactorMethod.SMS if config.is_sms_enabled else None

        logger.info(f"TOTP disabled for user {user_id}")

        return True

    # ========== SMS OTP Methods ==========

    def setup_sms(self, user_id: str, phone_number: str) -> bool:
        """
        Setup SMS OTP for user and send verification code.

        Args:
            user_id: User identifier
            phone_number: Phone number (E.164 format recommended: +1234567890)

        Returns:
            True if verification SMS sent
        """
        # Get or create config
        config = self._get_or_create_config(user_id)
        config.phone_number = phone_number
        config.updated_at = datetime.utcnow().isoformat()

        # Send verification code
        return self.send_sms_otp(user_id, phone_number)

    def verify_sms_setup(self, user_id: str, code: str) -> bool:
        """
        Verify SMS OTP during setup to enable SMS 2FA.

        Args:
            user_id: User identifier
            code: 6-digit SMS OTP

        Returns:
            True if code is valid and SMS is enabled
        """
        if not self.verify_sms_otp(user_id, code):
            return False

        config = self._configs.get(user_id)

        if not config:
            return False

        # Enable SMS
        config.is_sms_enabled = True
        config.sms_verified_at = datetime.utcnow().isoformat()

        if not config.preferred_method:
            config.preferred_method = TwoFactorMethod.SMS

        config.updated_at = datetime.utcnow().isoformat()

        # Generate backup codes if not already generated
        if not config.backup_codes:
            config.backup_codes = self._generate_backup_codes()

        logger.info(f"SMS 2FA enabled for user {user_id}")

        return True

    def send_sms_otp(self, user_id: str, phone_number: str) -> bool:
        """
        Send SMS OTP to phone number.

        Args:
            user_id: User identifier
            phone_number: Phone number

        Returns:
            True if sent successfully
        """
        # Generate OTP
        otp = self._generate_sms_otp()

        # Store OTP with expiry
        expiry = datetime.utcnow() + timedelta(minutes=self.sms_otp_expire_minutes)
        self._sms_otps[user_id] = (otp, expiry)

        # Send SMS
        message = f"Your {self.totp_issuer} verification code is: {otp}. Valid for {self.sms_otp_expire_minutes} minutes."

        success = self.sms_provider.send_sms(phone_number, message)

        if success:
            logger.info(f"SMS OTP sent to user {user_id}")
        else:
            logger.error(f"Failed to send SMS OTP to user {user_id}")

        return success

    def verify_sms_otp(self, user_id: str, code: str) -> bool:
        """
        Verify SMS OTP code.

        Args:
            user_id: User identifier
            code: 6-digit SMS OTP

        Returns:
            True if valid
        """
        otp_data = self._sms_otps.get(user_id)

        if not otp_data:
            logger.warning(f"No SMS OTP found for user {user_id}")
            return False

        stored_otp, expiry = otp_data

        # Check expiry
        if datetime.utcnow() > expiry:
            logger.warning(f"SMS OTP expired for user {user_id}")
            del self._sms_otps[user_id]
            return False

        # Verify code
        if code != stored_otp:
            logger.warning(f"Invalid SMS OTP for user {user_id}")
            return False

        # Remove used OTP
        del self._sms_otps[user_id]

        logger.info(f"SMS OTP verified for user {user_id}")

        return True

    def _generate_sms_otp(self) -> str:
        """Generate random SMS OTP code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.sms_otp_length)])

    def disable_sms(self, user_id: str) -> bool:
        """
        Disable SMS 2FA for user.

        Args:
            user_id: User identifier

        Returns:
            True if disabled successfully
        """
        config = self._configs.get(user_id)

        if not config:
            return False

        config.is_sms_enabled = False
        config.phone_number = None
        config.sms_verified_at = None
        config.updated_at = datetime.utcnow().isoformat()

        # Update preferred method if needed
        if config.preferred_method == TwoFactorMethod.SMS:
            config.preferred_method = TwoFactorMethod.TOTP if config.is_totp_enabled else None

        logger.info(f"SMS 2FA disabled for user {user_id}")

        return True

    # ========== Backup Codes ==========

    def _generate_backup_codes(self, count: int = 10) -> List[str]:
        """
        Generate backup codes for account recovery.

        Args:
            count: Number of backup codes to generate

        Returns:
            List of hashed backup codes
        """
        codes = []

        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = secrets.token_hex(4).upper()
            # Hash it before storing
            hashed = self._hash_backup_code(code)
            codes.append(hashed)

            # Log unhashed code (in production: return to user securely)
            logger.info(f"Generated backup code: {code}")

        return codes

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """
        Verify and consume a backup code.

        Args:
            user_id: User identifier
            code: Backup code

        Returns:
            True if valid (code is removed after use)
        """
        config = self._configs.get(user_id)

        if not config or not config.backup_codes:
            logger.warning(f"No backup codes for user {user_id}")
            return False

        # Hash the provided code
        hashed = self._hash_backup_code(code)

        # Check if it exists
        if hashed not in config.backup_codes:
            logger.warning(f"Invalid backup code for user {user_id}")
            return False

        # Remove used backup code
        config.backup_codes.remove(hashed)
        config.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Backup code used for user {user_id}. {len(config.backup_codes)} codes remaining.")

        return True

    def regenerate_backup_codes(self, user_id: str) -> List[str]:
        """
        Regenerate backup codes (invalidates old ones).

        Args:
            user_id: User identifier

        Returns:
            List of new hashed backup codes
        """
        config = self._configs.get(user_id)

        if not config:
            raise ValueError(f"No 2FA config for user {user_id}")

        config.backup_codes = self._generate_backup_codes()
        config.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Regenerated backup codes for user {user_id}")

        return config.backup_codes

    @staticmethod
    def _hash_backup_code(code: str) -> str:
        """Hash backup code for storage."""
        return hashlib.sha256(code.encode()).hexdigest()

    # ========== General Methods ==========

    def get_config(self, user_id: str) -> Optional[TwoFactorConfig]:
        """Get 2FA configuration for user."""
        return self._configs.get(user_id)

    def is_2fa_enabled(self, user_id: str) -> bool:
        """Check if 2FA is enabled for user."""
        config = self._configs.get(user_id)
        return config.is_enabled() if config else False

    def get_enabled_methods(self, user_id: str) -> List[str]:
        """Get list of enabled 2FA methods for user."""
        config = self._configs.get(user_id)

        if not config:
            return []

        methods = []
        if config.is_totp_enabled:
            methods.append(TwoFactorMethod.TOTP)
        if config.is_sms_enabled:
            methods.append(TwoFactorMethod.SMS)

        return methods

    def _get_or_create_config(self, user_id: str) -> TwoFactorConfig:
        """Get existing config or create new one."""
        if user_id not in self._configs:
            self._configs[user_id] = TwoFactorConfig(user_id=user_id)

        return self._configs[user_id]

    def verify_2fa(self, user_id: str, code: str, method: Optional[str] = None) -> bool:
        """
        Verify 2FA code (auto-detects method if not specified).

        Args:
            user_id: User identifier
            code: 2FA code or backup code
            method: Specific method to use (totp/sms), or None to auto-detect

        Returns:
            True if valid
        """
        config = self._configs.get(user_id)

        if not config or not config.is_enabled():
            logger.warning(f"2FA not enabled for user {user_id}")
            return False

        # Try specified method
        if method == TwoFactorMethod.TOTP and config.is_totp_enabled:
            return self.verify_totp(user_id, code)
        elif method == TwoFactorMethod.SMS and config.is_sms_enabled:
            return self.verify_sms_otp(user_id, code)

        # Auto-detect: try preferred method first
        if config.preferred_method == TwoFactorMethod.TOTP and config.is_totp_enabled:
            if self.verify_totp(user_id, code):
                return True
        elif config.preferred_method == TwoFactorMethod.SMS and config.is_sms_enabled:
            if self.verify_sms_otp(user_id, code):
                return True

        # Try other enabled methods
        if config.is_totp_enabled and config.preferred_method != TwoFactorMethod.TOTP:
            if self.verify_totp(user_id, code):
                return True

        if config.is_sms_enabled and config.preferred_method != TwoFactorMethod.SMS:
            if self.verify_sms_otp(user_id, code):
                return True

        # Try backup code as last resort
        if self.verify_backup_code(user_id, code):
            return True

        logger.warning(f"All 2FA verification methods failed for user {user_id}")
        return False
