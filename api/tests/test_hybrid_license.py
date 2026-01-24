import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.models import Base as MasterBase, Tenant, GlobalInstallationInfo, MasterUser
from core.models.models_per_tenant import Base as TenantBase, InstallationInfo
from core.services.license_service import LicenseService
from core.services.tenant_management_service import TenantManagementService
import jwt
import time
from datetime import datetime, timedelta, timezone

# Setup in-memory databases
@pytest.fixture
def master_db():
    engine = create_engine("sqlite:///:memory:")
    MasterBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Create global installation info for master db
    import uuid
    global_info = GlobalInstallationInfo(installation_id=str(uuid.uuid4()))
    session.add(global_info)
    session.commit()
    yield session
    session.close()

@pytest.fixture
def tenant_db():
    engine = create_engine("sqlite:///:memory:")
    TenantBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_global_activation(master_db, tenant_db, monkeypatch):
    service = LicenseService(tenant_db, master_db=master_db)
    global_id = master_db.query(GlobalInstallationInfo).first().installation_id
    
    # Mock verification to always succeed with the correct installation_id and exp timestamp
    exp_ts = int(time.time() + 3600*24*30)
    monkeypatch.setattr(LicenseService, "verify_license", 
                        lambda self, key: {"valid": True, "payload": {
                            "installation_id": global_id,
                            "customer_name": "Global Cust",
                            "customer_email": "global@example.com",
                            "max_tenants": 5,
                            "features": ["all"],
                            "exp": exp_ts
                        }, "error": None})
    
    result = service.activate_global_license("valid-key", user_id=1)
    
    assert result["success"] is True, f"Activation failed: {result.get('message')}"
    
    # Verify master db has the info
    global_info = master_db.query(GlobalInstallationInfo).first()
    assert global_info is not None
    assert global_info.is_licensed is True
    assert global_info.license_key == "valid-key"
    assert global_info.license_expires_at is not None

def test_tiered_status_fallback(master_db, tenant_db, monkeypatch):
    service = LicenseService(tenant_db, master_db=master_db)
    global_id = master_db.query(GlobalInstallationInfo).first().installation_id
    
    # Set up global license behavior
    exp_ts = int(time.time() + 3600*24*30)
    monkeypatch.setattr(LicenseService, "verify_license", 
                        lambda self, key: {"valid": True, "payload": {
                            "installation_id": global_id,
                            "customer_name": "Global Cust",
                            "customer_email": "global@example.com",
                            "max_tenants": 5,
                            "features": ["f1"],
                            "exp": exp_ts
                        }, "error": None})
    
    # Ensure local installation exists but is NOT licensed
    tenant_db.add(InstallationInfo(installation_id=global_id, is_licensed=False, license_status="invalid"))
    tenant_db.commit()
    
    service.activate_global_license("global-key")
    
    # Get status - should fall back to global
    status = service.get_license_status()
    assert status["is_licensed"] is True
    assert status["effective_source"] == "global"
    assert "f1" in status["enabled_features"]

def test_local_override(master_db, tenant_db, monkeypatch):
    service = LicenseService(tenant_db, master_db=master_db)
    global_id = master_db.query(GlobalInstallationInfo).first().installation_id
    exp_ts = int(time.time() + 3600*24*30)
    
    def mock_verify(self, key):
        if key == "global-key":
            return {"valid": True, "payload": {
                            "installation_id": global_id,
                            "customer_email": "g@e.com",
                            "features": ["f1"],
                            "exp": exp_ts
                        }, "error": None}
        else:
            return {"valid": True, "payload": {
                            "installation_id": global_id,
                            "customer_email": "l@e.com",
                            "features": ["f2"],
                            "exp": exp_ts
                        }, "error": None}

    monkeypatch.setattr(LicenseService, "verify_license", mock_verify)
    
    service.activate_global_license("global-key")
    service.activate_license("local-key")
    
    # Status should be local
    status = service.get_license_status()
    assert status["is_licensed"] is True
    assert status["effective_source"] == "local"
    assert "f2" in status["enabled_features"]

def test_tenant_limit_enforcement_with_exemptions(master_db, tenant_db, monkeypatch):
    # Mock max_tenants = 1
    monkeypatch.setattr(LicenseService, "get_max_tenants", lambda self: 1)
    
    # Create 3 tenants: 1 counted, 2 exempt
    t1 = Tenant(name="T1", count_against_license=True, is_enabled=True)
    t2 = Tenant(name="T2", count_against_license=False, is_enabled=True)
    t3 = Tenant(name="T3", count_against_license=False, is_enabled=True)
    master_db.add_all([t1, t2, t3])
    master_db.commit()
    
    admin = MasterUser(id=1, tenant_id=t1.id, is_superuser=True)
    
    service = TenantManagementService(master_db, tenant_db)
    result = service.enforce_tenant_limits(admin)
    
    # Should be success because only 1 is counted
    assert result["success"] is True
    assert t1.is_enabled is True
    assert t2.is_enabled is True
    assert t3.is_enabled is True

def test_tenant_limit_violation(master_db, tenant_db, monkeypatch):
    # Mock max_tenants = 1
    monkeypatch.setattr(LicenseService, "get_max_tenants", lambda self: 1)
    
    # Create 2 counted tenants
    t1 = Tenant(name="T1", count_against_license=True, is_enabled=True)
    t2 = Tenant(name="T2", count_against_license=True, is_enabled=True)
    master_db.add_all([t1, t2])
    master_db.commit()
    
    admin = MasterUser(id=1, tenant_id=t1.id, is_superuser=True)
    
    service = TenantManagementService(master_db, tenant_db)
    # This should trigger reduction
    result = service.enforce_tenant_limits(admin)
    
    # Counted tenants enabled should be 1
    enabled_counted = master_db.query(Tenant).filter(Tenant.is_enabled == True, Tenant.count_against_license == True).count()
    assert enabled_counted == 1
