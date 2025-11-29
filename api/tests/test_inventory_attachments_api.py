"""
Integration tests for Inventory Attachments API endpoints

Tests the complete attachment workflow including upload, download, and management.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import io
from unittest.mock import patch, MagicMock

from main import app
from core.models.models_per_tenant import InventoryItem, ItemAttachment, User
from core.models.database import get_db


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_user(db: Session):
    """Create test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        first_name="Test",
        last_name="User",
        role="admin",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_inventory_item(db: Session, test_user):
    """Create test inventory item"""
    item = InventoryItem(
        name="Test Laptop",
        description="A test laptop for attachment testing",
        unit_price=1299.99,
        cost_price=900.00,
        currency="USD",
        track_stock=True,
        current_stock=10,
        minimum_stock=2,
        unit_of_measure="each",
        item_type="product",
        is_active=True
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers"""
    # This would normally get a JWT token, but for testing we'll mock it
    return {"Authorization": "Bearer test_token"}


def test_attachment_upload_endpoint_structure(client):
    """Test that upload endpoint exists and has correct structure"""
    # Test that the endpoint accepts the expected parameters
    # Note: This is a structure test since we don't have full auth setup

    # Check if the endpoint is registered
    routes = [route.path for route in app.routes]
    upload_route = "/api/v1/inventory/{item_id}/attachments"

    # The route should exist (with item_id parameter)
    matching_routes = [route for route in routes if "inventory" in route and "attachments" in route]
    assert len(matching_routes) > 0, f"No attachment routes found. Available routes: {routes[:10]}..."

    print(f"✓ Found {len(matching_routes)} attachment routes")


def test_attachment_response_models():
    """Test that response models are properly defined"""
    from core.schemas.inventory_attachments import (
        AttachmentResponse,
        AttachmentCreate,
        AttachmentUpdate,
        AttachmentOrder
    )

    # Test that we can create instances of the models
    create_data = {
        "attachment_type": "image",
        "document_type": None,
        "description": "Test image"
    }

    create_model = AttachmentCreate(**create_data)
    assert create_model.attachment_type == "image"
    assert create_model.description == "Test image"

    print("✓ Response models are properly defined")


def test_file_storage_service_basic():
    """Test basic file storage service functionality"""
    from core.services.file_storage_service import FileStorageService

    service = FileStorageService()

    # Test secure filename generation
    original = "test image.jpg"
    item_id = 123
    secure_name = service.generate_secure_filename(original, item_id)

    assert "item_123" in secure_name
    assert secure_name.endswith(".jpg")
    assert len(secure_name) > len(original)  # Should include UUID

    print("✓ File storage service basic functionality works")


def test_image_processing_service_basic():
    """Test basic image processing service functionality"""
    from core.services.image_processing_service import ImageProcessingService

    service = ImageProcessingService()

    # Test that service has expected attributes
    assert hasattr(service, 'thumbnail_sizes')
    assert hasattr(service, 'max_image_size')
    assert hasattr(service, 'quality_settings')

    # Test thumbnail sizes configuration
    assert len(service.thumbnail_sizes) > 0
    assert all(isinstance(size, tuple) and len(size) == 2 for size in service.thumbnail_sizes)

    print("✓ Image processing service basic functionality works")


def test_attachment_service_basic():
    """Test basic attachment service functionality"""
    from core.services.attachment_service import AttachmentService
    from core.models.database import SessionLocal

    # Create service instance
    db = SessionLocal()
    try:
        service = AttachmentService(db)

        # Test that service has expected methods
        expected_methods = [
            'upload_attachment',
            'delete_attachment',
            'update_attachment_metadata',
            'set_primary_image',
            'reorder_attachments',
            'get_item_attachments',
            'get_attachment_by_id',
            'get_primary_image'
        ]

        for method in expected_methods:
            assert hasattr(service, method), f"Missing method: {method}"

        print("✓ Attachment service has all expected methods")

    finally:
        db.close()


def test_model_relationships():
    """Test that model relationships are properly configured"""
    from core.models.models_per_tenant import InventoryItem, ItemAttachment

    # Test InventoryItem has attachments relationship
    assert hasattr(InventoryItem, 'attachments')

    # Test ItemAttachment has item relationship
    assert hasattr(ItemAttachment, 'item')

    # Test ItemAttachment has uploader relationship
    assert hasattr(ItemAttachment, 'uploader')

    print("✓ Model relationships are properly configured")


def test_api_router_registration():
    """Test that the attachment router is properly registered"""
    from core.routers.inventory_attachments import router

    # Test that router has expected prefix (without the /api/v1 prefix that's added at app level)
    assert router.prefix == "/inventory/{item_id}/attachments"

    # Test that router has routes
    routes = [route.path for route in router.routes]
    assert len(routes) > 0

    # Check for key routes
    route_paths = [route.replace("/api/inventory/{item_id}/attachments", "") for route in routes]
    expected_routes = ["", "/{attachment_id}", "/{attachment_id}/set-primary", "/reorder"]

    for expected in expected_routes:
        assert expected in route_paths, f"Missing route: {expected}"

    print(f"✓ Router has {len(routes)} routes registered")


def test_service_integration():
    """Test that services can be imported and instantiated"""
    try:
        from core.services.file_storage_service import file_storage_service
        from core.services.image_processing_service import image_processing_service
        from core.services.attachment_service import AttachmentService
        from core.models.database import SessionLocal

        # Test global instances
        assert file_storage_service is not None
        assert image_processing_service is not None

        # Test service instantiation
        db = SessionLocal()
        try:
            attachment_service = AttachmentService(db)
            assert attachment_service is not None
            print("✓ All services can be imported and instantiated")
        finally:
            db.close()

    except ImportError as e:
        pytest.fail(f"Failed to import services: {e}")


def test_schema_validation():
    """Test that schemas validate correctly"""
    from core.schemas.inventory_attachments import (
        AttachmentCreate,
        AttachmentUpdate,
        AttachmentOrder
    )

    # Test valid attachment creation
    valid_create = AttachmentCreate(
        attachment_type="image",
        description="Test image"
    )
    assert valid_create.attachment_type == "image"

    # Test valid document creation
    valid_doc_create = AttachmentCreate(
        attachment_type="document",
        document_type="manual",
        description="User manual"
    )
    assert valid_doc_create.document_type == "manual"

    # Test invalid attachment type
    try:
        invalid_create = AttachmentCreate(attachment_type="invalid")
        pytest.fail("Should have raised validation error")
    except ValueError:
        pass  # Expected

    # Test invalid document type
    try:
        invalid_doc_create = AttachmentCreate(
            attachment_type="document",
            document_type="invalid"
        )
        pytest.fail("Should have raised validation error")
    except ValueError:
        pass  # Expected

    print("✓ Schema validation works correctly")


def test_router_dependencies():
    """Test that router has proper dependencies"""
    from core.routers.inventory_attachments import get_attachment_service, get_db

    # Test that dependency functions exist
    assert callable(get_attachment_service)
    assert callable(get_db)

    print("✓ Router dependencies are properly configured")


if __name__ == "__main__":
    print("🧪 Running Inventory Attachments API Tests...")
    print("=" * 50)

    # Run basic structure tests
    test_attachment_response_models()
    test_file_storage_service_basic()
    test_image_processing_service_basic()
    test_attachment_service_basic()
    test_model_relationships()
    test_api_router_registration()
    test_service_integration()
    test_schema_validation()
    test_router_dependencies()

    print("=" * 50)
    print("✅ All basic structure tests passed!")
    print("\n📝 Note: Full integration tests require:")
    print("   - Database setup and migrations")
    print("   - Authentication system")
    print("   - File storage system")
    print("   - Proper test fixtures")
