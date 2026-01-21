"""
Database integration tests for encrypted models.

Tests SQLAlchemy integration with encrypted columns, query performance,
and data integrity for the tenant database encryption system.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import StatementError

from core.models.database import Base, set_tenant_context, clear_tenant_context, get_tenant_context
from core.utils.column_encryptor import (
    EncryptedColumn, 
    EncryptedJSON, 
    create_encrypted_string_column,
    create_encrypted_json_column,
    is_encrypted_data,
    get_encryption_metadata
)
from core.services.encryption_service import EncryptionService
from core.exceptions.encryption_exceptions import EncryptionError, DecryptionError


# Test model with encrypted fields
class TestUser(Base):
    """Test user model with encrypted fields."""
    __tablename__ = "test_users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = EncryptedColumn(String, nullable=False, index=True)
    first_name = EncryptedColumn(String, nullable=True)
    last_name = EncryptedColumn(String, nullable=True)
    phone = EncryptedColumn(String, nullable=True)
    # Non-encrypted fields
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TestInvoice(Base):
    """Test invoice model with encrypted JSON fields."""
    __tablename__ = "test_invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    # Encrypted fields
    notes = EncryptedColumn(Text, nullable=True)
    custom_fields = EncryptedJSON(nullable=True)
    client_info = EncryptedJSON(nullable=True)
    # Non-encrypted fields
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)


class TestEncryptedModels:
    """Test cases for encrypted model operations."""

    @pytest.fixture
    def db_engine(self):
        """Create in-memory SQLite database engine for testing."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        return engine

    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session with test tables."""
        # Create all test tables
        Base.metadata.create_all(bind=db_engine)
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=db_engine)

    @pytest.fixture
    def tenant_context(self):
        """Set up tenant context for testing."""
        tenant_id = 1
        set_tenant_context(tenant_id)
        yield tenant_id
        clear_tenant_context()

    @pytest.fixture
    def mock_encryption_service(self):
        """Mock encryption service for testing."""
        with patch('api.utils.column_encryptor.get_encryption_service') as mock_get_service:
            mock_service = Mock(spec=EncryptionService)
            
            # Mock encryption/decryption to return predictable results
            def mock_encrypt(data, tenant_id):
                return f"encrypted_{data}_{tenant_id}"
            
            def mock_decrypt(data, tenant_id):
                if data.startswith(f"encrypted_") and data.endswith(f"_{tenant_id}"):
                    return data[10:-2]  # Remove "encrypted_" prefix and "_X" suffix
                return data
            
            def mock_encrypt_json(data, tenant_id):
                json_str = json.dumps(data, sort_keys=True)
                return f"encrypted_json_{json_str}_{tenant_id}"
            
            def mock_decrypt_json(data, tenant_id):
                if data.startswith(f"encrypted_json_") and data.endswith(f"_{tenant_id}"):
                    json_str = data[15:-2]  # Remove "encrypted_json_" prefix and "_X" suffix
                    return json.loads(json_str)
                return {}
            
            mock_service.encrypt_data.side_effect = mock_encrypt
            mock_service.decrypt_data.side_effect = mock_decrypt
            mock_service.encrypt_json.side_effect = mock_encrypt_json
            mock_service.decrypt_json.side_effect = mock_decrypt_json
            
            mock_get_service.return_value = mock_service
            yield mock_service

    def test_encrypted_string_column_storage_retrieval(self, db_session, tenant_context, mock_encryption_service):
        """Test storing and retrieving encrypted string data."""
        # Create test user
        user = TestUser(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            phone="+1-555-0123"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Verify encryption was called
        assert mock_encryption_service.encrypt_data.call_count == 4  # email, first_name, last_name, phone
        
        # Verify data is stored encrypted in database
        raw_result = db_session.execute(
            "SELECT email, first_name, last_name, phone FROM test_users WHERE id = ?",
            (user.id,)
        ).fetchone()
        
        assert raw_result[0] == f"encrypted_test@example.com_{tenant_context}"
        assert raw_result[1] == f"encrypted_John_{tenant_context}"
        assert raw_result[2] == f"encrypted_Doe_{tenant_context}"
        assert raw_result[3] == f"encrypted_+1-555-0123_{tenant_context}"
        
        # Verify data is decrypted when accessed through model
        retrieved_user = db_session.query(TestUser).filter(TestUser.id == user.id).first()
        assert retrieved_user.email == "test@example.com"
        assert retrieved_user.first_name == "John"
        assert retrieved_user.last_name == "Doe"
        assert retrieved_user.phone == "+1-555-0123"

    def test_encrypted_json_column_storage_retrieval(self, db_session, tenant_context, mock_encryption_service):
        """Test storing and retrieving encrypted JSON data."""
        custom_fields = {
            "project_code": "PROJ-123",
            "department": "Engineering",
            "metadata": {
                "priority": "high",
                "tags": ["urgent", "client-request"]
            }
        }
        
        client_info = {
            "contact_person": "Jane Smith",
            "billing_address": {
                "street": "123 Main St",
                "city": "Anytown",
                "country": "USA"
            }
        }
        
        # Create test invoice
        invoice = TestInvoice(
            number="INV-001",
            amount=1000.00,
            notes="Confidential project invoice",
            custom_fields=custom_fields,
            client_info=client_info
        )
        
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)
        
        # Verify encryption was called
        assert mock_encryption_service.encrypt_data.call_count == 1  # notes
        assert mock_encryption_service.encrypt_json.call_count == 2  # custom_fields, client_info
        
        # Verify data is stored encrypted in database
        raw_result = db_session.execute(
            "SELECT notes, custom_fields, client_info FROM test_invoices WHERE id = ?",
            (invoice.id,)
        ).fetchone()
        
        expected_custom_fields = f"encrypted_json_{json.dumps(custom_fields, sort_keys=True)}_{tenant_context}"
        expected_client_info = f"encrypted_json_{json.dumps(client_info, sort_keys=True)}_{tenant_context}"
        
        assert raw_result[0] == f"encrypted_Confidential project invoice_{tenant_context}"
        assert raw_result[1] == expected_custom_fields
        assert raw_result[2] == expected_client_info
        
        # Verify data is decrypted when accessed through model
        retrieved_invoice = db_session.query(TestInvoice).filter(TestInvoice.id == invoice.id).first()
        assert retrieved_invoice.notes == "Confidential project invoice"
        assert retrieved_invoice.custom_fields == custom_fields
        assert retrieved_invoice.client_info == client_info

    def test_empty_and_null_values(self, db_session, tenant_context, mock_encryption_service):
        """Test handling of empty and null values."""
        # Create user with some empty/null values
        user = TestUser(
            email="test@example.com",
            first_name="",  # Empty string
            last_name=None,  # Null value
            phone="555-0123"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Verify empty string and null are handled correctly
        retrieved_user = db_session.query(TestUser).filter(TestUser.id == user.id).first()
        assert retrieved_user.email == "test@example.com"
        assert retrieved_user.first_name == ""
        assert retrieved_user.last_name is None
        assert retrieved_user.phone == "555-0123"

    def test_query_operations(self, db_session, tenant_context, mock_encryption_service):
        """Test various query operations with encrypted data."""
        # Create multiple test users
        users = [
            TestUser(email="user1@example.com", first_name="Alice", last_name="Smith"),
            TestUser(email="user2@example.com", first_name="Bob", last_name="Jones"),
            TestUser(email="user3@example.com", first_name="Charlie", last_name="Brown")
        ]
        
        for user in users:
            db_session.add(user)
        db_session.commit()
        
        # Test basic queries
        all_users = db_session.query(TestUser).all()
        assert len(all_users) == 3
        
        # Test filtering (note: this won't work with real encryption due to encrypted values)
        # But with our mock, we can test the query structure
        first_user = db_session.query(TestUser).filter(TestUser.id == users[0].id).first()
        assert first_user.email == "user1@example.com"
        
        # Test ordering
        ordered_users = db_session.query(TestUser).order_by(TestUser.id).all()
        assert len(ordered_users) == 3
        
        # Test counting
        user_count = db_session.query(TestUser).count()
        assert user_count == 3

    def test_update_operations(self, db_session, tenant_context, mock_encryption_service):
        """Test update operations with encrypted data."""
        # Create test user
        user = TestUser(
            email="original@example.com",
            first_name="Original",
            last_name="Name"
        )
        
        db_session.add(user)
        db_session.commit()
        
        # Update encrypted fields
        user.email = "updated@example.com"
        user.first_name = "Updated"
        db_session.commit()
        
        # Verify updates
        retrieved_user = db_session.query(TestUser).filter(TestUser.id == user.id).first()
        assert retrieved_user.email == "updated@example.com"
        assert retrieved_user.first_name == "Updated"
        assert retrieved_user.last_name == "Name"  # Unchanged

    def test_delete_operations(self, db_session, tenant_context, mock_encryption_service):
        """Test delete operations with encrypted data."""
        # Create test user
        user = TestUser(
            email="delete@example.com",
            first_name="Delete",
            last_name="Me"
        )
        
        db_session.add(user)
        db_session.commit()
        user_id = user.id
        
        # Delete user
        db_session.delete(user)
        db_session.commit()
        
        # Verify deletion
        deleted_user = db_session.query(TestUser).filter(TestUser.id == user_id).first()
        assert deleted_user is None

    def test_tenant_isolation(self, db_session, mock_encryption_service):
        """Test that different tenants produce different encrypted data."""
        # Test with tenant 1
        set_tenant_context(1)
        user1 = TestUser(email="test@example.com", first_name="John")
        db_session.add(user1)
        db_session.commit()
        
        # Test with tenant 2
        set_tenant_context(2)
        user2 = TestUser(email="test@example.com", first_name="John")
        db_session.add(user2)
        db_session.commit()
        
        # Verify different encrypted values in database
        raw_results = db_session.execute(
            "SELECT id, email, first_name FROM test_users ORDER BY id"
        ).fetchall()
        
        assert len(raw_results) == 2
        assert raw_results[0][1] != raw_results[1][1]  # Different encrypted emails
        assert raw_results[0][2] != raw_results[1][2]  # Different encrypted first names
        
        clear_tenant_context()

    def test_missing_tenant_context_error(self, db_session, mock_encryption_service):
        """Test error handling when tenant context is missing."""
        clear_tenant_context()
        
        # Mock encryption service to raise error for missing context
        mock_encryption_service.encrypt_data.side_effect = EncryptionError("Tenant context required")
        
        user = TestUser(email="test@example.com", first_name="John")
        db_session.add(user)
        
        # Should raise error when trying to commit
        with pytest.raises(EncryptionError, match="Tenant context required"):
            db_session.commit()

    def test_decryption_error_handling(self, db_session, tenant_context, mock_encryption_service):
        """Test handling of decryption errors."""
        # Create user normally
        user = TestUser(email="test@example.com", first_name="John")
        db_session.add(user)
        db_session.commit()
        
        # Mock decryption to fail
        mock_encryption_service.decrypt_data.side_effect = DecryptionError("Decryption failed")
        
        # Should raise error when trying to access encrypted field
        with pytest.raises(DecryptionError, match="Decryption failed"):
            retrieved_user = db_session.query(TestUser).filter(TestUser.id == user.id).first()
            _ = retrieved_user.email  # This should trigger decryption

    def test_bulk_operations(self, db_session, tenant_context, mock_encryption_service):
        """Test bulk operations with encrypted data."""
        # Create multiple users
        users = []
        for i in range(10):
            user = TestUser(
                email=f"user{i}@example.com",
                first_name=f"User{i}",
                last_name="Bulk"
            )
            users.append(user)
        
        # Bulk insert
        db_session.add_all(users)
        db_session.commit()
        
        # Verify all users were created
        user_count = db_session.query(TestUser).count()
        assert user_count == 10
        
        # Bulk update
        db_session.query(TestUser).update({"last_name": "Updated"})
        db_session.commit()
        
        # Verify updates
        updated_users = db_session.query(TestUser).all()
        for user in updated_users:
            assert user.last_name == "Updated"

    def test_transaction_rollback(self, db_session, tenant_context, mock_encryption_service):
        """Test transaction rollback with encrypted data."""
        # Create initial user
        user1 = TestUser(email="user1@example.com", first_name="User1")
        db_session.add(user1)
        db_session.commit()
        
        # Start transaction that will be rolled back
        try:
            user2 = TestUser(email="user2@example.com", first_name="User2")
            db_session.add(user2)
            
            # Simulate error after adding user2
            raise Exception("Simulated error")
            
        except Exception:
            db_session.rollback()
        
        # Verify only user1 exists
        users = db_session.query(TestUser).all()
        assert len(users) == 1
        assert users[0].email == "user1@example.com"


class TestColumnEncryptorUtilities:
    """Test utility functions for column encryption."""

    def test_create_encrypted_string_column(self):
        """Test encrypted string column creation utility."""
        column = create_encrypted_string_column(length=255, nullable=False)
        
        assert isinstance(column, EncryptedColumn)
        assert column.nullable is False
        assert column.info.get('original_max_length') == 255

    def test_create_encrypted_json_column(self):
        """Test encrypted JSON column creation utility."""
        column = create_encrypted_json_column(nullable=True)
        
        assert isinstance(column, EncryptedJSON)
        assert column.nullable is True

    def test_is_encrypted_data(self):
        """Test encrypted data detection utility."""
        # Test with base64 encoded data (simulating encrypted data)
        import base64
        encrypted_like = base64.b64encode(b"this is encrypted data with nonce").decode('ascii')
        assert is_encrypted_data(encrypted_like) is True
        
        # Test with regular string
        assert is_encrypted_data("regular string") is False
        
        # Test with short string
        assert is_encrypted_data("short") is False
        
        # Test with None/empty
        assert is_encrypted_data(None) is False
        assert is_encrypted_data("") is False

    def test_get_encryption_metadata(self):
        """Test encryption metadata utility."""
        # Test with encrypted string column
        string_column = EncryptedColumn()
        metadata = get_encryption_metadata(string_column)
        
        assert metadata['is_encrypted'] is True
        assert metadata['encryption_type'] == 'string'
        assert metadata['supports_indexing'] is False
        
        # Test with encrypted JSON column
        json_column = EncryptedJSON()
        metadata = get_encryption_metadata(json_column)
        
        assert metadata['is_encrypted'] is True
        assert metadata['encryption_type'] == 'json'
        assert metadata['supports_indexing'] is False
        
        # Test with regular column
        regular_column = Column(String)
        metadata = get_encryption_metadata(regular_column)
        
        assert metadata['is_encrypted'] is False
        assert metadata['encryption_type'] is None
        assert metadata['supports_indexing'] is False


class TestEncryptedModelsPerformance:
    """Performance tests for encrypted models."""

    @pytest.fixture
    def db_session(self):
        """Create database session for performance testing."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    @pytest.fixture
    def tenant_context(self):
        """Set up tenant context for performance testing."""
        tenant_id = 1
        set_tenant_context(tenant_id)
        yield tenant_id
        clear_tenant_context()

    @pytest.fixture
    def mock_encryption_service(self):
        """Mock encryption service for performance testing."""
        with patch('api.utils.column_encryptor.get_encryption_service') as mock_get_service:
            mock_service = Mock(spec=EncryptionService)
            
            # Simple mock that just adds prefix/suffix
            mock_service.encrypt_data.side_effect = lambda data, tenant_id: f"enc_{data}"
            mock_service.decrypt_data.side_effect = lambda data, tenant_id: data[4:] if data.startswith("enc_") else data
            mock_service.encrypt_json.side_effect = lambda data, tenant_id: f"enc_json_{json.dumps(data)}"
            mock_service.decrypt_json.side_effect = lambda data, tenant_id: json.loads(data[9:]) if data.startswith("enc_json_") else {}
            
            mock_get_service.return_value = mock_service
            yield mock_service

    @pytest.mark.slow
    def test_large_dataset_operations(self, db_session, tenant_context, mock_encryption_service):
        """Test operations with large datasets."""
        import time
        
        # Create large number of users
        start_time = time.time()
        users = []
        for i in range(1000):
            user = TestUser(
                email=f"user{i}@example.com",
                first_name=f"FirstName{i}",
                last_name=f"LastName{i}",
                phone=f"555-{i:04d}"
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        creation_time = time.time() - start_time
        
        # Query all users
        start_time = time.time()
        all_users = db_session.query(TestUser).all()
        query_time = time.time() - start_time
        
        assert len(all_users) == 1000
        
        # Log performance metrics (in real tests, you might want to assert thresholds)
        print(f"Created 1000 encrypted users in {creation_time:.2f} seconds")
        print(f"Queried 1000 encrypted users in {query_time:.2f} seconds")
        
        # Verify encryption was called for each field
        expected_calls = 1000 * 4  # 4 encrypted fields per user
        assert mock_encryption_service.encrypt_data.call_count == expected_calls

    def test_complex_json_performance(self, db_session, tenant_context, mock_encryption_service):
        """Test performance with complex JSON data."""
        import time
        
        # Create complex JSON structure
        complex_data = {
            "user_preferences": {
                "theme": "dark",
                "language": "en",
                "notifications": {
                    "email": True,
                    "sms": False,
                    "push": True
                }
            },
            "permissions": ["read", "write", "admin"],
            "metadata": {
                "last_login": "2023-01-01T00:00:00Z",
                "login_count": 42,
                "features": {
                    "beta_features": True,
                    "experimental": False
                }
            },
            "custom_fields": [
                {"name": "field1", "value": "value1", "type": "string"},
                {"name": "field2", "value": 123, "type": "number"},
                {"name": "field3", "value": True, "type": "boolean"}
            ]
        }
        
        # Create invoices with complex JSON
        start_time = time.time()
        invoices = []
        for i in range(100):
            invoice = TestInvoice(
                number=f"INV-{i:04d}",
                amount=1000.00 + i,
                notes=f"Complex invoice {i}",
                custom_fields=complex_data,
                client_info={"client_id": i, "name": f"Client {i}"}
            )
            invoices.append(invoice)
        
        db_session.add_all(invoices)
        db_session.commit()
        
        creation_time = time.time() - start_time
        
        # Query and access JSON data
        start_time = time.time()
        all_invoices = db_session.query(TestInvoice).all()
        for invoice in all_invoices:
            # Access JSON fields to trigger decryption
            _ = invoice.custom_fields
            _ = invoice.client_info
        
        query_time = time.time() - start_time
        
        assert len(all_invoices) == 100
        
        print(f"Created 100 invoices with complex JSON in {creation_time:.2f} seconds")
        print(f"Queried and decrypted 100 invoices in {query_time:.2f} seconds")


class TestMigrationSupport:
    """Test migration scenarios for encrypted columns."""

    @pytest.fixture
    def db_session(self):
        """Create database session for migration testing."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_data_integrity_after_encryption_migration(self, db_session):
        """Test data integrity when migrating from unencrypted to encrypted columns."""
        # This test simulates a migration scenario where we have existing unencrypted data
        # and need to encrypt it
        
        # First, insert data directly (simulating pre-encryption state)
        db_session.execute(
            "INSERT INTO test_users (email, first_name, last_name, is_active) VALUES (?, ?, ?, ?)",
            ("test@example.com", "John", "Doe", True)
        )
        db_session.commit()
        
        # Now set tenant context and try to read through encrypted model
        set_tenant_context(1)
        
        with patch('api.utils.column_encryptor.get_encryption_service') as mock_get_service:
            mock_service = Mock(spec=EncryptionService)
            
            # Mock decryption to handle both encrypted and unencrypted data
            def smart_decrypt(data, tenant_id):
                if data and data.startswith("encrypted_"):
                    return data[10:-2]  # Remove encryption markers
                return data  # Return as-is for unencrypted data
            
            mock_service.decrypt_data.side_effect = smart_decrypt
            mock_get_service.return_value = mock_service
            
            # Should be able to read existing unencrypted data
            user = db_session.query(TestUser).first()
            assert user.email == "test@example.com"
            assert user.first_name == "John"
            assert user.last_name == "Doe"
        
        clear_tenant_context()

    def test_rollback_migration_scenario(self, db_session):
        """Test rollback scenario from encrypted to unencrypted columns."""
        set_tenant_context(1)
        
        with patch('api.utils.column_encryptor.get_encryption_service') as mock_get_service:
            mock_service = Mock(spec=EncryptionService)
            mock_service.encrypt_data.side_effect = lambda data, tenant_id: f"encrypted_{data}_{tenant_id}"
            mock_service.decrypt_data.side_effect = lambda data, tenant_id: data[10:-2] if data.startswith("encrypted_") else data
            mock_get_service.return_value = mock_service
            
            # Create encrypted user
            user = TestUser(email="test@example.com", first_name="John")
            db_session.add(user)
            db_session.commit()
            
            # Verify data is encrypted in database
            raw_result = db_session.execute(
                "SELECT email, first_name FROM test_users WHERE id = ?",
                (user.id,)
            ).fetchone()
            
            assert raw_result[0] == "encrypted_test@example.com_1"
            assert raw_result[1] == "encrypted_John_1"
        
        clear_tenant_context()