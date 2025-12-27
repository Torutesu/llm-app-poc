"""
Base connector interface for external service integrations.

All connectors (Slack, Google Drive, Notion, etc.) implement this interface.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConnectorType(str, Enum):
    """Supported connector types."""

    SLACK = "slack"
    GOOGLE_DRIVE = "google_drive"
    NOTION = "notion"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    GITHUB = "github"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    SHAREPOINT = "sharepoint"
    GMAIL = "gmail"


class ConnectorStatus(str, Enum):
    """Connector status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"
    SETUP = "setup"


class Document(BaseModel):
    """Unified document model from any connector."""

    # Identity
    id: str = Field(description="Unique document ID")
    connector_type: ConnectorType = Field(description="Source connector")
    external_id: str = Field(description="ID in external system")

    # Content
    title: str = Field(description="Document title")
    content: str = Field(description="Document content/body")
    url: Optional[str] = Field(default=None, description="Link to original document")

    # Metadata
    author: Optional[str] = Field(default=None, description="Document author")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    # Access Control
    tenant_id: str = Field(description="Tenant/organization ID")
    permissions: List[str] = Field(default_factory=list, description="Who can access")

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Connector-specific metadata")


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    documents_synced: int
    documents_failed: int
    errors: List[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime


class ConnectorConfig(BaseModel):
    """Base configuration for a connector."""

    connector_id: str = Field(description="Unique connector instance ID")
    connector_type: ConnectorType
    tenant_id: str = Field(description="Tenant this connector belongs to")
    user_id: str = Field(description="User who set up the connector")

    # OAuth credentials
    access_token: Optional[str] = Field(default=None, description="OAuth access token")
    refresh_token: Optional[str] = Field(default=None, description="OAuth refresh token")
    token_expires_at: Optional[datetime] = Field(default=None, description="Token expiration")

    # Sync settings
    sync_enabled: bool = Field(default=True)
    sync_interval_minutes: int = Field(default=60, description="How often to sync")
    last_sync_at: Optional[datetime] = Field(default=None)

    # Status
    status: ConnectorStatus = Field(default=ConnectorStatus.SETUP)

    # Connector-specific settings
    settings: Dict[str, Any] = Field(default_factory=dict, description="Connector-specific settings")


class BaseConnector(ABC):
    """
    Base class for all connectors.

    Each connector implements methods to:
    1. Authenticate with OAuth
    2. Fetch documents
    3. Sync data to vector store
    """

    def __init__(self, config: ConnectorConfig):
        """
        Initialize connector.

        Args:
            config: Connector configuration
        """
        self.config = config

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if connector can connect to external service.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """
        Get OAuth authorization URL.

        Args:
            redirect_uri: Where to redirect after auth
            state: CSRF protection state parameter

        Returns:
            OAuth authorization URL
        """
        pass

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange OAuth code for access token.

        Args:
            code: Authorization code
            redirect_uri: Same redirect URI used in authorization

        Returns:
            Token response with access_token, refresh_token, etc.
        """
        pass

    @abstractmethod
    async def refresh_access_token(self) -> bool:
        """
        Refresh the access token using refresh token.

        Returns:
            True if refresh successful
        """
        pass

    @abstractmethod
    async def fetch_documents(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Document]:
        """
        Fetch documents from external service.

        Args:
            since: Only fetch documents updated after this time
            limit: Maximum number of documents to fetch

        Returns:
            List of documents
        """
        pass

    @abstractmethod
    async def sync(self) -> SyncResult:
        """
        Sync all data from external service to local index.

        Returns:
            Sync result with statistics
        """
        pass

    async def get_metadata(self) -> Dict[str, Any]:
        """
        Get connector metadata (workspace name, user info, etc.).

        Returns:
            Connector metadata
        """
        return {
            "connector_type": self.config.connector_type,
            "status": self.config.status,
            "last_sync": self.config.last_sync_at
        }
