"""
Example: Hybrid multi-tenant/single-tenant deployment with Pathway.

This demonstrates how to use the tenant management system with Pathway LLM apps.
"""
import os
from pathlib import Path

import pathway as pw
from dotenv import load_dotenv

# Import our hybrid deployment modules
from config.deployment import DeploymentConfig, DeploymentMode
from control_plane.tenant_manager import get_tenant_manager, TenantTier
from middleware.tenant_context import TenantContext, TenantMiddleware
from middleware.tenant_data_filter import TenantDataFilter

load_dotenv()


# ========================================
# Scenario 1: Multi-tenant Deployment
# ========================================
def setup_multi_tenant_app():
    """
    Setup multi-tenant application serving multiple organizations.

    Characteristics:
    - Shared infrastructure
    - Logical data separation via tenant_id
    - Cost-efficient for many small/medium customers
    """
    print("\n=== Multi-Tenant Setup ===")

    # Load deployment config
    config = DeploymentConfig(
        mode=DeploymentMode.MULTI_TENANT,
        isolation_level="logical",
        require_tenant_in_request=True,
        enforce_tenant_isolation=True
    )

    # Register tenants
    tenant_manager = get_tenant_manager()

    tenant_a = tenant_manager.register_tenant("Startup Alpha", tier=TenantTier.STANDARD)
    tenant_b = tenant_manager.register_tenant("Company Beta", tier=TenantTier.ENTERPRISE)

    print(f"Registered tenants:")
    print(f"  - {tenant_a.tenant_id}: {tenant_a.tenant_name} ({tenant_a.tier})")
    print(f"  - {tenant_b.tenant_id}: {tenant_b.tenant_name} ({tenant_b.tier})")

    # Setup tenant-aware data sources
    # Assuming folder structure: ./data/tenants/{tenant_id}/documents/
    def create_tenant_sources(tenant_id: str):
        """Create data source for a specific tenant."""
        tenant_path = f"./data/tenants/{tenant_id}"
        Path(tenant_path).mkdir(parents=True, exist_ok=True)

        # Set tenant context
        TenantContext.set_tenant(tenant_id)

        # Create tenant-aware source
        source = TenantDataFilter.create_tenant_aware_source(
            pw.io.fs.read,
            tenant_id=tenant_id,
            path=tenant_path,
            format="binary",
            mode="streaming"
        )

        print(f"  Created source for tenant {tenant_id}: {tenant_path}")
        return source

    # Example: Create sources for both tenants
    # In production, this would be dynamic based on incoming requests
    sources = {
        tenant_a.tenant_id: create_tenant_sources(tenant_a.tenant_id),
        tenant_b.tenant_id: create_tenant_sources(tenant_b.tenant_id),
    }

    # API request handler with tenant middleware
    middleware = TenantMiddleware(config)

    def handle_query(request_data: dict):
        """Handle incoming query with tenant isolation."""
        # Process request and set tenant context
        enriched_request = middleware.process_request(request_data)

        tenant_id = enriched_request["tenant_id"]
        query = enriched_request["body"]["query"]

        print(f"Query from tenant {tenant_id}: {query}")

        # Fetch tenant-specific data
        tenant_source = sources.get(tenant_id)
        if not tenant_source:
            raise ValueError(f"No data source for tenant {tenant_id}")

        # Query only tenant's data
        # (In real app, this would go through indexer/retriever)
        results = f"Results for '{query}' from tenant {tenant_id}"

        return {"tenant_id": tenant_id, "results": results}

    # Simulate requests
    print("\nSimulating API requests:")

    req1 = {
        "headers": {"X-Tenant-ID": tenant_a.tenant_id},
        "body": {"query": "What is our revenue?"}
    }
    resp1 = handle_query(req1)
    print(f"  Response: {resp1}")

    req2 = {
        "headers": {"X-Tenant-ID": tenant_b.tenant_id},
        "body": {"query": "Show engineering docs"}
    }
    resp2 = handle_query(req2)
    print(f"  Response: {resp2}")

    return config, tenant_manager


# ========================================
# Scenario 2: Single-tenant Deployment
# ========================================
def setup_single_tenant_app(tenant_id: str = "megacorp_12345678"):
    """
    Setup single-tenant dedicated instance for large enterprise.

    Characteristics:
    - Dedicated infrastructure
    - Physical data separation
    - Custom configurations and features
    - Higher cost but maximum security/performance
    """
    print("\n=== Single-Tenant (Dedicated) Setup ===")

    # Load deployment config for dedicated instance
    config = DeploymentConfig(
        mode=DeploymentMode.SINGLE_TENANT,
        tenant_id=tenant_id,
        tenant_name="MegaCorp Inc.",
        isolation_level="physical",
        require_tenant_in_request=False,  # Not needed
        enforce_tenant_isolation=False,  # Only one tenant
    )

    print(f"Dedicated instance for tenant: {config.tenant_id}")
    print(f"Organization: {config.tenant_name}")

    # Setup data source (no tenant filtering needed)
    data_path = "./data"  # All data belongs to this tenant
    Path(data_path).mkdir(parents=True, exist_ok=True)

    source = pw.io.fs.read(
        data_path,
        format="binary",
        mode="streaming"
    )
    print(f"Data source: {data_path}")

    # API handler (no tenant middleware needed)
    def handle_query(request_data: dict):
        """Handle query in single-tenant mode."""
        query = request_data["body"]["query"]

        # No tenant filtering needed - all data belongs to this tenant
        print(f"Query: {query}")

        results = f"Results for '{query}' (tenant: {config.tenant_id})"

        return {"results": results}

    # Simulate request (no tenant ID needed in request)
    print("\nSimulating API request:")
    req = {"body": {"query": "Find all customer contracts"}}
    resp = handle_query(req)
    print(f"  Response: {resp}")

    return config


# ========================================
# Scenario 3: Hybrid - Upgrade Tenant
# ========================================
def demo_tenant_upgrade():
    """
    Demonstrate tenant upgrade from multi-tenant to single-tenant.

    Scenario: Enterprise customer starts on Standard tier (multi-tenant),
    then upgrades to Dedicated tier (single-tenant).
    """
    print("\n=== Hybrid: Tenant Upgrade Demo ===")

    tenant_manager = get_tenant_manager()

    # Start with Standard tier on multi-tenant
    tenant = tenant_manager.register_tenant(
        "Growing Company",
        tier=TenantTier.STANDARD
    )

    print(f"Initial setup:")
    print(f"  Tenant: {tenant.tenant_id}")
    print(f"  Tier: {tenant.tier}")
    print(f"  Deployment: {tenant.deployment_mode}")
    print(f"  Instance: {tenant_manager.get_routing_info(tenant.tenant_id).instance_url}")

    # Customer upgrades to Dedicated tier
    print(f"\nUpgrading to Dedicated tier...")
    upgraded_tenant = tenant_manager.upgrade_tenant_tier(
        tenant.tenant_id,
        TenantTier.DEDICATED
    )

    routing = tenant_manager.get_routing_info(tenant.tenant_id)

    print(f"After upgrade:")
    print(f"  Tier: {upgraded_tenant.tier}")
    print(f"  Deployment: {upgraded_tenant.deployment_mode}")
    print(f"  Dedicated URL: {upgraded_tenant.dedicated_instance_url}")
    print(f"  Is Dedicated: {routing.is_dedicated}")
    print(f"  Custom Models: {upgraded_tenant.custom_model_allowed}")
    print(f"  SSO Enabled: {upgraded_tenant.sso_enabled}")


# ========================================
# Scenario 4: Complete Integration
# ========================================
def integrated_example():
    """
    Show complete integration with Pathway app.

    This modifies the standard question_answering_rag template
    to support hybrid multi/single-tenant deployment.
    """
    print("\n=== Integrated Pathway App ===")

    # Determine deployment mode from environment
    deployment_mode = os.getenv("DEPLOYMENT_MODE", "multi_tenant")

    if deployment_mode == "single_tenant":
        config = DeploymentConfig(
            mode=DeploymentMode.SINGLE_TENANT,
            tenant_id=os.getenv("TENANT_ID", "default_tenant"),
            tenant_name=os.getenv("TENANT_NAME", "Default Org"),
        )
        print(f"Running in SINGLE-TENANT mode for: {config.tenant_id}")

    else:
        config = DeploymentConfig(
            mode=DeploymentMode.MULTI_TENANT,
            require_tenant_in_request=True,
            enforce_tenant_isolation=True
        )
        print(f"Running in MULTI-TENANT mode")

    # This config would be passed to your App class
    print(f"Config: {config.model_dump_json(indent=2)}")

    return config


# ========================================
# Main
# ========================================
if __name__ == "__main__":
    print("=" * 60)
    print("Hybrid Multi-Tenant / Single-Tenant Deployment Demo")
    print("=" * 60)

    # Run scenarios
    setup_multi_tenant_app()
    setup_single_tenant_app()
    demo_tenant_upgrade()
    integrated_example()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
