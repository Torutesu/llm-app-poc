"""
OAuth 2.0 provider integrations for enterprise SSO.

Supports:
- Google OAuth
- Microsoft Azure AD / Office 365
- Okta
- Auth0
- Generic OIDC providers
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OAuthConfig(BaseModel):
    """OAuth provider configuration."""

    provider_name: str = Field(description="Provider name (google, azure, okta, etc.)")
    client_id: str = Field(description="OAuth client ID")
    client_secret: str = Field(description="OAuth client secret")
    redirect_uri: str = Field(description="OAuth redirect URI")
    scopes: list[str] = Field(
        default_factory=list,
        description="OAuth scopes"
    )

    # Provider-specific settings
    tenant_id: Optional[str] = Field(
        default=None,
        description="Tenant ID (for Azure AD)"
    )
    authorization_endpoint: Optional[str] = Field(
        default=None,
        description="Custom authorization endpoint"
    )
    token_endpoint: Optional[str] = Field(
        default=None,
        description="Custom token endpoint"
    )
    userinfo_endpoint: Optional[str] = Field(
        default=None,
        description="Custom userinfo endpoint"
    )


class OAuthUserInfo(BaseModel):
    """User information from OAuth provider."""

    provider: str
    provider_user_id: str
    email: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None

    # Additional fields
    tenant_id: Optional[str] = None  # For mapping to our tenant system
    raw_data: Dict = Field(default_factory=dict)


class OAuthProvider(ABC):
    """Base class for OAuth providers."""

    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth provider.

        Args:
            config: OAuth configuration
        """
        self.config = config
        self.http_client = httpx.AsyncClient()

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """
        Get OAuth authorization URL for redirecting user.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL
        """
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from callback

        Returns:
            Token response with access_token, refresh_token, etc.
        """
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Get user information using access token.

        Args:
            access_token: OAuth access token

        Returns:
            User information
        """
        pass

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth provider."""

    AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

    DEFAULT_SCOPES = ["openid", "email", "profile"]

    def get_authorization_url(self, state: str) -> str:
        """Get Google OAuth authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes or self.DEFAULT_SCOPES),
            "state": state,
            "access_type": "offline",  # Get refresh token
            "prompt": "consent"
        }

        url = f"{self.AUTHORIZATION_ENDPOINT}?{urlencode(params)}"
        logger.info(f"Generated Google OAuth URL: {url[:100]}...")
        return url

    async def exchange_code_for_token(self, code: str) -> Dict:
        """Exchange code for Google access token."""
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code"
        }

        response = await self.http_client.post(self.TOKEN_ENDPOINT, data=data)
        response.raise_for_status()

        token_data = response.json()
        logger.info("Successfully exchanged code for Google token")

        return token_data

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from Google."""
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await self.http_client.get(self.USERINFO_ENDPOINT, headers=headers)
        response.raise_for_status()

        data = response.json()

        user_info = OAuthUserInfo(
            provider="google",
            provider_user_id=data["id"],
            email=data["email"],
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture=data.get("picture"),
            raw_data=data
        )

        logger.info(f"Retrieved Google user info: {user_info.email}")

        return user_info


class MicrosoftOAuthProvider(OAuthProvider):
    """Microsoft Azure AD / Office 365 OAuth provider."""

    AUTHORIZATION_ENDPOINT_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
    TOKEN_ENDPOINT_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    USERINFO_ENDPOINT = "https://graph.microsoft.com/v1.0/me"

    DEFAULT_SCOPES = ["openid", "email", "profile", "User.Read"]

    def get_authorization_url(self, state: str) -> str:
        """Get Microsoft OAuth authorization URL."""
        tenant = self.config.tenant_id or "common"

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes or self.DEFAULT_SCOPES),
            "state": state,
            "response_mode": "query"
        }

        endpoint = self.AUTHORIZATION_ENDPOINT_TEMPLATE.format(tenant=tenant)
        url = f"{endpoint}?{urlencode(params)}"

        logger.info(f"Generated Microsoft OAuth URL for tenant={tenant}")
        return url

    async def exchange_code_for_token(self, code: str) -> Dict:
        """Exchange code for Microsoft access token."""
        tenant = self.config.tenant_id or "common"

        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code",
            "scope": " ".join(self.config.scopes or self.DEFAULT_SCOPES)
        }

        endpoint = self.TOKEN_ENDPOINT_TEMPLATE.format(tenant=tenant)
        response = await self.http_client.post(endpoint, data=data)
        response.raise_for_status()

        token_data = response.json()
        logger.info("Successfully exchanged code for Microsoft token")

        return token_data

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from Microsoft Graph API."""
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await self.http_client.get(self.USERINFO_ENDPOINT, headers=headers)
        response.raise_for_status()

        data = response.json()

        user_info = OAuthUserInfo(
            provider="microsoft",
            provider_user_id=data["id"],
            email=data.get("mail") or data.get("userPrincipalName"),
            name=data.get("displayName"),
            given_name=data.get("givenName"),
            family_name=data.get("surname"),
            raw_data=data
        )

        logger.info(f"Retrieved Microsoft user info: {user_info.email}")

        return user_info


class OktaOAuthProvider(OAuthProvider):
    """Okta OAuth provider."""

    def __init__(self, config: OAuthConfig, okta_domain: str):
        """
        Initialize Okta provider.

        Args:
            config: OAuth configuration
            okta_domain: Okta domain (e.g., "dev-123456.okta.com")
        """
        super().__init__(config)
        self.okta_domain = okta_domain

        self.authorization_endpoint = f"https://{okta_domain}/oauth2/v1/authorize"
        self.token_endpoint = f"https://{okta_domain}/oauth2/v1/token"
        self.userinfo_endpoint = f"https://{okta_domain}/oauth2/v1/userinfo"

    DEFAULT_SCOPES = ["openid", "email", "profile"]

    def get_authorization_url(self, state: str) -> str:
        """Get Okta OAuth authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes or self.DEFAULT_SCOPES),
            "state": state
        }

        url = f"{self.authorization_endpoint}?{urlencode(params)}"
        logger.info(f"Generated Okta OAuth URL for domain={self.okta_domain}")
        return url

    async def exchange_code_for_token(self, code: str) -> Dict:
        """Exchange code for Okta access token."""
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code"
        }

        response = await self.http_client.post(self.token_endpoint, data=data)
        response.raise_for_status()

        token_data = response.json()
        logger.info("Successfully exchanged code for Okta token")

        return token_data

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from Okta."""
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await self.http_client.get(self.userinfo_endpoint, headers=headers)
        response.raise_for_status()

        data = response.json()

        user_info = OAuthUserInfo(
            provider="okta",
            provider_user_id=data["sub"],
            email=data["email"],
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture=data.get("picture"),
            raw_data=data
        )

        logger.info(f"Retrieved Okta user info: {user_info.email}")

        return user_info


class Auth0Provider(OAuthProvider):
    """Auth0 OAuth provider."""

    def __init__(self, config: OAuthConfig, auth0_domain: str):
        """
        Initialize Auth0 provider.

        Args:
            config: OAuth configuration
            auth0_domain: Auth0 domain (e.g., "your-tenant.auth0.com")
        """
        super().__init__(config)
        self.auth0_domain = auth0_domain

        self.authorization_endpoint = f"https://{auth0_domain}/authorize"
        self.token_endpoint = f"https://{auth0_domain}/oauth/token"
        self.userinfo_endpoint = f"https://{auth0_domain}/userinfo"

    DEFAULT_SCOPES = ["openid", "email", "profile"]

    def get_authorization_url(self, state: str) -> str:
        """Get Auth0 OAuth authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes or self.DEFAULT_SCOPES),
            "state": state
        }

        url = f"{self.authorization_endpoint}?{urlencode(params)}"
        logger.info(f"Generated Auth0 OAuth URL for domain={self.auth0_domain}")
        return url

    async def exchange_code_for_token(self, code: str) -> Dict:
        """Exchange code for Auth0 access token."""
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code"
        }

        response = await self.http_client.post(self.token_endpoint, json=data)
        response.raise_for_status()

        token_data = response.json()
        logger.info("Successfully exchanged code for Auth0 token")

        return token_data

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user info from Auth0."""
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await self.http_client.get(self.userinfo_endpoint, headers=headers)
        response.raise_for_status()

        data = response.json()

        user_info = OAuthUserInfo(
            provider="auth0",
            provider_user_id=data["sub"],
            email=data["email"],
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture=data.get("picture"),
            raw_data=data
        )

        logger.info(f"Retrieved Auth0 user info: {user_info.email}")

        return user_info


# Factory function
def create_oauth_provider(
    provider_name: str,
    config: OAuthConfig,
    **kwargs
) -> OAuthProvider:
    """
    Factory function to create OAuth provider.

    Args:
        provider_name: Provider name (google, microsoft, okta, auth0)
        config: OAuth configuration
        **kwargs: Provider-specific arguments

    Returns:
        OAuth provider instance

    Raises:
        ValueError: If provider not supported
    """
    providers = {
        "google": GoogleOAuthProvider,
        "microsoft": MicrosoftOAuthProvider,
        "azure": MicrosoftOAuthProvider,
        "okta": OktaOAuthProvider,
        "auth0": Auth0Provider,
    }

    provider_class = providers.get(provider_name.lower())

    if not provider_class:
        raise ValueError(
            f"Unsupported OAuth provider: {provider_name}. "
            f"Supported: {', '.join(providers.keys())}"
        )

    return provider_class(config, **kwargs)
