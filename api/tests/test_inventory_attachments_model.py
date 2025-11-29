"""
Unit tests for ItemAttachment model and relationships
"""
import pytest
from sqlalchemy.orm import Session
from core.models.models_per_tenant import ItemAttachment, InventoryItem, User
from datetime import datetime, timezone


def test_item_attachment_model_creation():
    """Test ItemAttachment model can be created with all required fields"""
    # Test that we can create an ItemAttachment instance
    # Note: This is a basic structure test since we don't have DB connection

    # Verify the model has all expected attributes from the design
    expected_fields = [
        'id', 'item_id', 'filename', 'stored_filename', 'file_path',
        'file_size', 'content_type', 'file_hash', 'attachment_type',
        'document_type', 'description', 'alt_text', 'is_primary',
        'display_order', 'image_width', 'image_height', 'has_thumbnail',
        'thumbnail_path', 'uploaded_by', 'upload_ip', 'is_active',
        'created_at', 'updated_at'
    ]

    # Check that ItemAttachment class exists and has expected attributes
    attachment_attrs = [attr for attr in dir(ItemAttachment) if not attr.startswith('_')]
    for field in expected_fields:
        assert field in attachment_attrs, f"Missing field: {field}"


def test_inventory_item_attachments_relationship():
    """Test that InventoryItem has attachments relationship"""
    # Verify InventoryItem has attachments relationship
    item_attrs = [attr for attr in dir(InventoryItem) if not attr.startswith('_')]
    assert 'attachments' in item_attrs, "InventoryItem missing attachments relationship"


def test_item_attachment_relationships():
    """Test that ItemAttachment has proper relationships"""
    attachment_attrs = [attr for attr in dir(ItemAttachment) if not attr.startswith('_')]
    assert 'item' in attachment_attrs, "ItemAttachment missing item relationship"
    assert 'uploader' in attachment_attrs, "ItemAttachment missing uploader relationship"


def test_model_table_names():
    """Test that models have correct table names"""
    assert ItemAttachment.__tablename__ == "item_attachments"
    assert InventoryItem.__tablename__ == "inventory_items"
    assert User.__tablename__ == "users"


def test_model_imports():
    """Test that all models can be imported successfully"""
    try:
        from core.models.models_per_tenant import ItemAttachment, InventoryItem, User
        assert True, "All models imported successfully"
    except ImportError as e:
        pytest.fail(f"Failed to import models: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
