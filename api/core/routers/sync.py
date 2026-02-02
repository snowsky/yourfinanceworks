from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
import httpx
import os
from datetime import datetime, timezone

from core.models.database import get_db, get_master_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.rbac import require_admin
from core.services.sync_service import SyncService
from core.utils.auth_utils import get_current_sync_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

class SyncRequest(httpx.Request):
    pass # Simple wrapper if needed

@router.get("/status")
async def get_sync_status(
    remote_url: Optional[str] = Query(None),
    remote_api_key: Optional[str] = Query(None),
    current_user: MasterUser = Depends(get_current_sync_auth),
    db: Session = Depends(get_db)
):
    """
    Get the sync status of the current instance.
    If remote_url is provided, it compares the local fingerprint with the remote one.
    """
    require_admin(current_user, "view sync status")

    local_fingerprint = SyncService.get_data_fingerprint(db)
    storage_identity = SyncService.get_storage_identity()

    status = {
        "local_fingerprint": local_fingerprint,
        "storage_identity": storage_identity,
        "is_in_sync": None,
        "remote_status": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if remote_url and remote_api_key:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{remote_url.rstrip('/')}/api/v1/sync/status",
                    headers={"Authorization": f"Bearer {remote_api_key}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    remote_data = response.json()
                    status["remote_fingerprint"] = remote_data.get("local_fingerprint")
                    status["remote_storage_identity"] = remote_data.get("storage_identity")
                    status["is_in_sync"] = (local_fingerprint == status["remote_fingerprint"])
                    status["remote_status"] = "reachable"
                    # Auto-suggest skipping attachments if storage identities match
                    status["suggest_skip_attachments"] = (storage_identity == status["remote_storage_identity"])
                elif response.status_code == 401:
                    detail = response.json().get("detail", "")
                    if "Invalid or expired token" in str(detail):
                        raise HTTPException(
                            status_code=400,
                            detail="Remote instance rejected the API key. Please ensure the remote instance is updated to the latest version supporting flexible sync authentication and the key is active."
                        )
                    raise HTTPException(status_code=400, detail=f"Remote authentication failed: {detail}")
                else:
                    remote_detail = response.text
                    try:
                        remote_detail = response.json().get("detail", response.text)
                    except:
                        pass
                    raise HTTPException(
                        status_code=400,
                        detail=f"Remote instance returned error ({response.status_code}): {remote_detail}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to check remote sync status: {e}")
            status["remote_status"] = f"unreachable: {str(e)}"

    return status

@router.post("/push")
async def push_data(
    remote_url: str = Query(...),
    remote_api_key: str = Query(...),
    include_attachments: bool = Query(True),
    current_user: MasterUser = Depends(get_current_sync_auth),
    db: Session = Depends(get_db)
):
    """
    Push local data to a remote instance.
    """
    require_admin(current_user, "perform sync push")

    try:
        # 1. Backend Guard: Check if remote storage is identical to local
        actual_include_attachments = include_attachments
        if include_attachments:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{remote_url.rstrip('/')}/api/v1/sync/status",
                        headers={"Authorization": f"Bearer {remote_api_key}"},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        remote_data = response.json()
                        local_storage = SyncService.get_storage_identity()
                        remote_storage = remote_data.get("storage_identity")
                        if local_storage == remote_storage:
                            logger.info("Shared cloud storage detected during push. Skipping attachment transfer.")
                            actual_include_attachments = False
            except Exception as e:
                logger.warning(f"Failed to verify remote storage identity before push: {e}. Proceeding with original settings.")

        # 2. Package local data
        package_bytes = SyncService.package_data(db, current_user.tenant_id, include_attachments=actual_include_attachments)

        # 3. Send to remote
        async with httpx.AsyncClient() as client:
            files = {'file': ('sync_package.zip', package_bytes, 'application/zip')}
            response = await client.post(
                f"{remote_url.rstrip('/')}/api/v1/sync/import",
                headers={"Authorization": f"Bearer {remote_api_key}"},
                files=files,
                params={"include_attachments": actual_include_attachments},
                timeout=300.0 # Long timeout for large packages
            )

            if response.status_code == 200:
                return {"message": "Data pushed successfully", "remote_response": response.json()}
            elif response.status_code == 401:
                detail = response.json().get("detail", "")
                if "Invalid or expired token" in str(detail):
                    raise HTTPException(
                        status_code=400,
                        detail="Remote instance rejected the API key. Please ensure the remote instance is updated to the latest version supporting flexible sync authentication."
                    )
                raise HTTPException(status_code=400, detail=f"Remote authentication failed: {detail}")
            else:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Remote instance returned error ({response.status_code}): {response.text}"
                )

    except Exception as e:
        logger.error(f"Sync push failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync push failed: {str(e)}")

@router.post("/pull")
async def pull_data(
    remote_url: str = Query(...),
    remote_api_key: str = Query(...),
    include_attachments: bool = Query(True),
    current_user: MasterUser = Depends(get_current_sync_auth),
    db: Session = Depends(get_db)
):
    """
    Pull data from a remote instance to the local instance.
    """
    require_admin(current_user, "perform sync pull")

    try:
        # 1. Backend Guard: Check if remote storage is identical to local
        actual_include_attachments = include_attachments
        if include_attachments:
            try:
                async with httpx.AsyncClient() as client:
                    status_response = await client.get(
                        f"{remote_url.rstrip('/')}/api/v1/sync/status",
                        headers={"Authorization": f"Bearer {remote_api_key}"},
                        timeout=10.0
                    )
                    if status_response.status_code == 200:
                        remote_data = status_response.json()
                        local_storage = SyncService.get_storage_identity()
                        remote_storage = remote_data.get("storage_identity")
                        if local_storage == remote_storage:
                            logger.info("Shared cloud storage detected during pull. Skipping attachment transfer.")
                            actual_include_attachments = False
            except Exception as e:
                logger.warning(f"Failed to verify remote storage identity before pull: {e}. Proceeding with original settings.")

        # 2. Request package from remote
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{remote_url.rstrip('/')}/api/v1/sync/export",
                headers={"Authorization": f"Bearer {remote_api_key}"},
                params={"include_attachments": actual_include_attachments},
                timeout=300.0
            )

            if response.status_code == 200:
                package_bytes = response.content
                # 3. Apply locally
                SyncService.apply_package(package_bytes, current_user.tenant_id)
                return {"message": "Data pulled and applied successfully"}
            elif response.status_code == 401:
                detail = response.json().get("detail", "")
                if "Invalid or expired token" in str(detail):
                    raise HTTPException(
                        status_code=400,
                        detail="Remote instance rejected the API key. Please ensure the remote instance is updated to the latest version supporting flexible sync authentication."
                    )
                raise HTTPException(status_code=400, detail=f"Remote authentication failed: {detail}")
            else:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Remote instance returned error ({response.status_code}): {response.text}"
                )

    except Exception as e:
        logger.error(f"Sync pull failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync pull failed: {str(e)}")

@router.post("/export")
async def export_sync_package(
    include_attachments: bool = Query(True),
    current_user: MasterUser = Depends(get_current_sync_auth),
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to export data for a pull request.
    """
    require_admin(current_user, "export sync data")

    try:
        package_bytes = SyncService.package_data(db, current_user.tenant_id, include_attachments=include_attachments)
        return Response(
            content=package_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=sync_package.zip"}
        )
    except Exception as e:
        logger.error(f"Export sync package failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_sync_package(
    file: UploadFile = File(...),
    current_user: MasterUser = Depends(get_current_sync_auth),
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to receive and apply a sync package.
    """
    require_admin(current_user, "import sync data")

    try:
        package_bytes = await file.read()
        SyncService.apply_package(package_bytes, current_user.tenant_id)
        return {"message": "Sync package applied successfully"}
    except Exception as e:
        logger.error(f"Import sync package failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
