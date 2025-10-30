"""
Cloud Storage Management API Router

Provides endpoints for:
- Cloud storage configuration management
- Migration management for administrators
- Storage monitoring and health checks
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

from models.database import get_db
from models.models import MasterUser
from routers.auth import get_current_user
from utils.rbac import require_admin
from services.cloud_storage_service import CloudStorageService
from services.attachment_migration_service import AttachmentMigrationService
from services.storage_monitoring_service import StorageMonitoringService
from storage_config.cloud_storage_config import get_cloud_storage_config, CloudStorageConfig
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cloud-storage", tags=["cloud-storage"])


# Pydantic models for request/response
class StorageConfigurationResponse(BaseModel):
    provider: str
    enabled: bool
    is_primary: bool
    health_status: str
    last_health_check: Optional[str] = None


class MigrationStatusResponse(BaseModel):
    tenant_id: str
    status: str
    total_files: int
    migrated_files: int
    failed_files: int
    skipped_files: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class StorageHealthResponse(BaseModel):
    provider: str
    status: str
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    last_check: str


class StorageUsageResponse(BaseModel):
    tenant_id: str
    total_files: int
    total_size_bytes: int
    by_provider: Dict[str, Dict[str, Any]]
    by_type: Dict[str, Dict[str, Any]]


# Storage Configuration Endpoints
@router.get("/configuration", response_model=List[StorageConfigurationResponse])
async def get_storage_configuration(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get current cloud storage configuration and health status.
    Requires admin privileges.
    """
    require_admin(current_user, "view storage configuration")
    
    try:
        # Initialize cloud storage service
        cloud_config = get_cloud_storage_config()
        cloud_storage_service = CloudStorageService(db, cloud_config)
        
        # Get provider configurations
        provider_configs = cloud_storage_service.provider_factory.get_provider_configs()
        
        configurations = []
        for provider_type, config in provider_configs.items():
            # Get health status
            try:
                is_healthy = cloud_storage_service._is_provider_healthy(provider_type)
                health_status = "healthy" if is_healthy else "unhealthy"
            except Exception as e:
                health_status = f"error: {str(e)}"
            
            configurations.append(StorageConfigurationResponse(
                provider=provider_type.value,
                enabled=config.get('enabled', True),
                is_primary=provider_type == cloud_storage_service.provider_factory.get_primary_provider_type(),
                health_status=health_status,
                last_health_check=datetime.now(timezone.utc).isoformat()
            ))
        
        return configurations
        
    except Exception as e:
        logger.error(f"Failed to get storage configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage configuration: {str(e)}"
        )


@router.post("/configuration/test")
async def test_storage_configuration(
    provider: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Test connectivity to a specific storage provider.
    Requires admin privileges.
    """
    require_admin(current_user, "test storage configuration")
    
    try:
        # Initialize cloud storage service
        cloud_config = get_cloud_storage_config()
        cloud_storage_service = CloudStorageService(db, cloud_config)
        
        # Get the specific provider
        from services.cloud_storage.provider import StorageProvider
        try:
            provider_type = StorageProvider(provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}"
            )
        
        provider_instance = cloud_storage_service.provider_factory.get_provider(provider_type)
        if not provider_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider} not configured"
            )
        
        # Perform health check
        start_time = datetime.now()
        health_result = await provider_instance.health_check()
        end_time = datetime.now()
        
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return {
            "provider": provider,
            "status": "healthy" if health_result.get("healthy", False) else "unhealthy",
            "response_time_ms": response_time_ms,
            "details": health_result,
            "timestamp": end_time.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test storage provider {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test storage provider: {str(e)}"
        )


# Migration Management Endpoints
@router.post("/migration/start")
async def start_migration(
    tenant_id: Optional[str] = Query(None, description="Specific tenant ID to migrate (admin only)"),
    dry_run: bool = Query(False, description="Perform dry run without actual migration"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Start attachment migration to cloud storage.
    If tenant_id is provided, requires admin privileges.
    """
    # Determine target tenant
    if tenant_id:
        require_admin(current_user, "migrate other tenant data")
        target_tenant_id = tenant_id
    else:
        target_tenant_id = str(current_user.tenant_id)
    
    try:
        # Initialize services
        cloud_config = get_cloud_storage_config()
        cloud_storage_service = CloudStorageService(db, cloud_config)
        migration_service = AttachmentMigrationService(cloud_storage_service, db)
        
        # Start migration
        migration_result = await migration_service.migrate_tenant_attachments(
            tenant_id=target_tenant_id,
            dry_run=dry_run
        )
        
        if 'error' in migration_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=migration_result['error']
            )
        
        return {
            "message": "Migration started successfully" if not dry_run else "Dry run completed",
            "tenant_id": target_tenant_id,
            "dry_run": dry_run,
            "stats": migration_result.get('stats', {}),
            "started_at": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start migration for tenant {target_tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start migration: {str(e)}"
        )


@router.get("/migration/status")
async def get_migration_status(
    tenant_id: Optional[str] = Query(None, description="Specific tenant ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get migration status for a tenant.
    If tenant_id is provided, requires admin privileges.
    """
    # Determine target tenant
    if tenant_id:
        require_admin(current_user, "view other tenant migration status")
        target_tenant_id = tenant_id
    else:
        target_tenant_id = str(current_user.tenant_id)
    
    try:
        # Initialize services
        cloud_config = get_cloud_storage_config()
        cloud_storage_service = CloudStorageService(db, cloud_config)
        migration_service = AttachmentMigrationService(cloud_storage_service, db)
        
        # Get migration status
        status_result = await migration_service.get_migration_status(target_tenant_id)
        
        return MigrationStatusResponse(
            tenant_id=target_tenant_id,
            status=status_result.get('status', 'unknown'),
            total_files=status_result.get('total_files', 0),
            migrated_files=status_result.get('migrated_files', 0),
            failed_files=status_result.get('failed_files', 0),
            skipped_files=status_result.get('skipped_files', 0),
            started_at=status_result.get('started_at'),
            completed_at=status_result.get('completed_at'),
            error_message=status_result.get('error_message')
        )
        
    except Exception as e:
        logger.error(f"Failed to get migration status for tenant {target_tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration status: {str(e)}"
        )


# Storage Monitoring Endpoints
@router.get("/health", response_model=List[StorageHealthResponse])
async def get_storage_health(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get health status of all configured storage providers.
    """
    try:
        # Initialize monitoring service
        monitoring_service = StorageMonitoringService(db)
        
        # Get health status for all providers
        health_results = await monitoring_service.check_all_providers_health()
        
        health_responses = []
        for provider, result in health_results.items():
            health_responses.append(StorageHealthResponse(
                provider=provider,
                status=result.get('status', 'unknown'),
                response_time_ms=result.get('response_time_ms'),
                error_message=result.get('error_message'),
                last_check=result.get('timestamp', datetime.now(timezone.utc).isoformat())
            ))
        
        return health_responses
        
    except Exception as e:
        logger.error(f"Failed to get storage health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage health: {str(e)}"
        )


@router.get("/usage")
async def get_storage_usage(
    tenant_id: Optional[str] = Query(None, description="Specific tenant ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get storage usage statistics.
    If tenant_id is provided, requires admin privileges.
    """
    # Determine target tenant
    if tenant_id:
        require_admin(current_user, "view other tenant storage usage")
        target_tenant_id = tenant_id
    else:
        target_tenant_id = str(current_user.tenant_id)
    
    try:
        # Initialize monitoring service
        monitoring_service = StorageMonitoringService(db)
        
        # Get usage statistics
        usage_stats = await monitoring_service.get_tenant_usage_stats(target_tenant_id)
        
        return StorageUsageResponse(
            tenant_id=target_tenant_id,
            total_files=usage_stats.get('total_files', 0),
            total_size_bytes=usage_stats.get('total_size_bytes', 0),
            by_provider=usage_stats.get('by_provider', {}),
            by_type=usage_stats.get('by_type', {})
        )
        
    except Exception as e:
        logger.error(f"Failed to get storage usage for tenant {target_tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage usage: {str(e)}"
        )


@router.get("/operations/logs")
async def get_operation_logs(
    limit: int = Query(100, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    tenant_id: Optional[str] = Query(None, description="Specific tenant ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get storage operation logs.
    If tenant_id is provided, requires admin privileges.
    """
    # Determine target tenant
    if tenant_id:
        require_admin(current_user, "view other tenant operation logs")
        target_tenant_id = tenant_id
    else:
        target_tenant_id = str(current_user.tenant_id)
    
    try:
        # Initialize monitoring service
        monitoring_service = StorageMonitoringService(db)
        
        # Get operation logs
        logs = await monitoring_service.get_operation_logs(
            tenant_id=target_tenant_id,
            limit=limit,
            offset=offset,
            operation_type=operation_type,
            provider=provider
        )
        
        return {
            "logs": logs,
            "total_count": len(logs),
            "limit": limit,
            "offset": offset,
            "filters": {
                "tenant_id": target_tenant_id,
                "operation_type": operation_type,
                "provider": provider
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get operation logs for tenant {target_tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get operation logs: {str(e)}"
        )


@router.post("/cleanup/orphaned-files")
async def cleanup_orphaned_files(
    tenant_id: Optional[str] = Query(None, description="Specific tenant ID (admin only)"),
    dry_run: bool = Query(True, description="Perform dry run without actual cleanup"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Clean up orphaned files (files without database records).
    If tenant_id is provided, requires admin privileges.
    """
    # Determine target tenant
    if tenant_id:
        require_admin(current_user, "cleanup other tenant files")
        target_tenant_id = tenant_id
    else:
        target_tenant_id = str(current_user.tenant_id)
    
    try:
        # Initialize monitoring service
        monitoring_service = StorageMonitoringService(db)
        
        # Perform cleanup
        cleanup_result = await monitoring_service.cleanup_orphaned_files(
            tenant_id=target_tenant_id,
            dry_run=dry_run
        )
        
        return {
            "message": "Cleanup completed" if not dry_run else "Dry run completed",
            "tenant_id": target_tenant_id,
            "dry_run": dry_run,
            "orphaned_files_found": cleanup_result.get('orphaned_files', 0),
            "files_cleaned": cleanup_result.get('files_cleaned', 0) if not dry_run else 0,
            "space_freed_bytes": cleanup_result.get('space_freed_bytes', 0) if not dry_run else 0,
            "errors": cleanup_result.get('errors', [])
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned files for tenant {target_tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup orphaned files: {str(e)}"
        )