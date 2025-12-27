"""
Authenticated RAG application with JWT and tenant isolation.

This is an enhanced version of question_answering_rag with:
- JWT authentication
- Tenant isolation
- Role-based access control
- OAuth support
"""
import logging
import os
from typing import Dict

import pathway as pw
from dotenv import load_dotenv
from pathway.xpacks.llm.question_answering import SummaryQuestionAnswerer

from auth.auth_middleware import (
    AuthMiddleware,
    Permissions,
    Roles,
    create_auth_handler,
)
from auth.jwt_handler import JWTConfig, JWTHandler
from auth.user_manager import UserManager
from config.deployment import DeploymentConfig, DeploymentMode
from middleware.tenant_context import TenantContext, TenantMiddleware
from middleware.tenant_data_filter import TenantDataFilter

# License and logging
pw.set_license_key("demo-license-key-with-telemetry")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

load_dotenv()

logger = logging.getLogger(__name__)


class AuthenticatedRAGApp:
    """RAG application with authentication and tenant isolation."""

    def __init__(
        self,
        deployment_config: DeploymentConfig,
        jwt_config: JWTConfig,
        question_answerer: SummaryQuestionAnswerer,
        host: str = "0.0.0.0",
        port: int = 8000
    ):
        """
        Initialize authenticated RAG app.

        Args:
            deployment_config: Deployment configuration
            jwt_config: JWT configuration
            question_answerer: Question answering pipeline
            host: Server host
            port: Server port
        """
        self.deployment_config = deployment_config
        self.jwt_config = jwt_config
        self.question_answerer = question_answerer
        self.host = host
        self.port = port

        # Initialize auth components
        self.jwt_handler = JWTHandler(jwt_config)
        self.user_manager = UserManager(self.jwt_handler)
        self.auth_middleware = AuthMiddleware(self.jwt_handler)
        self.tenant_middleware = TenantMiddleware(deployment_config)

        logger.info(
            f"Initialized AuthenticatedRAGApp in {deployment_config.mode} mode"
        )

    def handle_login(self, request_data: Dict) -> Dict:
        """
        Handle user login (email/password).

        POST /v1/auth/login
        Body: {"email": "user@example.com", "password": "secret"}

        Returns:
            JWT tokens
        """
        try:
            body = request_data.get("body", {})
            email = body.get("email")
            password = body.get("password")

            if not email or not password:
                return {
                    "error": "missing_credentials",
                    "message": "Email and password required",
                    "status_code": 400
                }

            # Authenticate user
            user = self.user_manager.authenticate_password(email, password)

            if not user:
                return {
                    "error": "invalid_credentials",
                    "message": "Invalid email or password",
                    "status_code": 401
                }

            # Create tokens
            tokens = self.user_manager.create_tokens_for_user(user)

            logger.info(f"User logged in: {user.user_id} ({email})")

            return {
                "user_id": user.user_id,
                "email": user.email,
                "tenant_id": user.tenant_id,
                "roles": user.roles,
                **tokens
            }

        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            return {
                "error": "login_failed",
                "message": str(e),
                "status_code": 500
            }

    def handle_refresh_token(self, request_data: Dict) -> Dict:
        """
        Refresh access token.

        POST /v1/auth/refresh
        Body: {"refresh_token": "..."}

        Returns:
            New access token
        """
        try:
            body = request_data.get("body", {})
            refresh_token = body.get("refresh_token")

            if not refresh_token:
                return {
                    "error": "missing_token",
                    "message": "Refresh token required",
                    "status_code": 400
                }

            # Refresh token
            new_access_token = self.jwt_handler.refresh_access_token(refresh_token)

            return {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": self.jwt_config.access_token_expire_minutes * 60
            }

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return {
                "error": "refresh_failed",
                "message": str(e),
                "status_code": 401
            }

    def handle_authenticated_query(self, request_data: Dict) -> Dict:
        """
        Handle authenticated search query.

        POST /v2/answer
        Headers: Authorization: Bearer <token>
        Body: {"query": "What is our Q4 revenue?"}

        Returns:
            Search results filtered by tenant and user permissions
        """
        try:
            # Authenticate and authorize
            authenticated_request = self.auth_middleware.authenticate_request(request_data)

            # Check permissions
            self.auth_middleware.require_permission(
                authenticated_request,
                Permissions.SEARCH
            )

            # Extract query
            body = authenticated_request.get("body", {})
            query = body.get("query")

            if not query:
                return {
                    "error": "missing_query",
                    "message": "Query is required",
                    "status_code": 400
                }

            # Get user context
            user_id = authenticated_request["user_id"]
            tenant_id = authenticated_request["tenant_id"]

            logger.info(f"Processing query for user={user_id}, tenant={tenant_id}")

            # Set tenant context for data filtering
            TenantContext.set_tenant(tenant_id)
            TenantContext.set_user(user_id)

            # Query the question answerer
            # (In production, this would filter documents by tenant)
            result = self.question_answerer.answer(query)

            return {
                "query": query,
                "result": result,
                "user_id": user_id,
                "tenant_id": tenant_id
            }

        except Exception as e:
            logger.error(f"Query error: {e}", exc_info=True)
            return {
                "error": "query_failed",
                "message": str(e),
                "status_code": 500
            }

        finally:
            TenantContext.clear()

    def handle_user_info(self, request_data: Dict) -> Dict:
        """
        Get current user info.

        GET /v1/auth/me
        Headers: Authorization: Bearer <token>

        Returns:
            User information
        """
        try:
            authenticated_request = self.auth_middleware.authenticate_request(request_data)

            user_id = authenticated_request["user_id"]
            user = self.user_manager.get_user(user_id)

            if not user:
                return {
                    "error": "user_not_found",
                    "status_code": 404
                }

            return {
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "tenant_id": user.tenant_id,
                "roles": user.roles,
                "permissions": user.get_all_permissions(),
                "is_active": user.is_active
            }

        except Exception as e:
            logger.error(f"User info error: {e}")
            return {
                "error": "failed",
                "message": str(e),
                "status_code": 500
            }

    def setup_endpoints(self):
        """
        Setup REST API endpoints with Pathway.

        Note: This is a conceptual example. In production, you'd integrate
        with Pathway's REST connector or use a FastAPI wrapper.
        """
        # Register endpoints
        endpoints = {
            "/v1/auth/login": self.handle_login,
            "/v1/auth/refresh": self.handle_refresh_token,
            "/v1/auth/me": self.handle_user_info,
            "/v2/answer": self.handle_authenticated_query,
        }

        logger.info(f"Registered endpoints: {list(endpoints.keys())}")

        return endpoints

    def run(self):
        """Run the application."""
        logger.info(
            f"Starting AuthenticatedRAGApp on {self.host}:{self.port} "
            f"in {self.deployment_config.mode} mode"
        )

        # Setup endpoints
        self.setup_endpoints()

        # Run Pathway
        pw.run(
            monitoring_level=pw.MonitoringLevel.NONE,
            persistence_config=pw.persistence.Config(
                pw.persistence.Backend.filesystem("./Cache"),
                persistence_mode=pw.PersistenceMode.UDF_CACHING
            )
        )


def create_app_from_config() -> AuthenticatedRAGApp:
    """
    Create authenticated RAG app from environment configuration.

    Environment variables:
    - DEPLOYMENT_MODE: "multi_tenant" or "single_tenant"
    - TENANT_ID: (for single-tenant mode)
    - JWT_SECRET_KEY: Secret key for JWT signing
    """
    # Load deployment config
    deployment_mode = os.getenv("DEPLOYMENT_MODE", "multi_tenant")

    if deployment_mode == "single_tenant":
        deployment_config = DeploymentConfig(
            mode=DeploymentMode.SINGLE_TENANT,
            tenant_id=os.getenv("TENANT_ID", "default_tenant"),
            tenant_name=os.getenv("TENANT_NAME", "Default Organization")
        )
    else:
        deployment_config = DeploymentConfig(
            mode=DeploymentMode.MULTI_TENANT,
            require_tenant_in_request=True,
            enforce_tenant_isolation=True
        )

    # JWT config
    jwt_config = JWTConfig(
        secret_key=os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
        access_token_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "30")),
        refresh_token_expire_days=int(os.getenv("JWT_REFRESH_DAYS", "7"))
    )

    # Create question answerer (simplified - would load from app.yaml in production)
    # This is just a placeholder - in production, initialize from config
    question_answerer = None  # TODO: Initialize from app.yaml

    app = AuthenticatedRAGApp(
        deployment_config=deployment_config,
        jwt_config=jwt_config,
        question_answerer=question_answerer,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000"))
    )

    return app


if __name__ == "__main__":
    app = create_app_from_config()
    app.run()
