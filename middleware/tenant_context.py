"""
Tenant context middleware for hybrid multi-tenant/single-tenant architecture.
"""
import contextvars
import logging
from typing import Optional

from config.deployment import DeploymentConfig, TenantMetadata

logger = logging.getLogger(__name__)

# Thread-safe tenant context
_tenant_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_context", default=None
)
_user_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_context", default=None
)


class TenantContext:
    """Manage tenant context for the current request."""

    @staticmethod
    def set_tenant(tenant_id: str) -> None:
        """Set the tenant ID for the current context."""
        _tenant_context.set(tenant_id)
        logger.debug(f"Tenant context set to: {tenant_id}")

    @staticmethod
    def get_tenant() -> Optional[str]:
        """Get the tenant ID for the current context."""
        return _tenant_context.get()

    @staticmethod
    def require_tenant() -> str:
        """
        Get the tenant ID, raising an error if not set.

        Raises:
            ValueError: If tenant context is not set
        """
        tenant_id = _tenant_context.get()
        if not tenant_id:
            raise ValueError("Tenant context not set")
        return tenant_id

    @staticmethod
    def set_user(user_id: str) -> None:
        """Set the user ID for the current context."""
        _user_context.set(user_id)
        logger.debug(f"User context set to: {user_id}")

    @staticmethod
    def get_user() -> Optional[str]:
        """Get the user ID for the current context."""
        return _user_context.get()

    @staticmethod
    def clear() -> None:
        """Clear the tenant and user context."""
        _tenant_context.set(None)
        _user_context.set(None)


class TenantMiddleware:
    """Middleware to extract and validate tenant from requests."""

    def __init__(self, deployment_config: DeploymentConfig):
        """
        Initialize tenant middleware.

        Args:
            deployment_config: Deployment configuration
        """
        self.deployment_config = deployment_config

    def extract_tenant_from_request(self, request_data: dict) -> str:
        """
        Extract tenant ID from request.

        Priority order:
        1. Single-tenant mode: use configured tenant_id
        2. JWT token claim 'tenant_id'
        3. Request header 'X-Tenant-ID'
        4. Request body 'tenant_id' field

        Args:
            request_data: Request payload/headers

        Returns:
            Extracted tenant ID

        Raises:
            ValueError: If tenant cannot be determined
        """
        # Single-tenant mode: always use configured tenant
        if self.deployment_config.is_single_tenant():
            tenant_id = self.deployment_config.tenant_id
            if not tenant_id:
                raise ValueError("tenant_id not configured for single-tenant mode")
            logger.info(f"Single-tenant mode: using tenant_id={tenant_id}")
            return tenant_id

        # Multi-tenant mode: extract from request
        tenant_id = None

        # 1. Check JWT token (if present)
        jwt_payload = request_data.get("jwt_payload", {})
        tenant_id = jwt_payload.get("tenant_id")

        # 2. Check header
        if not tenant_id:
            headers = request_data.get("headers", {})
            tenant_id = headers.get("x-tenant-id") or headers.get("X-Tenant-ID")

        # 3. Check request body
        if not tenant_id:
            body = request_data.get("body", {})
            tenant_id = body.get("tenant_id")

        if not tenant_id and self.deployment_config.require_tenant_in_request:
            raise ValueError(
                "tenant_id is required. Provide in JWT, X-Tenant-ID header, or request body"
            )

        if tenant_id:
            logger.info(f"Multi-tenant mode: extracted tenant_id={tenant_id}")

        return tenant_id or "default"

    def extract_user_from_request(self, request_data: dict) -> Optional[str]:
        """
        Extract user ID from request.

        Args:
            request_data: Request payload/headers

        Returns:
            User ID if found, None otherwise
        """
        # JWT token
        jwt_payload = request_data.get("jwt_payload", {})
        user_id = jwt_payload.get("sub") or jwt_payload.get("user_id")

        # Request body
        if not user_id:
            body = request_data.get("body", {})
            user_id = body.get("user") or body.get("user_id")

        return user_id

    def process_request(self, request_data: dict) -> dict:
        """
        Process incoming request and set tenant context.

        Args:
            request_data: Request data including headers, body, JWT

        Returns:
            Enriched request data with tenant_id

        Raises:
            ValueError: If tenant validation fails
        """
        # Extract tenant and user
        tenant_id = self.extract_tenant_from_request(request_data)
        user_id = self.extract_user_from_request(request_data)

        # Set context
        TenantContext.set_tenant(tenant_id)
        if user_id:
            TenantContext.set_user(user_id)

        # Add to request data
        request_data["tenant_id"] = tenant_id
        request_data["user_id"] = user_id

        logger.info(f"Request processed: tenant={tenant_id}, user={user_id}")

        return request_data

    def validate_tenant_access(
        self,
        request_tenant_id: str,
        resource_tenant_id: str
    ) -> bool:
        """
        Validate tenant has access to resource.

        Args:
            request_tenant_id: Tenant making the request
            resource_tenant_id: Tenant owning the resource

        Returns:
            True if access allowed

        Raises:
            PermissionError: If access denied
        """
        if not self.deployment_config.validate_tenant_access(
            request_tenant_id, resource_tenant_id
        ):
            raise PermissionError(
                f"Tenant {request_tenant_id} cannot access resources "
                f"owned by tenant {resource_tenant_id}"
            )
        return True


# Example usage with Pathway REST connector
def create_tenant_aware_handler(deployment_config: DeploymentConfig):
    """
    Create a request handler that enforces tenant context.

    Args:
        deployment_config: Deployment configuration

    Returns:
        Decorated handler function
    """
    middleware = TenantMiddleware(deployment_config)

    def handler_wrapper(original_handler):
        def wrapped_handler(request_data: dict, **kwargs):
            try:
                # Process request and set tenant context
                enriched_request = middleware.process_request(request_data)

                # Call original handler with tenant context set
                result = original_handler(enriched_request, **kwargs)

                return result
            except Exception as e:
                logger.error(f"Tenant middleware error: {e}")
                raise
            finally:
                # Clean up context
                TenantContext.clear()

        return wrapped_handler

    return handler_wrapper
