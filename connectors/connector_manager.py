"""
Connector manager for handling all external service integrations.

Manages:
- Connector lifecycle (create, update, delete)
- OAuth flows
- Sync scheduling
- Connector registry
"""
import logging
import secrets
from datetime import datetime
from typing import Dict, List, Optional

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
    SyncResult,
)
from connectors.google_drive_connector import GoogleDriveConnector
from connectors.slack_connector import SlackConnector

logger = logging.getLogger(__name__)


class ConnectorManager:
    """Manage all connectors for a tenant."""

    # Connector type to class mapping
    CONNECTOR_CLASSES = {
        ConnectorType.SLACK: SlackConnector,
        ConnectorType.GOOGLE_DRIVE: GoogleDriveConnector,
        # Add more connectors here
    }

    def __init__(self):
        """Initialize connector manager."""
        self._connectors: Dict[str, BaseConnector] = {}
        self._configs: Dict[str, ConnectorConfig] = {}
        self._oauth_states: Dict[str, Dict] = {}  # CSRF protection

    def create_connector(
        self,
        connector_type: ConnectorType,
        tenant_id: str,
        user_id: str,
        settings: Dict
    ) -> ConnectorConfig:
        """
        Create a new connector instance.

        Args:
            connector_type: Type of connector to create
            tenant_id: Tenant ID
            user_id: User who's creating the connector
            settings: Connector-specific settings (client_id, etc.)

        Returns:
            Connector configuration

        Raises:
            ValueError: If connector type not supported
        """
        if connector_type not in self.CONNECTOR_CLASSES:
            raise ValueError(f"Unsupported connector type: {connector_type}")

        # Generate unique connector ID
        connector_id = f"{connector_type}_{tenant_id}_{secrets.token_hex(8)}"

        # Create config
        config = ConnectorConfig(
            connector_id=connector_id,
            connector_type=connector_type,
            tenant_id=tenant_id,
            user_id=user_id,
            status=ConnectorStatus.SETUP,
            settings=settings
        )

        # Store config
        self._configs[connector_id] = config

        # Instantiate connector
        connector_class = self.CONNECTOR_CLASSES[connector_type]
        connector = connector_class(config)
        self._connectors[connector_id] = connector

        logger.info(f"Created connector: {connector_id} for tenant {tenant_id}")

        return config

    def get_connector(self, connector_id: str) -> Optional[BaseConnector]:
        """Get connector instance by ID."""
        return self._connectors.get(connector_id)

    def get_config(self, connector_id: str) -> Optional[ConnectorConfig]:
        """Get connector config by ID."""
        return self._configs.get(connector_id)

    def list_connectors(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[ConnectorConfig]:
        """
        List all connectors.

        Args:
            tenant_id: Filter by tenant
            user_id: Filter by user

        Returns:
            List of connector configs
        """
        configs = list(self._configs.values())

        if tenant_id:
            configs = [c for c in configs if c.tenant_id == tenant_id]

        if user_id:
            configs = [c for c in configs if c.user_id == user_id]

        return configs

    def delete_connector(self, connector_id: str) -> bool:
        """
        Delete a connector.

        Args:
            connector_id: Connector to delete

        Returns:
            True if deleted successfully
        """
        if connector_id in self._connectors:
            del self._connectors[connector_id]
            del self._configs[connector_id]
            logger.info(f"Deleted connector: {connector_id}")
            return True

        return False

    async def start_oauth_flow(
        self,
        connector_id: str,
        redirect_uri: str
    ) -> str:
        """
        Start OAuth authorization flow.

        Args:
            connector_id: Connector to authorize
            redirect_uri: Where to redirect after auth

        Returns:
            OAuth authorization URL

        Raises:
            ValueError: If connector not found
        """
        connector = self.get_connector(connector_id)
        if not connector:
            raise ValueError(f"Connector not found: {connector_id}")

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state with connector info
        self._oauth_states[state] = {
            "connector_id": connector_id,
            "redirect_uri": redirect_uri,
            "created_at": datetime.utcnow()
        }

        # Get OAuth URL from connector
        oauth_url = await connector.get_oauth_url(redirect_uri, state)

        return oauth_url

    async def complete_oauth_flow(
        self,
        code: str,
        state: str
    ) -> ConnectorConfig:
        """
        Complete OAuth flow with authorization code.

        Args:
            code: Authorization code from OAuth provider
            state: State parameter for CSRF protection

        Returns:
            Updated connector config

        Raises:
            ValueError: If state invalid or connector not found
        """
        # Validate state
        if state not in self._oauth_states:
            raise ValueError("Invalid OAuth state")

        oauth_info = self._oauth_states.pop(state)
        connector_id = oauth_info["connector_id"]
        redirect_uri = oauth_info["redirect_uri"]

        # Get connector
        connector = self.get_connector(connector_id)
        if not connector:
            raise ValueError(f"Connector not found: {connector_id}")

        # Exchange code for token
        token_data = await connector.exchange_code(code, redirect_uri)

        logger.info(f"Completed OAuth for connector: {connector_id}")

        return connector.config

    async def test_connector(self, connector_id: str) -> bool:
        """
        Test connector connection.

        Args:
            connector_id: Connector to test

        Returns:
            True if connection successful
        """
        connector = self.get_connector(connector_id)
        if not connector:
            return False

        return await connector.test_connection()

    async def sync_connector(self, connector_id: str) -> SyncResult:
        """
        Manually trigger connector sync.

        Args:
            connector_id: Connector to sync

        Returns:
            Sync result

        Raises:
            ValueError: If connector not found
        """
        connector = self.get_connector(connector_id)
        if not connector:
            raise ValueError(f"Connector not found: {connector_id}")

        logger.info(f"Starting manual sync for connector: {connector_id}")

        result = await connector.sync()

        logger.info(
            f"Sync completed for {connector_id}: "
            f"{result.documents_synced} synced, {result.documents_failed} failed"
        )

        return result

    async def sync_all_connectors(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict[str, SyncResult]:
        """
        Sync all active connectors.

        Args:
            tenant_id: Only sync connectors for this tenant

        Returns:
            Dict of connector_id to sync result
        """
        results = {}

        configs = self.list_connectors(tenant_id=tenant_id)

        for config in configs:
            if config.status != ConnectorStatus.ACTIVE or not config.sync_enabled:
                continue

            try:
                result = await self.sync_connector(config.connector_id)
                results[config.connector_id] = result
            except Exception as e:
                logger.error(f"Error syncing connector {config.connector_id}: {e}")

        return results

    async def get_connector_metadata(self, connector_id: str) -> Dict:
        """
        Get connector metadata (workspace name, etc.).

        Args:
            connector_id: Connector ID

        Returns:
            Connector metadata
        """
        connector = self.get_connector(connector_id)
        if not connector:
            raise ValueError(f"Connector not found: {connector_id}")

        return await connector.get_metadata()

    def update_sync_settings(
        self,
        connector_id: str,
        sync_enabled: Optional[bool] = None,
        sync_interval_minutes: Optional[int] = None
    ) -> ConnectorConfig:
        """
        Update connector sync settings.

        Args:
            connector_id: Connector to update
            sync_enabled: Enable/disable sync
            sync_interval_minutes: Sync interval

        Returns:
            Updated config

        Raises:
            ValueError: If connector not found
        """
        config = self.get_config(connector_id)
        if not config:
            raise ValueError(f"Connector not found: {connector_id}")

        if sync_enabled is not None:
            config.sync_enabled = sync_enabled

        if sync_interval_minutes is not None:
            config.sync_interval_minutes = sync_interval_minutes

        logger.info(f"Updated sync settings for connector: {connector_id}")

        return config


# Global connector manager instance
connector_manager = ConnectorManager()
