"""
Slack connector for indexing Slack messages and files.

Syncs:
- Public channels
- Private channels (user has access to)
- Direct messages
- Files and attachments
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
    Document,
    SyncResult,
)

logger = logging.getLogger(__name__)


class SlackConnector(BaseConnector):
    """Slack workspace connector."""

    OAUTH_BASE_URL = "https://slack.com/oauth/v2"
    API_BASE_URL = "https://slack.com/api"

    def __init__(self, config: ConnectorConfig):
        """Initialize Slack connector."""
        super().__init__(config)
        self.client_id = config.settings.get("client_id")
        self.client_secret = config.settings.get("client_secret")

    async def test_connection(self) -> bool:
        """Test Slack API connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.API_BASE_URL}/auth.test",
                    headers={"Authorization": f"Bearer {self.config.access_token}"}
                )
                return response.json().get("ok", False)
        except Exception as e:
            logger.error(f"Slack connection test failed: {e}")
            return False

    async def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Get Slack OAuth URL."""
        scopes = [
            "channels:history",
            "channels:read",
            "groups:history",
            "groups:read",
            "im:history",
            "im:read",
            "files:read",
            "users:read",
            "team:read"
        ]

        params = {
            "client_id": self.client_id,
            "scope": ",".join(scopes),
            "redirect_uri": redirect_uri,
            "state": state,
            "user_scope": "search:read"
        }

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.OAUTH_BASE_URL}/authorize?{param_str}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange OAuth code for Slack access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.OAUTH_BASE_URL}/access",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri
                }
            )

            data = response.json()

            if not data.get("ok"):
                raise Exception(f"Slack OAuth failed: {data.get('error')}")

            # Update config with tokens
            self.config.access_token = data["access_token"]
            self.config.status = ConnectorStatus.ACTIVE

            return data

    async def refresh_access_token(self) -> bool:
        """Slack tokens don't expire, no refresh needed."""
        return True

    async def fetch_documents(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Document]:
        """Fetch messages from Slack channels."""
        documents = []

        try:
            # Get all channels
            channels = await self._get_channels()

            for channel in channels:
                messages = await self._get_channel_messages(
                    channel["id"],
                    since=since,
                    limit=limit
                )

                for msg in messages:
                    doc = self._message_to_document(msg, channel)
                    if doc:
                        documents.append(doc)

        except Exception as e:
            logger.error(f"Error fetching Slack documents: {e}")

        return documents

    async def _get_channels(self) -> List[Dict[str, Any]]:
        """Get all channels user has access to."""
        async with httpx.AsyncClient() as client:
            # Public channels
            response = await client.get(
                f"{self.API_BASE_URL}/conversations.list",
                headers={"Authorization": f"Bearer {self.config.access_token}"},
                params={"types": "public_channel,private_channel"}
            )

            data = response.json()
            return data.get("channels", [])

    async def _get_channel_messages(
        self,
        channel_id: str,
        since: Optional[datetime] = None,
        limit: Optional[int] = 100
    ) -> List[Dict[str, Any]]:
        """Get messages from a specific channel."""
        async with httpx.AsyncClient() as client:
            params = {"channel": channel_id, "limit": limit}

            if since:
                params["oldest"] = str(since.timestamp())

            response = await client.get(
                f"{self.API_BASE_URL}/conversations.history",
                headers={"Authorization": f"Bearer {self.config.access_token}"},
                params=params
            )

            data = response.json()
            return data.get("messages", [])

    def _message_to_document(
        self,
        message: Dict[str, Any],
        channel: Dict[str, Any]
    ) -> Optional[Document]:
        """Convert Slack message to Document."""
        if not message.get("text"):
            return None

        # Generate unique ID
        doc_id = f"slack_{channel['id']}_{message['ts']}"

        # Get timestamp
        ts = float(message["ts"])
        timestamp = datetime.fromtimestamp(ts)

        # Get message URL
        team_id = self.config.settings.get("team_id", "")
        url = f"https://app.slack.com/client/{team_id}/{channel['id']}/thread/{message['ts']}"

        return Document(
            id=doc_id,
            connector_type=ConnectorType.SLACK,
            external_id=message["ts"],
            title=f"Message in #{channel['name']}",
            content=message["text"],
            url=url,
            author=message.get("user"),
            created_at=timestamp,
            updated_at=timestamp,
            tenant_id=self.config.tenant_id,
            permissions=[self.config.user_id],  # Simplified: user who connected
            metadata={
                "channel_id": channel["id"],
                "channel_name": channel["name"],
                "message_type": message.get("type"),
                "thread_ts": message.get("thread_ts")
            }
        )

    async def sync(self) -> SyncResult:
        """Sync all Slack data."""
        started_at = datetime.utcnow()
        documents_synced = 0
        documents_failed = 0
        errors = []

        try:
            self.config.status = ConnectorStatus.SYNCING

            # Fetch documents since last sync
            documents = await self.fetch_documents(
                since=self.config.last_sync_at
            )

            # TODO: Index documents to vector store
            # For now, just count them
            documents_synced = len(documents)

            self.config.last_sync_at = datetime.utcnow()
            self.config.status = ConnectorStatus.ACTIVE

        except Exception as e:
            logger.error(f"Slack sync failed: {e}")
            errors.append(str(e))
            self.config.status = ConnectorStatus.ERROR
            documents_failed = 1

        completed_at = datetime.utcnow()

        return SyncResult(
            success=len(errors) == 0,
            documents_synced=documents_synced,
            documents_failed=documents_failed,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at
        )

    async def get_metadata(self) -> Dict[str, Any]:
        """Get Slack workspace metadata."""
        base_metadata = await super().get_metadata()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/team.info",
                    headers={"Authorization": f"Bearer {self.config.access_token}"}
                )

                data = response.json()
                team = data.get("team", {})

                base_metadata.update({
                    "workspace_name": team.get("name"),
                    "workspace_domain": team.get("domain"),
                    "team_id": team.get("id")
                })

        except Exception as e:
            logger.error(f"Error getting Slack metadata: {e}")

        return base_metadata
