"""
FastAPI endpoints for connector management.

Endpoints:
- Create connector
- OAuth flow
- List/delete connectors
- Trigger sync
- View sync status
"""
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.auth_api import get_current_user
from auth.user_manager import User
from connectors.base_connector import ConnectorStatus, ConnectorType, SyncResult
from connectors.connector_manager import connector_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])


# ============================================================
# Request/Response Models
# ============================================================

class CreateConnectorRequest(BaseModel):
    """Request to create a new connector."""

    connector_type: ConnectorType = Field(description="Type of connector")
    settings: Dict = Field(
        description="Connector settings (client_id, client_secret, etc.)"
    )


class ConnectorResponse(BaseModel):
    """Connector information."""

    connector_id: str
    connector_type: ConnectorType
    tenant_id: str
    user_id: str
    status: ConnectorStatus
    sync_enabled: bool
    sync_interval_minutes: int
    last_sync_at: Optional[str] = None
    metadata: Optional[Dict] = None


class OAuthStartResponse(BaseModel):
    """OAuth flow start response."""

    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """OAuth callback data."""

    code: str
    state: str


class SyncResponse(BaseModel):
    """Sync operation result."""

    success: bool
    documents_synced: int
    documents_failed: int
    errors: List[str]
    started_at: str
    completed_at: str


class UpdateSyncSettingsRequest(BaseModel):
    """Update sync settings."""

    sync_enabled: Optional[bool] = None
    sync_interval_minutes: Optional[int] = None


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


# ============================================================
# Connector Management Endpoints
# ============================================================

@router.post("/", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    request: CreateConnectorRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new connector.

    This initializes the connector but doesn't authorize it yet.
    After creation, use the OAuth flow to authorize access.
    """
    try:
        config = connector_manager.create_connector(
            connector_type=request.connector_type,
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            settings=request.settings
        )

        return ConnectorResponse(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            tenant_id=config.tenant_id,
            user_id=config.user_id,
            status=config.status,
            sync_enabled=config.sync_enabled,
            sync_interval_minutes=config.sync_interval_minutes,
            last_sync_at=config.last_sync_at.isoformat() if config.last_sync_at else None
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[ConnectorResponse])
async def list_connectors(
    current_user: User = Depends(get_current_user)
):
    """
    List all connectors for the current user's tenant.
    """
    configs = connector_manager.list_connectors(
        tenant_id=current_user.tenant_id
    )

    return [
        ConnectorResponse(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            tenant_id=config.tenant_id,
            user_id=config.user_id,
            status=config.status,
            sync_enabled=config.sync_enabled,
            sync_interval_minutes=config.sync_interval_minutes,
            last_sync_at=config.last_sync_at.isoformat() if config.last_sync_at else None
        )
        for config in configs
    ]


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get connector details including metadata.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Get metadata
    metadata = None
    try:
        metadata = await connector_manager.get_connector_metadata(connector_id)
    except Exception as e:
        logger.warning(f"Could not get connector metadata: {e}")

    return ConnectorResponse(
        connector_id=config.connector_id,
        connector_type=config.connector_type,
        tenant_id=config.tenant_id,
        user_id=config.user_id,
        status=config.status,
        sync_enabled=config.sync_enabled,
        sync_interval_minutes=config.sync_interval_minutes,
        last_sync_at=config.last_sync_at.isoformat() if config.last_sync_at else None,
        metadata=metadata
    )


@router.delete("/{connector_id}", response_model=MessageResponse)
async def delete_connector(
    connector_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a connector.

    This will stop syncing and remove the connector configuration.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    success = connector_manager.delete_connector(connector_id)

    if success:
        return MessageResponse(message="Connector deleted successfully")
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete connector"
        )


@router.patch("/{connector_id}/sync-settings", response_model=ConnectorResponse)
async def update_sync_settings(
    connector_id: str,
    request: UpdateSyncSettingsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update connector sync settings.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    updated_config = connector_manager.update_sync_settings(
        connector_id=connector_id,
        sync_enabled=request.sync_enabled,
        sync_interval_minutes=request.sync_interval_minutes
    )

    return ConnectorResponse(
        connector_id=updated_config.connector_id,
        connector_type=updated_config.connector_type,
        tenant_id=updated_config.tenant_id,
        user_id=updated_config.user_id,
        status=updated_config.status,
        sync_enabled=updated_config.sync_enabled,
        sync_interval_minutes=updated_config.sync_interval_minutes,
        last_sync_at=updated_config.last_sync_at.isoformat() if updated_config.last_sync_at else None
    )


# ============================================================
# OAuth Flow Endpoints
# ============================================================

@router.post("/{connector_id}/oauth/start")
async def start_oauth(
    connector_id: str,
    redirect_uri: str = Query(..., description="OAuth redirect URI"),
    current_user: User = Depends(get_current_user)
):
    """
    Start OAuth authorization flow.

    Returns the authorization URL to redirect the user to.
    After authorization, the OAuth provider will redirect back to redirect_uri.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        oauth_url = await connector_manager.start_oauth_flow(
            connector_id=connector_id,
            redirect_uri=redirect_uri
        )

        # Extract state from URL
        state = oauth_url.split("state=")[1].split("&")[0] if "state=" in oauth_url else ""

        return OAuthStartResponse(
            authorization_url=oauth_url,
            state=state
        )

    except Exception as e:
        logger.error(f"Error starting OAuth flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{connector_id}/oauth/callback", response_model=ConnectorResponse)
async def oauth_callback(
    connector_id: str,
    request: OAuthCallbackRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Complete OAuth flow with authorization code.

    This endpoint should be called after the user authorizes the app
    and is redirected back with the authorization code.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        updated_config = await connector_manager.complete_oauth_flow(
            code=request.code,
            state=request.state
        )

        return ConnectorResponse(
            connector_id=updated_config.connector_id,
            connector_type=updated_config.connector_type,
            tenant_id=updated_config.tenant_id,
            user_id=updated_config.user_id,
            status=updated_config.status,
            sync_enabled=updated_config.sync_enabled,
            sync_interval_minutes=updated_config.sync_interval_minutes,
            last_sync_at=updated_config.last_sync_at.isoformat() if updated_config.last_sync_at else None
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error completing OAuth flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================
# Sync Endpoints
# ============================================================

@router.post("/{connector_id}/sync", response_model=SyncResponse)
async def sync_connector(
    connector_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger connector sync.

    This will fetch all new/updated documents from the external service
    and index them for search.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        result = await connector_manager.sync_connector(connector_id)

        return SyncResponse(
            success=result.success,
            documents_synced=result.documents_synced,
            documents_failed=result.documents_failed,
            errors=result.errors,
            started_at=result.started_at.isoformat(),
            completed_at=result.completed_at.isoformat()
        )

    except Exception as e:
        logger.error(f"Error syncing connector: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/sync-all", response_model=Dict[str, SyncResponse])
async def sync_all_connectors(
    current_user: User = Depends(get_current_user)
):
    """
    Sync all active connectors for the current tenant.
    """
    try:
        results = await connector_manager.sync_all_connectors(
            tenant_id=current_user.tenant_id
        )

        return {
            connector_id: SyncResponse(
                success=result.success,
                documents_synced=result.documents_synced,
                documents_failed=result.documents_failed,
                errors=result.errors,
                started_at=result.started_at.isoformat(),
                completed_at=result.completed_at.isoformat()
            )
            for connector_id, result in results.items()
        }

    except Exception as e:
        logger.error(f"Error syncing all connectors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{connector_id}/test")
async def test_connection(
    connector_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Test connector connection.

    Verifies that the connector can successfully connect to the external service.
    """
    config = connector_manager.get_config(connector_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check permission
    if config.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        success = await connector_manager.test_connector(connector_id)

        return {
            "success": success,
            "message": "Connection successful" if success else "Connection failed"
        }

    except Exception as e:
        logger.error(f"Error testing connector: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
