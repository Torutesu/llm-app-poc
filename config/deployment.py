"""
Deployment configuration for hybrid multi-tenant/single-tenant architecture.
"""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DeploymentMode(str, Enum):
    """Deployment mode for the application."""
    MULTI_TENANT = "multi_tenant"  # Shared environment for multiple organizations
    SINGLE_TENANT = "single_tenant"  # Dedicated instance for one organization


class IsolationLevel(str, Enum):
    """Data isolation level."""
    LOGICAL = "logical"  # Tenant ID-based filtering in shared database/index
    PHYSICAL = "physical"  # Separate database/index per tenant


class TenantTier(str, Enum):
    """Tenant pricing/feature tier."""
    FREE = "free"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    DEDICATED = "dedicated"  # Single-tenant deployment


class DeploymentConfig(BaseModel):
    """Configuration for deployment mode and tenant isolation."""

    mode: DeploymentMode = Field(
        default=DeploymentMode.MULTI_TENANT,
        description="Deployment mode: multi_tenant (shared) or single_tenant (dedicated)"
    )

    # Single-tenant specific settings
    tenant_id: Optional[str] = Field(
        default=None,
        description="Fixed tenant ID for single-tenant deployments"
    )

    tenant_name: Optional[str] = Field(
        default=None,
        description="Organization name for single-tenant deployments"
    )

    # Isolation settings
    isolation_level: IsolationLevel = Field(
        default=IsolationLevel.LOGICAL,
        description="Data isolation level"
    )

    # Feature flags
    enable_cross_tenant_analytics: bool = Field(
        default=False,
        description="Allow aggregated analytics across tenants (multi-tenant only)"
    )

    require_tenant_in_request: bool = Field(
        default=True,
        description="Require tenant_id in API requests (multi-tenant only)"
    )

    # Security settings
    enforce_tenant_isolation: bool = Field(
        default=True,
        description="Strictly enforce tenant data isolation"
    )

    enable_audit_logging: bool = Field(
        default=True,
        description="Enable audit logs for compliance"
    )

    def is_multi_tenant(self) -> bool:
        """Check if running in multi-tenant mode."""
        return self.mode == DeploymentMode.MULTI_TENANT

    def is_single_tenant(self) -> bool:
        """Check if running in single-tenant mode."""
        return self.mode == DeploymentMode.SINGLE_TENANT

    def get_tenant_id(self, request_tenant_id: Optional[str] = None) -> str:
        """
        Get the effective tenant ID.

        Args:
            request_tenant_id: Tenant ID from incoming request

        Returns:
            Effective tenant ID to use

        Raises:
            ValueError: If tenant ID cannot be determined
        """
        if self.is_single_tenant():
            # Single-tenant: always use configured tenant_id
            if not self.tenant_id:
                raise ValueError("tenant_id must be configured for single-tenant mode")
            return self.tenant_id

        # Multi-tenant: use tenant_id from request
        if self.require_tenant_in_request and not request_tenant_id:
            raise ValueError("tenant_id is required in multi-tenant mode")

        if not request_tenant_id:
            raise ValueError("Cannot determine tenant_id")

        return request_tenant_id

    def validate_tenant_access(
        self,
        request_tenant_id: str,
        resource_tenant_id: str
    ) -> bool:
        """
        Validate that request tenant can access resource.

        Args:
            request_tenant_id: Tenant making the request
            resource_tenant_id: Tenant that owns the resource

        Returns:
            True if access allowed, False otherwise
        """
        if not self.enforce_tenant_isolation:
            return True

        return request_tenant_id == resource_tenant_id


class TenantMetadata(BaseModel):
    """Metadata about a tenant/organization."""

    tenant_id: str = Field(description="Unique tenant identifier")
    tenant_name: str = Field(description="Organization name")
    tier: TenantTier = Field(default=TenantTier.STANDARD)

    # Deployment info
    deployment_mode: DeploymentMode = Field(default=DeploymentMode.MULTI_TENANT)
    dedicated_instance_url: Optional[str] = Field(
        default=None,
        description="URL for dedicated single-tenant instance"
    )

    # Feature flags per tenant
    max_users: Optional[int] = Field(default=None, description="Maximum users allowed")
    max_documents: Optional[int] = Field(default=None, description="Maximum documents")
    custom_model_allowed: bool = Field(default=False)
    advanced_security: bool = Field(default=False)
    sso_enabled: bool = Field(default=False)

    # Resource limits
    api_rate_limit: int = Field(default=100, description="Requests per minute")
    storage_quota_gb: Optional[int] = Field(default=None)

    # Created/Updated timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
