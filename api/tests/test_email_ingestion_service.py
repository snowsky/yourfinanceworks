import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timezone, timedelta
from services.email_ingestion_service import EmailIngestionService
from models.models_per_tenant import Settings, Expense
from constants.expense_status import ExpenseStatus

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    return EmailIngestionService(mock_db, user_id=1, tenant_id=1)

def test_validate_config_success(service):
    config = {
        "imap_host": "imap.test.com",
        "imap_port": 993,
        "username": "test@test.com",
        "password": "password"
    }
    
    with patch("imaplib.IMAP4_SSL") as mock_imap:
        mock_instance = mock_imap.return_value
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        
        is_valid, message = service.validate_config(config)
        
        assert is_valid is True
        assert message == "Connection successful"
        mock_imap.assert_called_with("imap.test.com", 993, ssl_context=ANY)
        mock_instance.login.assert_called_with("test@test.com", "password")

def test_validate_config_failure(service):
    config = {
        "imap_host": "imap.test.com",
        "imap_port": 993,
        "username": "test@test.com",
        "password": "password"
    }
    
    with patch("imaplib.IMAP4_SSL") as mock_imap:
        mock_imap.side_effect = Exception("Connection failed")
        
        is_valid, message = service.validate_config(config)
        
        assert is_valid is False
        assert "Connection failed" in message

def test_sync_emails_disabled(service, mock_db):
    # Mock settings to return disabled config
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        value={"enabled": False}
    )
    # Re-init service to pick up settings (or mock _get_settings)
    service.settings = {"enabled": False}
    
    result = service.sync_emails()
    assert result == {"downloaded": 0, "processed": 0}

@patch("services.email_ingestion_service.EmailIngestionService._connect")
def test_sync_emails_success(mock_connect, service, mock_db):
    service.settings = {
        "enabled": True,
        "imap_host": "imap.test.com",
        "username": "test",
        "password": "pw",
        "folders": ["INBOX"]
    }
    
    mock_mail = MagicMock()
    mock_connect.return_value = mock_mail
    
    # Mock search response
    mock_mail.search.return_value = ("OK", [b"1 2"])
    
    # Mock DB query to return None (email doesn't exist)
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    # Mock fetch response
    # We need to construct a valid raw email bytes
    from email.mime.text import MIMEText
    msg = MIMEText("Test body")
    msg["Subject"] = "Test Subject"
    msg["From"] = "sender@example.com"
    msg["Date"] = "Wed, 25 Nov 2025 12:00:00 +0000"
    msg["Message-ID"] = "<test-id@example.com>"
    raw_email = msg.as_bytes()
    
    # Mock side_effect for fetch to handle both header and body requests
    def fetch_side_effect(email_id, part):
        if "HEADER" in part:
            return ("OK", [(b"1 (BODY.PEEK[HEADER] {100})", raw_email)])
        return ("OK", [(b"1 (RFC822 {100})", raw_email)])
        
    mock_mail.fetch.side_effect = fetch_side_effect
    
    result = service.sync_emails()
    
    assert result["downloaded"] == 2 # 2 emails downloaded
    assert result["downloaded"] == 2
    
    # Verify search was called with SINCE criteria
    # We default to 7 days lookback (not 30 as comment said)
    from datetime import datetime, timedelta
    expected_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%d-%b-%Y")
    mock_mail.search.assert_called_with(None, f'(SINCE "{expected_date}")')
    
    # Verify expense creation
    assert mock_db.add.call_count == 2
    # Verify commit
    assert mock_db.commit.call_count == 2

@patch("services.email_ingestion_service.EmailIngestionService._connect")
def test_sync_emails_filtered_sender(mock_connect, service, mock_db):
    service.settings = {
        "enabled": True,
        "imap_host": "imap.test.com",
        "username": "test",
        "password": "pw",
        "folders": ["INBOX"],
        "allowed_senders": "allowed@example.com"
    }
    
    mock_mail = MagicMock()
    mock_connect.return_value = mock_mail
    mock_mail.search.return_value = ("OK", [b"1"])
    
    # Email from blocked sender
    from email.mime.text import MIMEText
    msg = MIMEText("Test body")
    msg["Subject"] = "Test Subject"
    msg["From"] = "blocked@example.com"
    raw_email = msg.as_bytes()
    
    msg["Message-ID"] = "<blocked-id@example.com>"
    raw_email = msg.as_bytes()
    
    # Mock side_effect for fetch to handle both header and body requests
    def fetch_side_effect(email_id, part):
        if "HEADER" in part:
            return ("OK", [(b"1 (BODY.PEEK[HEADER] {100})", raw_email)])
        return ("OK", [(b"1 (RFC822 {100})", raw_email)])
        
    mock_mail.fetch.side_effect = fetch_side_effect
    
    result = service.sync_emails()
    
    assert result["processed"] == 0
    assert mock_db.add.call_count == 0
