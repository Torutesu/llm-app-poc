"""
Control plane for managing tenants in hybrid multi/single-tenant architecture.

This service manages:
- Tenant registration and metadata
- Routing to multi-tenant vs single-tenant instances
- Tenant tier management
- Resource allocation
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from config.deployment import DeploymentMode, TenantMetadata, TenantTier
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TenantRoutingInfo(BaseModel):
    """Routing information for a tenant."""

    tenant_id: str
    deployment_mode: DeploymentMode
    instance_url: str  # API endpoint for this tenant
    is_dedicated: bool
    tier: TenantTier


class TenantManager:
    """
    Central tenant management service.

    In production, this would be backed by a database (PostgreSQL).
    For now, using in-memory storage for demonstration.
    """

    def __init__(self):
        """Initialize tenant manager."""
        # In-memory tenant registry
        # In production: self.db = connect_to_postgres()
        self._tenants: Dict[str, TenantMetadata] = {}
        self._routing_table: Dict[str, TenantRoutingInfo] = {}

        # Multi-tenant shared instance URL
        self.shared_instance_url = "https://api.yoursaas.com"

    def register_tenant(
        self,
        tenant_name: str,
        tier: TenantTier = TenantTier.STANDARD,
        deployment_mode: Optional[DeploymentMode] = None
    ) -> TenantMetadata:
        """
        Register a new tenant/organization.

        Args:
            tenant_name: Organization name
            tier: Pricing tier
            deployment_mode: Force specific deployment mode (or auto-assign)

        Returns:
            Created tenant metadata
        """
        # Generate tenant_id
        tenant_id = self._generate_tenant_id(tenant_name)

        # Auto-assign deployment mode based on tier
        if deployment_mode is None:
            if tier == TenantTier.DEDICATED:
                deployment_mode = DeploymentMode.SINGLE_TENANT
            else:
                deployment_mode = DeploymentMode.MULTI_TENANT

        # Determine instance URL
        if deployment_mode == DeploymentMode.SINGLE_TENANT:
            # Provision dedicated instance
            instance_url = self._provision_dedicated_instance(tenant_id)
        else:
            # Use shared multi-tenant instance
            instance_url = self.shared_instance_url

        # Create metadata
        tenant = TenantMetadata(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            tier=tier,
            deployment_mode=deployment_mode,
            dedicated_instance_url=instance_url if deployment_mode == DeploymentMode.SINGLE_TENANT else None,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            # Tier-based feature flags
            custom_model_allowed=(tier in [TenantTier.ENTERPRISE, TenantTier.DEDICATED]),
            advanced_security=(tier in [TenantTier.ENTERPRISE, TenantTier.DEDICATED]),
            sso_enabled=(tier in [TenantTier.ENTERPRISE, TenantTier.DEDICATED]),
            api_rate_limit=self._get_rate_limit_for_tier(tier),
        )

        # Store tenant
        self._tenants[tenant_id] = tenant

        # Update routing table
        self._routing_table[tenant_id] = TenantRoutingInfo(
            tenant_id=tenant_id,
            deployment_mode=deployment_mode,
            instance_url=instance_url,
            is_dedicated=(deployment_mode == DeploymentMode.SINGLE_TENANT),
            tier=tier
        )

        logger.info(
            f"Registered tenant: {tenant_id} ({tenant_name}), "
            f"tier={tier}, mode={deployment_mode}, url={instance_url}"
        )

        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[TenantMetadata]:
        """
        Get tenant metadata.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant metadata or None
        """
        return self._tenants.get(tenant_id)

    def get_routing_info(self, tenant_id: str) -> Optional[TenantRoutingInfo]:
        """
        Get routing information for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Routing info or None
        """
        return self._routing_table.get(tenant_id)

    def list_tenants(
        self,
        tier: Optional[TenantTier] = None,
        deployment_mode: Optional[DeploymentMode] = None
    ) -> List[TenantMetadata]:
        """
        List all tenants with optional filters.

        Args:
            tier: Filter by tier
            deployment_mode: Filter by deployment mode

        Returns:
            List of tenant metadata
        """
        tenants = list(self._tenants.values())

        if tier:
            tenants = [t for t in tenants if t.tier == tier]

        if deployment_mode:
            tenants = [t for t in tenants if t.deployment_mode == deployment_mode]

        return tenants

    def upgrade_tenant_tier(self, tenant_id: str, new_tier: TenantTier) -> TenantMetadata:
        """
        Upgrade/downgrade tenant tier.

        May trigger migration from multi-tenant to single-tenant.

        Args:
            tenant_id: Tenant to upgrade
            new_tier: New pricing tier

        Returns:
            Updated tenant metadata

        Raises:
            ValueError: If tenant not found
        """
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        old_tier = tenant.tier
        old_mode = tenant.deployment_mode

        # Update tier
        tenant.tier = new_tier
        tenant.updated_at = datetime.utcnow().isoformat()

        # Check if migration needed
        if new_tier == TenantTier.DEDICATED and old_mode == DeploymentMode.MULTI_TENANT:
            logger.info(f"Migrating {tenant_id} from multi-tenant to single-tenant")
            self._migrate_to_dedicated(tenant_id)

        elif new_tier != TenantTier.DEDICATED and old_mode == DeploymentMode.SINGLE_TENANT:
            logger.info(f"Migrating {tenant_id} from single-tenant to multi-tenant")
            self._migrate_to_shared(tenant_id)

        # Update feature flags
        tenant.custom_model_allowed = (new_tier in [TenantTier.ENTERPRISE, TenantTier.DEDICATED])
        tenant.advanced_security = (new_tier in [TenantTier.ENTERPRISE, TenantTier.DEDICATED])
        tenant.sso_enabled = (new_tier in [TenantTier.ENTERPRISE, TenantTier.DEDICATED])
        tenant.api_rate_limit = self._get_rate_limit_for_tier(new_tier)

        logger.info(f"Upgraded {tenant_id} from {old_tier} to {new_tier}")

        return tenant

    def _provision_dedicated_instance(self, tenant_id: str) -> str:
        """
        Provision a dedicated single-tenant instance.

        In production, this would:
        1. Create Kubernetes namespace/deployment
        2. Provision dedicated database
        3. Set up load balancer
        4. Configure DNS

        Args:
            tenant_id: Tenant identifier

        Returns:
            URL of provisioned instance
        """
        # Mock provisioning
        dedicated_url = f"https://{tenant_id}.dedicated.yoursaas.com"

        logger.info(f"Provisioned dedicated instance for {tenant_id}: {dedicated_url}")

        # In production: trigger infrastructure automation
        # - Terraform/Kubernetes deployment
        # - Database creation
        # - Configuration

        return dedicated_url

    def _migrate_to_dedicated(self, tenant_id: str) -> None:
        """
        Migrate tenant from multi-tenant to single-tenant.

        Steps:
        1. Provision dedicated instance
        2. Copy tenant data from shared to dedicated instance
        3. Update routing table
        4. Validate migration
        5. Decommission data from shared instance

        Args:
            tenant_id: Tenant to migrate
        """
        tenant = self._tenants[tenant_id]

        # Provision dedicated instance
        dedicated_url = self._provision_dedicated_instance(tenant_id)

        # Update tenant metadata
        tenant.deployment_mode = DeploymentMode.SINGLE_TENANT
        tenant.dedicated_instance_url = dedicated_url

        # Update routing
        self._routing_table[tenant_id] = TenantRoutingInfo(
            tenant_id=tenant_id,
            deployment_mode=DeploymentMode.SINGLE_TENANT,
            instance_url=dedicated_url,
            is_dedicated=True,
            tier=tenant.tier
        )

        logger.info(f"Migration to dedicated complete for {tenant_id}")

    def _migrate_to_shared(self, tenant_id: str) -> None:
        """
        Migrate tenant from single-tenant to multi-tenant.

        Args:
            tenant_id: Tenant to migrate
        """
        tenant = self._tenants[tenant_id]

        # Update tenant metadata
        tenant.deployment_mode = DeploymentMode.MULTI_TENANT
        old_dedicated_url = tenant.dedicated_instance_url
        tenant.dedicated_instance_url = None

        # Update routing
        self._routing_table[tenant_id] = TenantRoutingInfo(
            tenant_id=tenant_id,
            deployment_mode=DeploymentMode.MULTI_TENANT,
            instance_url=self.shared_instance_url,
            is_dedicated=False,
            tier=tenant.tier
        )

        # Decommission old dedicated instance
        logger.info(f"Decommissioning dedicated instance: {old_dedicated_url}")

        logger.info(f"Migration to shared complete for {tenant_id}")

    @staticmethod
    def _generate_tenant_id(tenant_name: str) -> str:
        """Generate unique tenant ID from name."""
        import re
        import uuid

        # Slugify name
        slug = re.sub(r'[^\w\s-]', '', tenant_name.lower())
        slug = re.sub(r'[-\s]+', '_', slug)

        # Add unique suffix
        suffix = uuid.uuid4().hex[:8]

        return f"{slug}_{suffix}"

    @staticmethod
    def _get_rate_limit_for_tier(tier: TenantTier) -> int:
        """Get API rate limit based on tier."""
        rate_limits = {
            TenantTier.FREE: 10,
            TenantTier.STANDARD: 100,
            TenantTier.ENTERPRISE: 500,
            TenantTier.DEDICATED: 1000,
        }
        return rate_limits.get(tier, 100)


# Singleton instance
_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    """Get global tenant manager instance."""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager
