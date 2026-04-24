from core.routers.super_admin._shared import require_super_admin
from core.models.models import Tenant, MasterUser


def test_delete_tenant_archives_without_deleting_data(client, db_session):
    admin_tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()

    target_tenant = Tenant(
        id=2,
        name="Archive Me Org",
        email="org@example.com",
        default_currency="USD",
        is_active=True,
        is_enabled=True,
        count_against_license=True,
    )
    db_session.add(target_tenant)
    db_session.flush()

    admin_user = MasterUser(
        email="admin@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        tenant_id=admin_tenant.id,
        role="admin",
    )
    target_user = MasterUser(
        email="member@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        tenant_id=target_tenant.id,
        role="admin",
    )
    db_session.add_all([admin_user, target_user])
    db_session.commit()

    app = client.app
    app.dependency_overrides[require_super_admin] = lambda: admin_user

    try:
        response = client.delete("/api/v1/super-admin/tenants/2")
    finally:
        app.dependency_overrides.pop(require_super_admin, None)

    assert response.status_code == 200, response.text

    archived_tenant = db_session.query(Tenant).filter(Tenant.id == 2).first()
    assert archived_tenant is not None
    assert archived_tenant.is_active is False
    assert archived_tenant.is_enabled is False
    assert archived_tenant.count_against_license is False
    assert archived_tenant.archived_at is not None
    assert archived_tenant.archived_by_id == admin_user.id

    assert db_session.query(MasterUser).filter(MasterUser.tenant_id == 2).count() == 1


def test_restore_tenant_reactivates_license_capacity(client, db_session):
    admin_tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()

    target_tenant = Tenant(
        id=3,
        name="Restore Me Org",
        email="restore@example.com",
        default_currency="USD",
        is_active=False,
        is_enabled=False,
        count_against_license=False,
    )
    db_session.add(target_tenant)
    db_session.flush()

    admin_user = MasterUser(
        email="restore-admin@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        tenant_id=admin_tenant.id,
        role="admin",
    )
    db_session.add(admin_user)
    db_session.commit()

    target_tenant.archived_by_id = admin_user.id
    target_tenant.archive_reason = "Test archive"
    target_tenant.archived_at = target_tenant.created_at
    db_session.commit()

    app = client.app
    app.dependency_overrides[require_super_admin] = lambda: admin_user

    try:
        response = client.patch("/api/v1/super-admin/tenants/3/restore")
    finally:
        app.dependency_overrides.pop(require_super_admin, None)

    assert response.status_code == 200, response.text

    restored_tenant = db_session.query(Tenant).filter(Tenant.id == 3).first()
    assert restored_tenant.is_active is True
    assert restored_tenant.is_enabled is True
    assert restored_tenant.count_against_license is True
    assert restored_tenant.archived_at is None
    assert restored_tenant.archived_by_id is None
    assert restored_tenant.archive_reason is None
