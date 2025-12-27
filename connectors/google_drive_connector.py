"""
Google Drive connector for indexing documents and files.

Syncs:
- Google Docs
- Google Sheets
- Google Slides
- PDFs and other files
- Shared drives
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


class GoogleDriveConnector(BaseConnector):
    """Google Drive connector."""

    OAUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2"
    API_BASE_URL = "https://www.googleapis.com/drive/v3"
    EXPORT_BASE_URL = "https://www.googleapis.com/drive/v3/files"

    # MIME types for Google Workspace files
    GOOGLE_MIME_TYPES = {
        "application/vnd.google-apps.document": "text/plain",  # Docs → Plain text
        "application/vnd.google-apps.spreadsheet": "text/csv",  # Sheets → CSV
        "application/vnd.google-apps.presentation": "text/plain",  # Slides → Plain text
    }

    def __init__(self, config: ConnectorConfig):
        """Initialize Google Drive connector."""
        super().__init__(config)
        self.client_id = config.settings.get("client_id")
        self.client_secret = config.settings.get("client_secret")

    async def test_connection(self) -> bool:
        """Test Google Drive API connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/about",
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                    params={"fields": "user"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Google Drive connection test failed: {e}")
            return False

    async def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Get Google OAuth URL."""
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly"
        ]

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",  # Get refresh token
            "prompt": "consent"
        }

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.OAUTH_BASE_URL}/auth?{param_str}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange OAuth code for Google access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
            )

            data = response.json()

            if "error" in data:
                raise Exception(f"Google OAuth failed: {data['error']}")

            # Update config with tokens
            self.config.access_token = data["access_token"]
            self.config.refresh_token = data.get("refresh_token")

            if "expires_in" in data:
                expires_in = data["expires_in"]
                self.config.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            self.config.status = ConnectorStatus.ACTIVE

            return data

    async def refresh_access_token(self) -> bool:
        """Refresh Google access token."""
        if not self.config.refresh_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.config.refresh_token,
                        "grant_type": "refresh_token"
                    }
                )

                data = response.json()

                if "error" in data:
                    logger.error(f"Token refresh failed: {data['error']}")
                    return False

                self.config.access_token = data["access_token"]

                if "expires_in" in data:
                    from datetime import timedelta
                    expires_in = data["expires_in"]
                    self.config.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                return True

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    async def fetch_documents(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Document]:
        """Fetch files from Google Drive."""
        documents = []

        try:
            # Build query
            query_parts = ["trashed = false"]

            if since:
                query_parts.append(f"modifiedTime > '{since.isoformat()}'")

            query = " and ".join(query_parts)

            # Get files
            files = await self._list_files(query, limit)

            for file in files:
                doc = await self._file_to_document(file)
                if doc:
                    documents.append(doc)

        except Exception as e:
            logger.error(f"Error fetching Google Drive documents: {e}")

        return documents

    async def _list_files(
        self,
        query: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List files from Google Drive."""
        files = []
        page_token = None

        async with httpx.AsyncClient() as client:
            while True:
                params = {
                    "q": query,
                    "fields": "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, owners, webViewLink, size)",
                    "pageSize": min(limit or 100, 1000)
                }

                if page_token:
                    params["pageToken"] = page_token

                response = await client.get(
                    f"{self.API_BASE_URL}/files",
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                    params=params
                )

                data = response.json()
                files.extend(data.get("files", []))

                page_token = data.get("nextPageToken")

                if not page_token or (limit and len(files) >= limit):
                    break

        return files[:limit] if limit else files

    async def _file_to_document(self, file: Dict[str, Any]) -> Optional[Document]:
        """Convert Google Drive file to Document."""
        mime_type = file.get("mimeType")

        # Extract content
        content = ""

        if mime_type in self.GOOGLE_MIME_TYPES:
            # Google Workspace file - export as text
            content = await self._export_google_file(file["id"], mime_type)
        elif mime_type == "application/pdf":
            # TODO: Extract PDF text
            content = f"[PDF file: {file['name']}]"
        elif mime_type.startswith("text/"):
            # Plain text file
            content = await self._download_file_content(file["id"])
        else:
            # Other file types - just metadata
            content = f"[File: {file['name']}]"

        if not content:
            return None

        # Generate unique ID
        doc_id = f"gdrive_{file['id']}"

        # Parse timestamps
        created_at = datetime.fromisoformat(file["createdTime"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00"))

        # Get owner
        owners = file.get("owners", [])
        author = owners[0].get("displayName") if owners else None

        return Document(
            id=doc_id,
            connector_type=ConnectorType.GOOGLE_DRIVE,
            external_id=file["id"],
            title=file["name"],
            content=content[:100000],  # Limit content size
            url=file.get("webViewLink"),
            author=author,
            created_at=created_at,
            updated_at=updated_at,
            tenant_id=self.config.tenant_id,
            permissions=[self.config.user_id],
            metadata={
                "mime_type": mime_type,
                "size": file.get("size"),
                "owners": [o.get("emailAddress") for o in owners]
            }
        )

    async def _export_google_file(self, file_id: str, mime_type: str) -> str:
        """Export Google Workspace file as text."""
        export_mime_type = self.GOOGLE_MIME_TYPES.get(mime_type)

        if not export_mime_type:
            return ""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.EXPORT_BASE_URL}/{file_id}/export",
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                    params={"mimeType": export_mime_type}
                )

                if response.status_code == 200:
                    return response.text

        except Exception as e:
            logger.error(f"Error exporting file {file_id}: {e}")

        return ""

    async def _download_file_content(self, file_id: str) -> str:
        """Download file content."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.EXPORT_BASE_URL}/{file_id}",
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                    params={"alt": "media"}
                )

                if response.status_code == 200:
                    return response.text

        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")

        return ""

    async def sync(self) -> SyncResult:
        """Sync all Google Drive data."""
        started_at = datetime.utcnow()
        documents_synced = 0
        documents_failed = 0
        errors = []

        try:
            self.config.status = ConnectorStatus.SYNCING

            # Check if token needs refresh
            if self.config.token_expires_at and datetime.utcnow() >= self.config.token_expires_at:
                if not await self.refresh_access_token():
                    raise Exception("Failed to refresh access token")

            # Fetch documents since last sync
            documents = await self.fetch_documents(
                since=self.config.last_sync_at
            )

            # TODO: Index documents to vector store
            documents_synced = len(documents)

            self.config.last_sync_at = datetime.utcnow()
            self.config.status = ConnectorStatus.ACTIVE

        except Exception as e:
            logger.error(f"Google Drive sync failed: {e}")
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
        """Get Google Drive metadata."""
        base_metadata = await super().get_metadata()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/about",
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                    params={"fields": "user,storageQuota"}
                )

                data = response.json()
                user = data.get("user", {})
                quota = data.get("storageQuota", {})

                base_metadata.update({
                    "user_email": user.get("emailAddress"),
                    "user_name": user.get("displayName"),
                    "storage_used": quota.get("usage"),
                    "storage_limit": quota.get("limit")
                })

        except Exception as e:
            logger.error(f"Error getting Google Drive metadata: {e}")

        return base_metadata
