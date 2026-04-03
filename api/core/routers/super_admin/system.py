from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import logging

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.audit import log_audit_event_master
from core.routers.super_admin._shared import require_super_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== DATABASE OPERATIONS ==========

@router.get("/tenants/{tenant_id}/database/status")
async def get_tenant_database_status(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get the status of a tenant's database"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    try:
        # Try to connect to tenant database
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()

        # Test connection with a simple query
        tenant_session.execute(text("SELECT 1"))

        tenant_session.close()

        return {
            "tenant_id": tenant_id,
            "database_name": f"tenant_{tenant_id}",
            "status": "connected",
            "message": "Database is accessible"
        }
    except Exception as e:
        return {
            "tenant_id": tenant_id,
            "database_name": f"tenant_{tenant_id}",
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }


@router.post("/tenants/{tenant_id}/database/recreate")
async def recreate_tenant_database(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin),
    request: Request = None
):
    """Recreate a tenant's database (WARNING: This will delete all data)"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Prevent super admin from recreating their own tenant's database
    if tenant_id == current_user.tenant_id:
        # Log audit event for attempted self-database recreation
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECREATE_DATABASE",
            resource_type="DATABASE",
            resource_id=str(tenant_id),
            resource_name=f"{tenant.name} Database",
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "error": "Attempted to recreate own tenant database",
                "user_tenant_id": current_user.tenant_id
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message="Cannot recreate your own tenant's database",
            tenant_id=tenant_id
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot recreate your own tenant's database"
        )

    try:
        success = tenant_db_manager.recreate_tenant_database(tenant_id, tenant.name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to recreate tenant database"
            )

        # Log audit event for database recreation
        logger.info(f"Creating master audit log for database recreation by {current_user.email}")
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECREATE_DATABASE",
            resource_type="DATABASE",
            resource_id=str(tenant_id),
            resource_name=f"{tenant.name} Database",
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "database_name": f"tenant_{tenant_id}_{tenant.name.lower().replace(' ', '_')}"
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="success",
            tenant_id=tenant_id
        )
        logger.info("Master audit log created successfully")

        return {"message": f"Database for tenant {tenant.name} recreated successfully"}

    except Exception as e:
        # Log audit event for failed database recreation
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECREATE_DATABASE",
            resource_type="DATABASE",
            resource_id=str(tenant_id),
            resource_name=f"{tenant.name} Database",
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "error": str(e)
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message=str(e),
            tenant_id=tenant_id
        )
        raise


@router.get("/database/overview")
async def get_database_overview(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get overview of all tenant databases"""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    tenants = master_db.query(Tenant).all()

    overview = {
        "total_tenants": len(tenants),
        "databases": []
    }

    def test_tenant_connection(tenant_id: int, tenant_name: str) -> dict:
        """Test database connection for a single tenant with timeout"""
        db_info = {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "database_name": f"tenant_{tenant_id}",
            "status": "unknown"
        }

        try:
            # Test database connection with a timeout
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
            tenant_session.execute(text("SELECT 1"))
            tenant_session.close()
            db_info["status"] = "connected"
        except Exception as e:
            db_info["status"] = "error"
            db_info["error"] = str(e)

        return db_info

    # Use ThreadPoolExecutor with timeout to prevent hanging
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for tenant in tenants:
            future = executor.submit(test_tenant_connection, tenant.id, tenant.name)
            futures.append(future)

        # Wait for all futures with a timeout of 30 seconds total
        for future in futures:
            try:
                db_info = future.result(timeout=5)  # 5 second timeout per tenant
                overview["databases"].append(db_info)
            except FuturesTimeoutError:
                # Extract tenant info from the future if possible
                tenant_id = None
                tenant_name = "Unknown"
                for i, tenant in enumerate(tenants):
                    if futures[i] == future:
                        tenant_id = tenant.id
                        tenant_name = tenant.name
                        break

                overview["databases"].append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "database_name": f"tenant_{tenant_id}" if tenant_id else "unknown",
                    "status": "timeout",
                    "error": "Database connection test timed out"
                })
            except Exception as e:
                # Handle any other exceptions
                tenant_id = None
                tenant_name = "Unknown"
                for i, tenant in enumerate(tenants):
                    if futures[i] == future:
                        tenant_id = tenant.id
                        tenant_name = tenant.name
                        break

                overview["databases"].append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "database_name": f"tenant_{tenant_id}" if tenant_id else "unknown",
                    "status": "error",
                    "error": str(e)
                })

    return overview


# ========== CROSS-TENANT ANOMALY DETECTION ==========

@router.get("/anomalies")
async def get_all_anomalies(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    risk_level: Optional[str] = Query(None),
    is_dismissed: bool = Query(False),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Aggregate anomalies from all tenants for platform-wide monitoring"""
    from core.services.feature_config_service import FeatureConfigService

    # Debug logging
    logger.info(f"get_all_anomalies called with skip={skip}, limit={limit}, risk_level={risk_level}, is_dismissed={is_dismissed}")

    # Check if anomaly detection is enabled via environment variable or license
    # Note: We check without db to avoid transaction issues with master_db
    is_enabled = FeatureConfigService.is_enabled('anomaly_detection', db=None, check_license=False)

    logger.info(f"Anomaly detection check - enabled: {is_enabled}")

    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FinanceWorks Insights feature is not available in your current license"
        )

    tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()

    all_anomalies = []
    total_count = 0

    # First, count total anomalies across all tenants
    for tenant in tenants:
        tenant_session = None
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
            from core.models.models_per_tenant import Anomaly

            query = tenant_session.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)

            if risk_level:
                query = query.filter(Anomaly.risk_level == risk_level)

            # Count total anomalies for this tenant
            total_count += query.count()

        except Exception as e:
            logger.error(f"Failed to count anomalies for tenant {tenant.id}: {e}")
            continue
        finally:
            if tenant_session:
                try:
                    tenant_session.close()
                except Exception as e:
                    logger.error(f"Error closing tenant session for {tenant.id}: {e}")

    # Now fetch paginated results more efficiently
    # Calculate how many records we need to fetch from each tenant
    # For page N with size L, we need to fetch enough records to potentially fill all pages up to N
    # We fetch (skip + limit) records from each tenant to ensure we have enough data
    fetch_per_tenant = skip + limit

    # But cap it to avoid excessive fetching
    max_fetch_per_tenant = min(fetch_per_tenant, 500)  # Increased cap to ensure we have enough data

    logger.info(f"Fetching up to {max_fetch_per_tenant} records per tenant for pagination (skip={skip}, limit={limit})")

    for tenant in tenants:
        tenant_session = None
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
            from core.models.models_per_tenant import Anomaly

            query = tenant_session.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)

            if risk_level:
                query = query.filter(Anomaly.risk_level == risk_level)

            # Get sufficient anomalies from each tenant for sorting and pagination
            anomalies = query.order_by(Anomaly.created_at.desc()).limit(max_fetch_per_tenant).all()

            for a in anomalies:
                all_anomalies.append({
                    "id": a.id,
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "risk_score": a.risk_score,
                    "risk_level": a.risk_level,
                    "reason": a.reason,
                    "rule_id": a.rule_id,
                    "details": a.details,
                    "created_at": a.created_at
                })

        except Exception as e:
            logger.error(f"Failed to fetch anomalies for tenant {tenant.id}: {e}")
            continue
        finally:
            if tenant_session:
                try:
                    tenant_session.close()
                except Exception as e:
                    logger.error(f"Error closing tenant session for {tenant.id}: {e}")

    # Sort results by date across all tenants and apply pagination
    all_anomalies.sort(key=lambda x: x['created_at'], reverse=True)
    paginated_anomalies = all_anomalies[skip:skip + limit]

    logger.info(f"Before pagination: {len(all_anomalies)} total anomalies collected")
    logger.info(f"After pagination: {len(paginated_anomalies)} items returned (skip={skip}, limit={limit})")

    return {
        "items": paginated_anomalies,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }


@router.post("/anomalies/audit")
async def trigger_full_audit(
    days: int = Query(30),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Trigger a forensic audit scan for all active tenants for the last N days"""
    from core.services.feature_config_service import FeatureConfigService

    logger.info(f"trigger_full_audit: Starting audit scan for {days} days")

    # For super admin operations, check license using super admin's tenant database
    # since InstallationInfo is stored in tenant databases, not master
    super_admin_tenant_id = current_user.tenant_id
    tenant_session = tenant_db_manager.get_tenant_session(super_admin_tenant_id)()

    try:
        # Check if anomaly detection is enabled using tenant database for license check
        feature_enabled = FeatureConfigService.is_enabled('anomaly_detection', db=tenant_session)
        logger.info(f"trigger_full_audit: anomaly_detection feature enabled = {feature_enabled}")

        if not feature_enabled:
            logger.error("trigger_full_audit: anomaly_detection feature not enabled")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FinanceWorks Insights feature is not available in your current license"
            )
    finally:
        tenant_session.close()

    logger.info("trigger_full_audit: License check passed, proceeding with audit scan")
    from commercial.ai.services.ocr_service import publish_fraud_audit_task
    from core.models.models_per_tenant import Expense, BankStatementTransaction
    from datetime import datetime, timezone, timedelta

    tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    total_triggered = 0

    for tenant in tenants:
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()

            # Audit Expenses
            expenses = tenant_session.query(Expense).filter(
                Expense.created_at >= cutoff_date
            ).all()
            for exp in expenses:
                if publish_fraud_audit_task(tenant.id, "expense", exp.id, reprocess_mode=False):
                    total_triggered += 1

            # Audit Bank Transactions
            transactions = tenant_session.query(BankStatementTransaction).filter(
                BankStatementTransaction.created_at >= cutoff_date
            ).all()
            for txn in transactions:
                if publish_fraud_audit_task(tenant.id, "bank_statement_transaction", txn.id, reprocess_mode=False):
                    total_triggered += 1

            tenant_session.close()
        except Exception as e:
            logger.error(f"Failed to trigger audit for tenant {tenant.id}: {e}")
            continue

    # Log audit event
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="TRIGGER_FULL_ANOMALY_AUDIT",
        resource_type="ANOMALY_DETECTION",
        details={
            "days": days,
            "entities_triggered": total_triggered,
            "tenants_scanned": len(tenants)
        }
    )

    return {
        "message": f"Successfully queued {total_triggered} entities for forensic audit across {len(tenants)} active tenants.",
        "entities_queued": total_triggered,
        "tenants_scanned": len(tenants)
    }


@router.post("/anomalies/reprocess")
async def trigger_reprocess_all(
    days: int = Query(30),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Trigger reprocessing of all entities (including previously processed) for last N days"""
    from core.services.feature_config_service import FeatureConfigService

    logger.info(f"trigger_reprocess_all: Starting reprocess scan for {days} days")

    # For super admin operations, check license using super admin's tenant database
    # since InstallationInfo is stored in tenant databases, not master
    super_admin_tenant_id = current_user.tenant_id
    tenant_session = tenant_db_manager.get_tenant_session(super_admin_tenant_id)()

    try:
        # Check if anomaly detection is enabled using tenant database for license check
        feature_enabled = FeatureConfigService.is_enabled('anomaly_detection', db=tenant_session)
        logger.info(f"trigger_reprocess_all: anomaly_detection feature enabled = {feature_enabled}")

        if not feature_enabled:
            logger.error("trigger_reprocess_all: anomaly_detection feature not enabled")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FinanceWorks Insights feature is not available in your current license"
            )
    finally:
        tenant_session.close()

    logger.info("trigger_reprocess_all: License check passed, proceeding with reprocess scan")
    from commercial.ai.services.ocr_service import publish_fraud_audit_task
    from core.models.models_per_tenant import Expense, BankStatementTransaction, Invoice
    from datetime import datetime, timezone, timedelta

    tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    total_triggered = 0

    for tenant in tenants:
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()

            # Reprocess ALL entities without filtering for previous processing
            # This includes entities that may have been processed before

            # Reprocess Expenses
            expenses = tenant_session.query(Expense).filter(
                Expense.created_at >= cutoff_date
            ).all()
            for exp in expenses:
                if publish_fraud_audit_task(tenant.id, "expense", exp.id, reprocess_mode=True):
                    total_triggered += 1

            # Reprocess Invoices
            invoices = tenant_session.query(Invoice).filter(
                Invoice.created_at >= cutoff_date
            ).all()
            for inv in invoices:
                if publish_fraud_audit_task(tenant.id, "invoice", inv.id, reprocess_mode=True):
                    total_triggered += 1

            # Reprocess Bank Transactions
            transactions = tenant_session.query(BankStatementTransaction).filter(
                BankStatementTransaction.created_at >= cutoff_date
            ).all()
            for txn in transactions:
                if publish_fraud_audit_task(tenant.id, "bank_statement_transaction", txn.id, reprocess_mode=True):
                    total_triggered += 1

            tenant_session.close()
        except Exception as e:
            logger.error(f"Failed to trigger reprocess for tenant {tenant.id}: {e}")
            continue

    # Log audit event
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="TRIGGER_ANOMALY_REPROCESS_ALL",
        resource_type="ANOMALY_DETECTION",
        details={
            "days": days,
            "entities_triggered": total_triggered,
            "tenants_scanned": len(tenants)
        }
    )

    return {
        "message": f"Successfully queued {total_triggered} entities for reprocessing across {len(tenants)} active tenants.",
        "entities_queued": total_triggered,
        "tenants_scanned": len(tenants)
    }
