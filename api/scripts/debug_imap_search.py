#!/usr/bin/env python3
"""
Debug script to test IMAP search and see what emails are actually found.
This helps diagnose why emails aren't being picked up.
"""
import sys
import os
import imaplib
import email
from datetime import datetime, timedelta, timezone
import ssl

# Add api directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imap_search(host, port, username, password, verify_ssl=True):
    """Test IMAP connection and search for recent emails."""

    print(f"\n{'='*60}")
    print(f"Testing IMAP Connection to {host}:{port}")
    print(f"{'='*60}\n")

    # Create SSL context
    ssl_context = ssl.create_default_context()
    if not verify_ssl:
        print("⚠️  SSL verification disabled")
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1

    try:
        # Connect
        print(f"Connecting to {host}:{port}...")
        mail = imaplib.IMAP4_SSL(host, port, ssl_context=ssl_context)
        
        # Login
        print(f"Logging in as {username}...")
        mail.login(username, password)
        print("✅ Login successful\n")

        # Select INBOX
        mail.select("INBOX")
        print("📬 Selected INBOX\n")

        # Test different search criteria
        test_searches = [
            ("ALL (last 10)", "ALL"),
            ("Last 24 hours", f'(SINCE "{(datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")}")'),
            ("Last 7 days", f'(SINCE "{(datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")}")'),
            ("Nov 28, 2025", '(SINCE "28-Nov-2025")'),
            ("Nov 27, 2025", '(SINCE "27-Nov-2025")'),
        ]

        for name, criteria in test_searches:
            print(f"🔍 Search: {name}")
            print(f"   Criteria: {criteria}")

            try:
                status, messages = mail.search(None, criteria)

                if status == "OK":
                    email_ids = messages[0].split()
                    count = len(email_ids)
                    print(f"   ✅ Found {count} emails")

                    # For ALL search, show details of last 10 emails
                    if criteria == "ALL" and count > 0:
                        # Get last 10 (most recent)
                        recent_ids = email_ids[-10:] if count > 10 else email_ids
                        print(f"\n   📧 Details of {len(recent_ids)} most recent emails:")

                        for idx, email_id in enumerate(reversed(recent_ids), 1):
                            try:
                                # Fetch headers
                                res, header_data = mail.fetch(email_id, '(BODY.PEEK[HEADER])')
                                if res == "OK":
                                    msg = email.message_from_bytes(header_data[0][1])

                                    subject = msg.get("Subject", "(no subject)")
                                    sender = msg.get("From", "(unknown)")
                                    date_str = msg.get("Date", "(no date)")
                                    message_id = msg.get("Message-ID", "(no ID)")

                                    print(f"\n   {idx}. Email ID: {email_id.decode()}")
                                    print(f"      From: {sender}")
                                    print(f"      Subject: {subject}")
                                    print(f"      Date: {date_str}")
                                    print(f"      Message-ID: {message_id}")
                            except Exception as e:
                                print(f"   ❌ Error fetching email {email_id}: {e}")
                else:
                    print(f"   ❌ Search failed: {status}")
            except Exception as e:
                print(f"   ❌ Error: {e}")

            print()
        
        # Logout
        mail.logout()
        print("\n✅ Test complete")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("IMAP Email Search Diagnostic Tool")
    print("="*60)

    # Get credentials from environment or prompt
    host = os.getenv("IMAP_HOST", "imap.gmail.com")
    port = int(os.getenv("IMAP_PORT", "993"))
    username = os.getenv("IMAP_USERNAME")
    password = os.getenv("IMAP_PASSWORD")

    if not username:
        username = input("Enter IMAP username/email: ")
    if not password:
        import getpass
        password = getpass.getpass("Enter IMAP password: ")

    verify_ssl = os.getenv("IMAP_VERIFY_SSL", "true").lower() != "false"

    test_imap_search(host, port, username, password, verify_ssl)
