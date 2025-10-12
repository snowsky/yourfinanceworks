#!/usr/bin/env python3
"""
Test script to verify ItemAttachment table creation in tenant databases.
"""
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import logging

from models.models_per_tenant import ItemAttachment
from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_table_creation():
    """Test that ItemAttachment table can be created."""
    try:
        # Create a test database URL (you can modify this for your environment)
        test_db_url = "sqlite:///./test_inventory_attachments.db"

        logger.info("Creating test database engine...")
        engine = create_engine(test_db_url)

        # Create the ItemAttachment table
        logger.info("Creating ItemAttachment table...")
        ItemAttachment.__table__.create(bind=engine, checkfirst=True)

        # Verify table was created
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if 'item_attachments' in tables:
            logger.info("✓ ItemAttachment table created successfully")

            # Get table columns
            columns = inspector.get_columns('item_attachments')
            column_names = [col['name'] for col in columns]
            logger.info(f"✓ Table has {len(columns)} columns: {', '.join(column_names)}")

            # Check indexes
            indexes = inspector.get_indexes('item_attachments')
            logger.info(f"✓ Table has {len(indexes)} indexes")

            # Verify expected columns exist
            expected_columns = [
                'id', 'item_id', 'filename', 'stored_filename', 'file_path',
                'file_size', 'content_type', 'file_hash', 'attachment_type',
                'document_type', 'description', 'alt_text', 'is_primary',
                'display_order', 'image_width', 'image_height', 'has_thumbnail',
                'thumbnail_path', 'uploaded_by', 'upload_ip', 'is_active',
                'created_at', 'updated_at'
            ]

            actual_columns = [col['name'] for col in columns]
            missing_columns = set(expected_columns) - set(actual_columns)

            if missing_columns:
                logger.error(f"✗ Missing columns: {missing_columns}")
                return False

            logger.info("✓ All expected columns present")

            # Test that we can create and query an ItemAttachment instance
            from sqlalchemy.orm import sessionmaker
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db = SessionLocal()

            try:
                # Test creating an attachment record
                attachment = ItemAttachment(
                    item_id=1,
                    filename="test_image.jpg",
                    stored_filename="item_1_123456_test_image.jpg",
                    file_path="/attachments/tenant_1/inventory/images/test_image.jpg",
                    file_size=1024000,
                    content_type="image/jpeg",
                    file_hash="abc123def456",
                    attachment_type="image",
                    description="Test image",
                    is_primary=True,
                    display_order=0,
                    uploaded_by=1,
                    is_active=True
                )

                db.add(attachment)
                db.commit()
                db.refresh(attachment)

                logger.info(f"✓ Successfully created attachment with ID: {attachment.id}")

                # Test querying
                retrieved = db.query(ItemAttachment).filter(ItemAttachment.id == attachment.id).first()
                if retrieved:
                    logger.info("✓ Successfully retrieved attachment")
                    logger.info(f"  - Filename: {retrieved.filename}")
                    logger.info(f"  - Size: {retrieved.file_size} bytes")
                    logger.info(f"  - Type: {retrieved.attachment_type}")
                    logger.info(f"  - Primary: {retrieved.is_primary}")
                else:
                    logger.error("✗ Failed to retrieve attachment")
                    return False

            finally:
                db.close()

            return True

        else:
            logger.error("✗ ItemAttachment table was not created")
            return False

    except Exception as e:
        logger.error(f"Error testing table creation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_relationships():
    """Test model relationships."""
    try:
        from models.models_per_tenant import InventoryItem, User

        # Test that InventoryItem has attachments relationship
        assert hasattr(InventoryItem, 'attachments'), "InventoryItem missing attachments relationship"

        # Test that ItemAttachment has relationships
        assert hasattr(ItemAttachment, 'item'), "ItemAttachment missing item relationship"
        assert hasattr(ItemAttachment, 'uploader'), "ItemAttachment missing uploader relationship"

        logger.info("✓ Model relationships are correct")
        return True

    except Exception as e:
        logger.error(f"Error testing relationships: {e}")
        return False


def main():
    """Main test function."""
    logger.info("🧪 Testing ItemAttachment Table Creation")
    logger.info("=" * 50)

    success = True

    # Test model relationships
    if not test_relationships():
        success = False

    # Test table creation
    if not test_table_creation():
        success = False

    logger.info("=" * 50)
    if success:
        logger.info("✅ All tests passed! ItemAttachment table is ready.")
        logger.info("\n📋 Next steps:")
        logger.info("   1. Run database initialization with: python db_init.py")
        logger.info("   2. Or use the creation script: python scripts/create_inventory_attachments_table.py --all-tenants")
        logger.info("   3. Continue with frontend implementation")
    else:
        logger.error("❌ Some tests failed")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
