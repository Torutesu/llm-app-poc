"""
Unit tests for authentication system.

Tests:
- User creation and authentication
- Two-factor authentication (TOTP/SMS)
- Password reset
- Session management
"""
import pytest
from datetime import datetime, timedelta

from auth.jwt_handler import JWTConfig, JWTHandler
from auth.password_reset import PasswordResetManager
from auth.session_manager import SessionManager, DeviceInfo
from auth.two_factor import TwoFactorManager
from auth.user_manager import UserManager


@pytest.fixture
def jwt_handler():
    """Create JWT handler for testing."""
    config = JWTConfig(secret_key="test-secret-key-do-not-use-in-production")
    return JWTHandler(config)


@pytest.fixture
def user_manager(jwt_handler):
    """Create user manager for testing."""
    return UserManager(jwt_handler)


@pytest.fixture
def tfa_manager():
    """Create 2FA manager for testing."""
    return TwoFactorManager()


@pytest.fixture
def session_manager():
    """Create session manager for testing."""
    return SessionManager()


@pytest.fixture
def password_reset_manager():
    """Create password reset manager for testing."""
    return PasswordResetManager()


class TestUserManager:
    """Tests for UserManager."""

    def test_create_user(self, user_manager):
        """Test user creation."""
        user = user_manager.create_user(
            email="test@example.com",
            tenant_id="tenant_123",
            password="SecurePassword123!",
            name="Test User",
            roles=["viewer"]
        )

        assert user.email == "test@example.com"
        assert user.tenant_id == "tenant_123"
        assert user.name == "Test User"
        assert user.roles == ["viewer"]
        assert user.password_hash is not None
        assert user.is_active is True

    def test_duplicate_user(self, user_manager):
        """Test creating duplicate user raises error."""
        user_manager.create_user(
            email="test@example.com",
            tenant_id="tenant_123",
            password="Password123!"
        )

        with pytest.raises(ValueError, match="already exists"):
            user_manager.create_user(
                email="test@example.com",
                tenant_id="tenant_123",
                password="Password123!"
            )

    def test_authenticate_password_success(self, user_manager):
        """Test successful password authentication."""
        user_manager.create_user(
            email="test@example.com",
            tenant_id="tenant_123",
            password="SecurePassword123!"
        )

        user = user_manager.authenticate_password(
            email="test@example.com",
            password="SecurePassword123!"
        )

        assert user is not None
        assert user.email == "test@example.com"
        assert user.last_login_at is not None

    def test_authenticate_password_failure(self, user_manager):
        """Test failed password authentication."""
        user_manager.create_user(
            email="test@example.com",
            tenant_id="tenant_123",
            password="SecurePassword123!"
        )

        user = user_manager.authenticate_password(
            email="test@example.com",
            password="WrongPassword"
        )

        assert user is None

    def test_create_tokens(self, user_manager):
        """Test JWT token creation."""
        user = user_manager.create_user(
            email="test@example.com",
            tenant_id="tenant_123",
            password="Password123!"
        )

        tokens = user_manager.create_tokens_for_user(user)

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "Bearer"


class TestTwoFactorAuth:
    """Tests for Two-Factor Authentication."""

    def test_setup_totp(self, tfa_manager):
        """Test TOTP setup."""
        setup_data = tfa_manager.setup_totp(
            user_id="user_123",
            user_email="test@example.com"
        )

        assert "secret" in setup_data
        assert "provisioning_uri" in setup_data
        assert "qr_code_url" in setup_data
        assert len(setup_data["secret"]) > 0

    def test_verify_totp_setup(self, tfa_manager):
        """Test TOTP verification during setup."""
        import pyotp

        # Setup TOTP
        setup_data = tfa_manager.setup_totp(
            user_id="user_123",
            user_email="test@example.com"
        )

        # Generate code
        totp = pyotp.TOTP(setup_data["secret"])
        code = totp.now()

        # Verify setup
        is_valid = tfa_manager.verify_totp_setup("user_123", code)

        assert is_valid is True

        # Check that 2FA is enabled
        assert tfa_manager.is_2fa_enabled("user_123") is True

    def test_verify_totp_login(self, tfa_manager):
        """Test TOTP verification during login."""
        import pyotp

        # Setup and enable TOTP
        setup_data = tfa_manager.setup_totp("user_123", "test@example.com")
        totp = pyotp.TOTP(setup_data["secret"])
        tfa_manager.verify_totp_setup("user_123", totp.now())

        # Generate new code for login
        code = totp.now()

        # Verify login
        is_valid = tfa_manager.verify_totp("user_123", code)

        assert is_valid is True

    def test_verify_invalid_totp(self, tfa_manager):
        """Test TOTP verification with invalid code."""
        # Setup TOTP
        setup_data = tfa_manager.setup_totp("user_123", "test@example.com")

        # Try invalid code
        is_valid = tfa_manager.verify_totp_setup("user_123", "000000")

        assert is_valid is False

    def test_backup_codes(self, tfa_manager):
        """Test backup codes."""
        import pyotp

        # Setup and enable TOTP
        setup_data = tfa_manager.setup_totp("user_123", "test@example.com")
        totp = pyotp.TOTP(setup_data["secret"])
        tfa_manager.verify_totp_setup("user_123", totp.now())

        # Get config
        config = tfa_manager.get_config("user_123")

        # Should have 10 backup codes
        assert len(config.backup_codes) == 10

    def test_disable_totp(self, tfa_manager):
        """Test disabling TOTP."""
        import pyotp

        # Setup and enable TOTP
        setup_data = tfa_manager.setup_totp("user_123", "test@example.com")
        totp = pyotp.TOTP(setup_data["secret"])
        tfa_manager.verify_totp_setup("user_123", totp.now())

        # Disable TOTP
        tfa_manager.disable_totp("user_123")

        # Check that 2FA is disabled
        assert tfa_manager.is_2fa_enabled("user_123") is False


class TestSessionManagement:
    """Tests for Session Management."""

    def test_create_session(self, session_manager):
        """Test session creation."""
        device_info = DeviceInfo(
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1",
            device_type="desktop",
            os="macOS",
            browser="Chrome"
        )

        session = session_manager.create_session(
            user_id="user_123",
            tenant_id="tenant_456",
            device_info=device_info
        )

        assert session.user_id == "user_123"
        assert session.tenant_id == "tenant_456"
        assert session.is_active is True
        assert session.device_type == "desktop"
        assert session.os == "macOS"

    def test_validate_session(self, session_manager):
        """Test session validation."""
        session = session_manager.create_session(
            user_id="user_123",
            tenant_id="tenant_456"
        )

        validated = session_manager.validate_session(session.session_id)

        assert validated is not None
        assert validated.session_id == session.session_id

    def test_invalidate_session(self, session_manager):
        """Test session invalidation."""
        session = session_manager.create_session(
            user_id="user_123",
            tenant_id="tenant_456"
        )

        # Invalidate session
        success = session_manager.invalidate_session(
            session.session_id,
            reason="user_logout"
        )

        assert success is True

        # Session should no longer be valid
        validated = session_manager.validate_session(session.session_id)
        assert validated is None

    def test_invalidate_all_sessions(self, session_manager):
        """Test invalidating all user sessions."""
        # Create multiple sessions
        session1 = session_manager.create_session("user_123", "tenant_456")
        session2 = session_manager.create_session("user_123", "tenant_456")
        session3 = session_manager.create_session("user_123", "tenant_456")

        # Invalidate all except session1
        count = session_manager.invalidate_all_user_sessions(
            user_id="user_123",
            except_session_id=session1.session_id,
            reason="logout_all"
        )

        assert count == 2

        # Session1 should still be valid
        assert session_manager.validate_session(session1.session_id) is not None

        # Session2 and session3 should be invalid
        assert session_manager.validate_session(session2.session_id) is None
        assert session_manager.validate_session(session3.session_id) is None


class TestPasswordReset:
    """Tests for Password Reset."""

    def test_request_password_reset(self, password_reset_manager):
        """Test password reset request."""
        success = password_reset_manager.request_password_reset(
            user_id="user_123",
            email="test@example.com"
        )

        assert success is True

    def test_validate_reset_token(self, password_reset_manager):
        """Test reset token validation."""
        # Request reset
        password_reset_manager.request_password_reset(
            user_id="user_123",
            email="test@example.com"
        )

        # Get token
        token_data = password_reset_manager.get_user_active_token("user_123")

        assert token_data is not None
        assert token_data.user_id == "user_123"
        assert token_data.email == "test@example.com"

    def test_expired_token(self, password_reset_manager):
        """Test expired token validation."""
        from datetime import datetime, timedelta

        # Request reset
        password_reset_manager.request_password_reset(
            user_id="user_123",
            email="test@example.com"
        )

        # Get and expire token
        token_hash = password_reset_manager._user_tokens["user_123"]
        token_data = password_reset_manager._tokens[token_hash]
        token_data.expires_at = datetime.utcnow() - timedelta(hours=1)

        # Should be invalid
        active_token = password_reset_manager.get_user_active_token("user_123")
        assert active_token is None


class TestJWTHandler:
    """Tests for JWT handling."""

    def test_create_access_token(self, jwt_handler):
        """Test access token creation."""
        token = jwt_handler.create_access_token(
            user_id="user_123",
            tenant_id="tenant_456",
            email="test@example.com",
            roles=["viewer"]
        )

        assert token is not None
        assert len(token) > 0

    def test_verify_token(self, jwt_handler):
        """Test token verification."""
        token = jwt_handler.create_access_token(
            user_id="user_123",
            tenant_id="tenant_456",
            email="test@example.com"
        )

        claims = jwt_handler.verify_token(token)

        assert claims.sub == "user_123"
        assert claims.tenant_id == "tenant_456"
        assert claims.email == "test@example.com"

    def test_invalid_token(self, jwt_handler):
        """Test invalid token verification."""
        with pytest.raises(Exception):
            jwt_handler.verify_token("invalid_token_12345")

    def test_create_refresh_token(self, jwt_handler):
        """Test refresh token creation."""
        token = jwt_handler.create_refresh_token(
            user_id="user_123",
            tenant_id="tenant_456"
        )

        claims = jwt_handler.verify_token(token)

        assert claims.token_type == "refresh"
        assert claims.sub == "user_123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
