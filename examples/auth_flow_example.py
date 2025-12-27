"""
Authentication flow examples.

Demonstrates:
1. Email/password authentication
2. OAuth authentication (Google, Microsoft, Okta)
3. Token refresh
4. Authenticated API calls
5. Role-based access control
"""
import asyncio
import logging

from auth.auth_middleware import Permissions, Roles
from auth.jwt_handler import JWTConfig, JWTHandler
from auth.oauth_providers import (
    Auth0Provider,
    GoogleOAuthProvider,
    MicrosoftOAuthProvider,
    OAuthConfig,
    OktaOAuthProvider,
)
from auth.user_manager import UserManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ========================================
# Example 1: Email/Password Authentication
# ========================================
def example_password_auth():
    """Demonstrate email/password authentication."""
    print("\n" + "=" * 60)
    print("Example 1: Email/Password Authentication")
    print("=" * 60)

    # Setup
    jwt_config = JWTConfig(
        secret_key="your-super-secret-key-change-in-production",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7
    )

    jwt_handler = JWTHandler(jwt_config)
    user_manager = UserManager(jwt_handler)

    # Create users for different tenants
    user1 = user_manager.create_user(
        email="alice@startup.com",
        tenant_id="startup_alpha",
        password="secure_password_123",
        name="Alice Smith",
        roles=[Roles.ADMIN]
    )

    user2 = user_manager.create_user(
        email="bob@company.com",
        tenant_id="company_beta",
        password="another_secure_pass",
        name="Bob Johnson",
        roles=[Roles.VIEWER]
    )

    print(f"\n✓ Created users:")
    print(f"  - {user1.email} (tenant: {user1.tenant_id}, roles: {user1.roles})")
    print(f"  - {user2.email} (tenant: {user2.tenant_id}, roles: {user2.roles})")

    # Authenticate Alice
    print(f"\n→ Authenticating {user1.email}...")
    authenticated_user = user_manager.authenticate_password(
        "alice@startup.com",
        "secure_password_123"
    )

    if authenticated_user:
        print(f"✓ Authentication successful!")

        # Create tokens
        tokens = user_manager.create_tokens_for_user(authenticated_user)

        print(f"\n✓ Generated tokens:")
        print(f"  - Access token: {tokens['access_token'][:50]}...")
        print(f"  - Refresh token: {tokens['refresh_token'][:50]}...")
        print(f"  - Expires in: {tokens['expires_in']} seconds")

        # Verify token
        claims = jwt_handler.verify_token(tokens['access_token'])
        print(f"\n✓ Token claims:")
        print(f"  - User ID: {claims.sub}")
        print(f"  - Tenant ID: {claims.tenant_id}")
        print(f"  - Email: {claims.email}")
        print(f"  - Roles: {claims.roles}")
        print(f"  - Permissions: {claims.permissions[:3]}... ({len(claims.permissions)} total)")

        return tokens

    else:
        print("✗ Authentication failed")


# ========================================
# Example 2: OAuth Authentication
# ========================================
async def example_oauth_auth():
    """Demonstrate OAuth authentication flow."""
    print("\n" + "=" * 60)
    print("Example 2: OAuth Authentication")
    print("=" * 60)

    # Google OAuth
    print("\n--- Google OAuth ---")

    google_config = OAuthConfig(
        provider_name="google",
        client_id="your-google-client-id",
        client_secret="your-google-client-secret",
        redirect_uri="https://yourapp.com/auth/callback",
        scopes=["openid", "email", "profile"]
    )

    google_provider = GoogleOAuthProvider(google_config)

    # Get authorization URL
    auth_url = google_provider.get_authorization_url(state="random_state_token")
    print(f"\n1. Redirect user to:")
    print(f"   {auth_url[:100]}...")

    print(f"\n2. User authorizes and is redirected back with 'code' parameter")
    print(f"   https://yourapp.com/auth/callback?code=AUTH_CODE&state=random_state_token")

    print(f"\n3. Exchange code for token (in production):")
    print(f"   token_data = await google_provider.exchange_code_for_token(code)")
    print(f"   user_info = await google_provider.get_user_info(token_data['access_token'])")

    # Cleanup
    await google_provider.close()

    # Microsoft OAuth
    print("\n--- Microsoft Azure AD OAuth ---")

    microsoft_config = OAuthConfig(
        provider_name="microsoft",
        client_id="your-azure-client-id",
        client_secret="your-azure-client-secret",
        redirect_uri="https://yourapp.com/auth/callback",
        tenant_id="common",  # or specific tenant ID
        scopes=["openid", "email", "profile", "User.Read"]
    )

    microsoft_provider = MicrosoftOAuthProvider(microsoft_config)

    auth_url = microsoft_provider.get_authorization_url(state="random_state_token")
    print(f"\n1. Redirect user to Azure AD:")
    print(f"   {auth_url[:100]}...")

    await microsoft_provider.close()

    # Okta OAuth
    print("\n--- Okta OAuth ---")

    okta_config = OAuthConfig(
        provider_name="okta",
        client_id="your-okta-client-id",
        client_secret="your-okta-client-secret",
        redirect_uri="https://yourapp.com/auth/callback",
        scopes=["openid", "email", "profile"]
    )

    okta_provider = OktaOAuthProvider(okta_config, okta_domain="dev-123456.okta.com")

    auth_url = okta_provider.get_authorization_url(state="random_state_token")
    print(f"\n1. Redirect user to Okta:")
    print(f"   {auth_url[:100]}...")

    await okta_provider.close()


# ========================================
# Example 3: Token Refresh
# ========================================
def example_token_refresh():
    """Demonstrate token refresh."""
    print("\n" + "=" * 60)
    print("Example 3: Token Refresh")
    print("=" * 60)

    jwt_config = JWTConfig(
        secret_key="your-super-secret-key",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7
    )

    jwt_handler = JWTHandler(jwt_config)
    user_manager = UserManager(jwt_handler)

    # Create user
    user = user_manager.create_user(
        email="test@example.com",
        tenant_id="test_tenant",
        password="password123",
        roles=[Roles.EDITOR]
    )

    # Get tokens
    tokens = user_manager.create_tokens_for_user(user)
    print(f"\n✓ Initial tokens generated")
    print(f"  - Access token expires in: {jwt_config.access_token_expire_minutes} minutes")
    print(f"  - Refresh token expires in: {jwt_config.refresh_token_expire_days} days")

    # Simulate access token expiration
    print(f"\n⏰ Access token expired!")

    # Refresh access token
    print(f"\n→ Using refresh token to get new access token...")
    new_access_token = jwt_handler.refresh_access_token(tokens['refresh_token'])

    print(f"✓ New access token generated!")
    print(f"  - New token: {new_access_token[:50]}...")

    # Verify new token
    claims = jwt_handler.verify_token(new_access_token)
    print(f"✓ New token is valid for user: {claims.sub}")


# ========================================
# Example 4: Authenticated API Calls
# ========================================
def example_authenticated_api_calls():
    """Demonstrate authenticated API calls with RBAC."""
    print("\n" + "=" * 60)
    print("Example 4: Authenticated API Calls with RBAC")
    print("=" * 60)

    jwt_config = JWTConfig(secret_key="your-secret-key")
    jwt_handler = JWTHandler(jwt_config)
    user_manager = UserManager(jwt_handler)

    # Create users with different roles
    admin_user = user_manager.create_user(
        email="admin@company.com",
        tenant_id="company_xyz",
        password="admin_pass",
        roles=[Roles.ADMIN]
    )

    viewer_user = user_manager.create_user(
        email="viewer@company.com",
        tenant_id="company_xyz",
        password="viewer_pass",
        roles=[Roles.VIEWER]
    )

    print(f"\n✓ Created users:")
    print(f"  - Admin: {admin_user.email}")
    print(f"    Permissions: {admin_user.get_all_permissions()[:3]}... ({len(admin_user.get_all_permissions())} total)")
    print(f"  - Viewer: {viewer_user.email}")
    print(f"    Permissions: {viewer_user.get_all_permissions()}")

    # Admin makes authenticated request
    print(f"\n--- Admin User Request ---")
    admin_tokens = user_manager.create_tokens_for_user(admin_user)

    # Simulate API request
    request_data = {
        "headers": {
            "Authorization": f"Bearer {admin_tokens['access_token']}"
        },
        "body": {
            "query": "Show all financial documents"
        }
    }

    print(f"→ Request: POST /v2/answer")
    print(f"  Authorization: Bearer {admin_tokens['access_token'][:30]}...")
    print(f"  Query: {request_data['body']['query']}")

    # Check permissions
    claims = jwt_handler.verify_token(admin_tokens['access_token'])
    has_search = Permissions.SEARCH in claims.permissions
    has_delete = Permissions.DELETE_DOCUMENTS in claims.permissions

    print(f"\n✓ Admin permissions:")
    print(f"  - Can search: {has_search}")
    print(f"  - Can delete: {has_delete}")

    # Viewer makes authenticated request
    print(f"\n--- Viewer User Request ---")
    viewer_tokens = user_manager.create_tokens_for_user(viewer_user)

    claims = jwt_handler.verify_token(viewer_tokens['access_token'])
    has_search = Permissions.SEARCH in claims.permissions
    has_delete = Permissions.DELETE_DOCUMENTS in claims.permissions

    print(f"✓ Viewer permissions:")
    print(f"  - Can search: {has_search}")
    print(f"  - Can delete: {has_delete}")


# ========================================
# Example 5: Cross-Tenant Isolation
# ========================================
def example_tenant_isolation():
    """Demonstrate tenant isolation."""
    print("\n" + "=" * 60)
    print("Example 5: Cross-Tenant Isolation")
    print("=" * 60)

    jwt_config = JWTConfig(secret_key="your-secret-key")
    jwt_handler = JWTHandler(jwt_config)
    user_manager = UserManager(jwt_handler)

    # Create users in different tenants
    user_a = user_manager.create_user(
        email="user@tenant-a.com",
        tenant_id="tenant_a",
        password="pass123",
        roles=[Roles.ADMIN]
    )

    user_b = user_manager.create_user(
        email="user@tenant-b.com",
        tenant_id="tenant_b",
        password="pass123",
        roles=[Roles.ADMIN]
    )

    print(f"\n✓ Created users in separate tenants:")
    print(f"  - {user_a.email} → tenant_a")
    print(f"  - {user_b.email} → tenant_b")

    # User A tries to access their data
    tokens_a = user_manager.create_tokens_for_user(user_a)
    claims_a = jwt_handler.verify_token(tokens_a['access_token'])

    print(f"\n→ User A makes request:")
    print(f"  - User: {claims_a.email}")
    print(f"  - Tenant: {claims_a.tenant_id}")
    print(f"  ✓ Access granted to tenant_a data")

    # User A tries to access tenant B's data (should fail)
    print(f"\n→ User A tries to access tenant_b data:")
    print(f"  - User token tenant: {claims_a.tenant_id}")
    print(f"  - Resource tenant: tenant_b")
    print(f"  ✗ Access DENIED (tenant mismatch)")


# ========================================
# Main
# ========================================
def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("AUTHENTICATION SYSTEM EXAMPLES")
    print("=" * 60)

    # Example 1: Password auth
    example_password_auth()

    # Example 2: OAuth (async)
    asyncio.run(example_oauth_auth())

    # Example 3: Token refresh
    example_token_refresh()

    # Example 4: Authenticated API calls
    example_authenticated_api_calls()

    # Example 5: Tenant isolation
    example_tenant_isolation()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
