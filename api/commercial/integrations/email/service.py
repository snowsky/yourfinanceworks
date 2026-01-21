import imaplib
import email
from email.header import decode_header
import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
import os
import json
import ssl
import time
from sqlalchemy.orm import Session
from core.models.models_per_tenant import Settings, Expense, ExpenseAttachment
from commercial.ai.services.ocr_service import _run_ocr, queue_or_process_attachment
from core.services.currency_service import CurrencyService
from core.services.inventory_service import InventoryService
from core.services.inventory_integration_service import InventoryIntegrationService
from commercial.ai_expense.services.email_classification_service import EmailClassificationService
from commercial.ai.services.ai_config_service import AIConfigService
from core.constants.expense_status import ExpenseStatus
import tempfile
import mimetypes

logger = logging.getLogger(__name__)

class EmailIngestionService:
    def __init__(self, db: Session, user_id: int, tenant_id: int):
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.settings = self._get_settings()

    def _get_settings(self) -> Optional[Dict[str, Any]]:
        setting = self.db.query(Settings).filter(Settings.key == "email_integration_config").first()
        if setting:
            return setting.value
        return None

    def _get_last_sync_state(self) -> Optional[Dict[str, Any]]:
        """Get the last successful email sync state (timestamp and last UIDs)."""
        setting = self.db.query(Settings).filter(Settings.key == "last_email_sync").first()
        if setting and setting.value:
            return setting.value
        return None

    def _update_last_sync_state(self, timestamp: datetime, last_uids: Dict[str, int]):
        """Update the last successful email sync state."""
        setting = self.db.query(Settings).filter(Settings.key == "last_email_sync").first()

        # Preserve existing UIDs for folders not in the current sync
        if setting and setting.value and setting.value.get("last_uids"):
            existing_uids = setting.value.get("last_uids", {})
            existing_uids.update(last_uids)
            last_uids = existing_uids

        new_state = {
            "timestamp": timestamp.isoformat(),
            "last_uids": last_uids
        }

        if not setting:
            setting = Settings(
                key="last_email_sync",
                value=new_state,
                category="system",
                description="Last successful email sync state (timestamp and UIDs)"
            )
            self.db.add(setting)
        else:
            setting.value = new_state
        self.db.commit()

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        required_fields = ["imap_host", "imap_port", "username", "password"]
        for field in required_fields:
            if not config.get(field):
                return False, f"Missing required field: {field}"
        
        try:
            self._connect(config)
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

    def _update_sync_status(self, status: str, message: str, downloaded: int = 0, processed: int = 0):
        try:
            # Re-query settings to avoid stale state if possible, or just update
            setting = self.db.query(Settings).filter(Settings.key == "email_sync_status").first()
            status_data = {
                "status": status,
                "message": message,
                "downloaded": downloaded,
                "processed": processed,
                "timestamp": datetime.now().isoformat()
            }
            
            if not setting:
                setting = Settings(
                    key="email_sync_status",
                    value=status_data,
                    category="system",
                    description="Status of email synchronization"
                )
                self.db.add(setting)
            else:
                # Merge with existing to preserve counts if not provided
                current = setting.value or {}
                # If we are just updating message/status, keep counts
                if downloaded == 0 and "downloaded" in current and status != "starting":
                    status_data["downloaded"] = current["downloaded"]
                if processed == 0 and "processed" in current and status != "starting":
                    status_data["processed"] = current["processed"]
                
                setting.value = status_data
            
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update sync status: {e}")
            # Don't rollback main transaction if status update fails
            # But we need to be careful about transaction state
            pass

    def _connect(self, config: Dict[str, Any]) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server with SSL context configuration."""
        host = config.get("imap_host")
        port = int(config.get("imap_port", 993))
        username = config.get("username")
        password = config.get("password")
        verify_ssl = config.get("verify_ssl", True)  # Default to True for security

        # Create SSL context with configurable verification
        ssl_context = ssl.create_default_context()
        
        if not verify_ssl:
            # Disable SSL verification (NOT RECOMMENDED for production)
            logger.warning(f"SSL verification disabled for {host} - this is insecure!")
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        else:
            # Standard SSL verification
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # Set minimum TLS version (try TLS 1.0 for compatibility with older servers)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1
        
        try:
            mail = imaplib.IMAP4_SSL(host, port, ssl_context=ssl_context)
            mail.login(username, password)
            logger.info(f"Successfully connected to IMAP server {host}:{port}")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server {host}:{port}: {e}")
            raise

    def sync_emails(self) -> Dict[str, int]:
        """
        Public method to trigger sync.
        Downloads emails to RawEmail table.
        Returns stats.
        """
        self._update_sync_status("running", "Starting sync...", 0, 0)

        if not self.settings or not self.settings.get("enabled", False):
            self._update_sync_status("completed", "Email integration disabled", 0, 0)
            return {"downloaded": 0, "processed": 0}

        config = self.settings
        
        try:
            # 1. Poll and save to RawEmail
            self._update_sync_status("running", "Scanning for new emails...", 0, 0)
            downloaded = self.poll_and_save(config)
            
            # 2. Trigger processing of pending emails (optional, can be left to worker)
            # For "Sync Now" UX, we might want to process immediately or return "Queued"
            # Let's process a small batch immediately to give feedback
            self._update_sync_status("running", f"Downloaded {downloaded} emails. Processing...", downloaded, 0)
            processed = self.process_pending_emails(limit=5)
            
            self._update_sync_status("completed", "Sync complete", downloaded, processed)
            return {"downloaded": downloaded, "processed": processed}
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self._update_sync_status("failed", f"Sync failed: {str(e)}")
            raise e

    def poll_and_save(self, config: Dict[str, Any]) -> int:
        """Connect to IMAP and save new emails to the database using UID-based sync."""
        count = 0
        consecutive_errors = 0
        max_consecutive_errors = 10
        new_last_uids = {}

        try:
            mail = self._connect(config)
            folders = config.get("folders", ["INBOX"])
            allowed_senders = [s.strip().lower() for s in config.get("allowed_senders", "").split(",") if s.strip()]
            lookback_days = config.get("lookback_days", 7)
            max_emails_to_fetch = config.get("max_emails_to_fetch", 100)

            logger.info(f"[CONFIG] Email sync using UID-based strategy. Folders: {folders}, Lookback: {lookback_days} days, Max Fetch: {max_emails_to_fetch}")

            last_sync_state = self._get_last_sync_state()
            sync_start_time = datetime.now(timezone.utc)
            last_uids = (last_sync_state or {}).get("last_uids", {})

            for folder in folders:
                max_uid_in_folder = 0
                try:
                    mail.select(f'"{folder}"')
                    
                    last_uid = last_uids.get(folder)
                    search_criteria = ''

                    if last_uid:
                        search_criteria = f"UID {last_uid}:*"
                        logger.info(f"Searching folder '{folder}' for emails with UID > {last_uid}")
                    else:
                        # Fallback to date-based search for the first sync of a folder
                        since_date = (sync_start_time - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
                        search_criteria = f'SINCE "{since_date}"'
                        logger.info(f"No last UID for folder '{folder}'. Searching for emails since {since_date}.")

                    status, messages = mail.uid('search', None, search_criteria)
                    if status != "OK":
                        logger.warning(f"Failed to search folder '{folder}'")
                        continue

                    uids = messages[0].split()
                    total_emails = len(uids)
                    logger.info(f"Found {total_emails} new emails in folder '{folder}'")

                    if total_emails > max_emails_to_fetch:
                        logger.info(f"Limiting to {max_emails_to_fetch} most recent emails (out of {total_emails})")
                        uids = uids[-max_emails_to_fetch:]
                    
                    skipped_existing = 0

                    for idx, uid in enumerate(uids):
                        max_uid_in_folder = max(max_uid_in_folder, int(uid))
                        try:
                            if idx % 10 == 0:
                                self._update_sync_status("running", f"Processing email {idx + 1}/{len(uids)} in '{folder}'...", count, 0)
                            
                            if idx > 0 and idx % 5 == 0:
                                time.sleep(0.5)

                            # Fetch headers first to check Message-ID and get UID
                            res, header_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER])')
                            if res != "OK":
                                logger.warning(f"Failed to fetch headers for email UID {uid}")
                                consecutive_errors += 1
                                if consecutive_errors >= max_consecutive_errors:
                                    raise Exception(f"Too many consecutive errors, aborting sync")
                                continue

                            msg_header = email.message_from_bytes(header_data[0][1])
                            message_id = msg_header.get("Message-ID")

                            # Check if email already exists by Message-ID
                            if message_id:
                                from core.models.models_per_tenant import RawEmail
                                if self.db.query(RawEmail).filter(RawEmail.message_id == message_id).first():
                                    logger.debug(f"Email with Message-ID {message_id} (UID {uid}) already exists, skipping.")
                                    skipped_existing += 1
                                    continue

                            sender = email.utils.parseaddr(msg_header.get("From", ""))[1].lower()
                            if allowed_senders and sender not in allowed_senders:
                                logger.info(f"Email UID {uid} from '{sender}' filtered by sender list.")
                                continue

                            # Fetch full body
                            res, msg_data = mail.uid('fetch', uid, "(RFC822)")
                            if res != "OK":
                                logger.warning(f"Failed to fetch body for email UID {uid}")
                                continue

                            raw_content = msg_data[0][1]
                            self._save_raw_email(email.message_from_bytes(raw_content), raw_content, message_id, int(uid))
                            count += 1
                            consecutive_errors = 0

                        except (imaplib.IMAP4.abort, ssl.SSLError) as e:
                            logger.error(f"Connection error processing email UID {uid}: {e}")
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                raise Exception(f"Too many consecutive connection errors, aborting sync.")
                            try:
                                mail.logout()
                            except: pass
                            time.sleep(5)
                            mail = self._connect(config)
                            mail.select(f'"{folder}"')
                        except Exception as e:
                            logger.error(f"Error processing email UID {uid}: {e}", exc_info=True)
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                raise Exception(f"Too many consecutive errors, aborting sync.")

                except Exception as e:
                    logger.error(f"Error processing folder '{folder}': {e}", exc_info=True)
                    raise

                if max_uid_in_folder > 0:
                    new_last_uids[folder] = max_uid_in_folder

                logger.info(f"[SUMMARY] Folder '{folder}': Found={total_emails}, Processed={count}, Skipped={skipped_existing}")

            try:
                mail.logout()
            except:
                pass

        except Exception as e:
            logger.error(f"Error in poll_and_save: {e}", exc_info=True)
            raise

        if new_last_uids:
            try:
                self._update_last_sync_state(sync_start_time, new_last_uids)
                logger.info(f"Updated last sync state. Timestamp: {sync_start_time.isoformat()}, New UIDs: {new_last_uids}")
            except Exception as e:
                logger.warning(f"Failed to update last sync state: {e}")

        return count

    def _save_raw_email(self, msg, raw_bytes: bytes, message_id: str, uid: int):
        try:
            from core.models.models_per_tenant import RawEmail

            subject = self._decode_header(msg.get("Subject", ""))
            sender = msg.get("From")
            recipient = msg.get("To")

            date_tuple = email.utils.parsedate_tz(msg.get("Date"))
            if date_tuple:
                email_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            else:
                email_date = datetime.now()

            try:
                raw_content_str = raw_bytes.decode('utf-8', errors='replace')
            except:
                raw_content_str = str(raw_bytes)

            raw_email = RawEmail(
                uid=uid,
                message_id=message_id,
                subject=subject,
                sender=sender,
                recipient=recipient,
                date=email_date,
                raw_content=raw_content_str,
                status="pending"
            )
            self.db.add(raw_email)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save raw email: {e}")
            self.db.rollback()

    def process_pending_emails(self, limit: int = 10) -> int:
        """Process pending RawEmails into Expenses with AI classification."""
        from core.models.models_per_tenant import RawEmail
        from sqlalchemy import or_

        # Include both pending and failed emails (with retry limit)
        pending_emails = self.db.query(RawEmail).filter(
            or_(
                RawEmail.status == "pending",
                (RawEmail.status == "failed") & (RawEmail.retry_count < 3)
            )
        ).limit(limit).all()

        # Get allowed senders from core.settings
        allowed_senders = [s.strip().lower() for s in self.settings.get("allowed_senders", "").split(",") if s.strip()] if self.settings else []

        logger.info(f"[PROCESS] Found {len(pending_emails)} pending/failed emails to process (limit={limit})")

        count = 0
        for raw_email in pending_emails:
            try:
                # Check sender filter before processing
                sender = email.utils.parseaddr(raw_email.sender or "")[1].lower() if raw_email.sender else ""
                logger.debug(f"[DEBUG] Processing email {raw_email.id}: subject='{raw_email.subject}', sender='{sender}'")

                if allowed_senders and sender not in allowed_senders:
                    logger.info(f"[FILTER] Email {raw_email.id} filtered by sender in process_pending: '{sender}' not in {allowed_senders}")
                    raw_email.status = "ignored"
                    raw_email.error_message = f"Sender '{sender}' not in allowed list"
                    self.db.commit()
                    continue

                raw_email.status = "processing"
                self.db.commit()

                # Parse email
                msg = email.message_from_string(raw_email.raw_content)

                # Extract body for classification
                body = self._extract_body_text(msg)

                logger.info(f"[DEBUG] Processing email {raw_email.id}: subject='{raw_email.subject}', sender='{sender}'")

                # Check if AI classification is enabled
                enable_ai = self.settings.get("enable_ai_classification", True) if self.settings else True

                if enable_ai:
                    # Classify email using AI
                    logger.info(f"[DEBUG] Starting AI classification for email {raw_email.id}")
                    classification = asyncio.run(
                        self._classify_email_async(raw_email.subject or "", body, raw_email.sender or "", msg)
                    )
                    logger.info(f"[DEBUG] Classification result for email {raw_email.id}: is_expense={classification['is_expense']}, confidence={classification['confidence']}, reasoning='{classification['reasoning']}'")

                    # Check confidence threshold
                    min_confidence = self.settings.get("min_confidence_threshold", 0.7) if self.settings else 0.7

                    if not classification["is_expense"] or classification["confidence"] < min_confidence:
                        # Not an expense, mark as ignored
                        raw_email.status = "ignored"
                        raw_email.error_message = f"Not classified as expense: {classification['reasoning']}"
                        self.db.commit()
                        logger.info(f"Email {raw_email.id} ignored: {classification['reasoning']}")
                        continue

                # Create expense with AI extraction
                # Ensure tenant context is set for encryption
                from core.models.database import set_tenant_context
                set_tenant_context(self.tenant_id)

                self._create_expense_from_email(msg, raw_email, body)

                raw_email.status = "processed"
                raw_email.processed_at = datetime.now(timezone.utc)
                self.db.commit()
                count += 1

                # Delete if configured
                if self.settings and self.settings.get("delete_processed", False):
                    self.db.delete(raw_email)
                    self.db.commit()

            except Exception as e:
                logger.error(f"Failed to process raw email {raw_email.id}: {e}", exc_info=True)
                # Rollback the failed transaction
                self.db.rollback()
                raw_email.status = "failed"
                raw_email.error_message = str(e)
                raw_email.retry_count += 1
                self.db.commit()

        return count

    async def _classify_email_async(self, subject: str, body: str, sender: str, msg) -> Dict[str, Any]:
        """Classify email using AI."""
        has_attachments = any(part.get_filename() for part in msg.walk() if part.get_content_maintype() != 'multipart')

        classifier = EmailClassificationService(self.db)
        return await classifier.classify_email(subject, body, sender, has_attachments)

    def _extract_body_text(self, msg) -> str:
        """Extract plain text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if "attachment" not in str(part.get("Content-Disposition", "")):
                    if content_type == "text/plain":
                        try:
                            body += part.get_payload(decode=True).decode(errors="ignore")
                        except:
                            pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(errors="ignore")
            except:
                body = str(msg.get_payload())
        return body

    async def _extract_expense_from_body_async(self, subject: str, body: str) -> Dict[str, Any]:
        """Extract expense data from email body using AI."""
        try:
            # Get AI configuration
            ai_config = AIConfigService.get_ai_config(self.db, "ocr")
            if not ai_config:
                logger.warning("No AI config available for expense extraction")
                return {}

            # Build extraction prompt
            prompt = f"""Extract expense/receipt information from this email.

Subject: {subject}
Body:
{body[:2000]}

Extract the following fields if present:
- amount: numeric value only
- currency: 3-letter code (USD, EUR, etc.)
- expense_date: YYYY-MM-DD format
- vendor: merchant/store name
- category: expense category (e.g., Food, Transportation, Shopping, etc.)

Respond with ONLY valid JSON:
{{
  "amount": number or null,
  "currency": "USD" or null,
  "expense_date": "YYYY-MM-DD" or null,
  "vendor": "string" or null,
  "category": "string" or null
}}"""

            # Call LLM
            from litellm import completion

            provider_name = ai_config.get("provider_name", "ollama")
            model_name = ai_config.get("model_name")

            if provider_name == "ollama":
                model = f"ollama/{model_name}"
                api_base = ai_config.get("provider_url", "http://localhost:11434")
            elif provider_name == "openai":
                model = model_name
                api_base = ai_config.get("provider_url", "https://api.openai.com/v1")
            else:
                model = f"{provider_name}/{model_name}"
                api_base = ai_config.get("provider_url")

            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 300,
            }

            if api_base:
                kwargs["api_base"] = api_base
            if ai_config.get("api_key"):
                kwargs["api_key"] = ai_config["api_key"]

            # Run in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: completion(**kwargs))

            # Parse response
            content = response.choices[0].message.content.strip()
            result = self._extract_json_from_llm_response(content)

            if result:
                # Parse date if present
                if result.get("expense_date"):
                    try:
                        result["expense_date"] = datetime.strptime(result["expense_date"], "%Y-%m-%d")
                    except:
                        result["expense_date"] = None
                
                logger.info(f"Extracted expense data: {result}")
                return result

            return {}

        except Exception as e:
            logger.error(f"Expense extraction from body failed: {e}", exc_info=True)
            return {}

    async def _extract_from_pdf_async(self, pdf_path: str) -> Dict[str, Any]:
        """Extract expense data from PDF attachment using OCR."""
        try:
            # Get AI configuration
            ai_config = AIConfigService.get_ai_config(self.db, "ocr")
            if not ai_config:
                logger.warning("No AI config available for PDF extraction")
                return {}

            # Use the same OCR service as direct PDF uploads
            extracted_data = await _run_ocr(pdf_path, ai_config=ai_config)

            logger.info(f"Extracted data from PDF: {extracted_data}")
            return extracted_data

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}", exc_info=True)
            return {}
    
    def _extract_json_from_llm_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response."""
        import re

        # Remove markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except:
            pass

        # Find JSON object
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except:
                pass

        return None
    
    def _create_expense_from_email(self, msg, raw_email, body: str = None) -> Expense:
        """Create expense from email with AI-powered extraction."""
        subject = self._decode_header(msg.get("Subject", ""))

        # Extract body if not provided
        if body is None:
            body = self._extract_body_text(msg)

        # Try AI extraction from email body
        expense_data = asyncio.run(self._extract_expense_from_body_async(subject, body))

        # Create expense with extracted data or defaults
        expense = Expense(
            user_id=self.user_id,
            status=ExpenseStatus.RECORDED.value,
            expense_date=expense_data.get("expense_date") or raw_email.date or datetime.now(),
            category=expense_data.get("category") or "Uncategorized",
            vendor=expense_data.get("vendor"),
            amount=expense_data.get("amount"),
            currency=expense_data.get("currency") or "USD",
            notes=f"Imported from email.\nSubject: {subject}\nSender: {raw_email.sender}\n\n{body[:500]}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            analysis_status="queued" if expense_data.get("has_attachments") else "done"
        )
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)

        # Trigger gamification event for expense creation
        try:
            from core.services.tenant_database_manager import tenant_db_manager
            from core.services.financial_event_processor import create_financial_event_processor

            self.logger.info(f"STEP: Processing gamification for email expense {expense.id}")

            # Get tenant database session for gamification
            tenant_session = tenant_db_manager.get_tenant_session(self.tenant_id)

            event_processor = create_financial_event_processor(tenant_session)
            gamification_result = asyncio.run(event_processor.process_expense_added(
                user_id=self.user_id,
                expense_id=expense.id,
                expense_data={
                    "amount": float(expense.amount) if expense.amount else 0,
                    "category": expense.category,
                    "vendor": expense.vendor,
                    "has_attachments": bool(expense.attachments)
                }
            ))

            logger.info(f"✅ STEP: Gamification processed for email expense {expense.id}")
        except Exception as e:
            logger.warning(f"Failed to process gamification for email expense {expense.id}: {e}")
            # Don't fail the expense creation if gamification processing fails

        # Link expense to raw email
        raw_email.expense_id = expense.id

        # Process attachments (will update expense with attachment data if found)
        self._process_attachments(msg, expense)

        return expense

    def _process_attachments(self, msg, expense: Expense):
        """Process email attachments and extract data from PDFs."""
        logger.info(f"[ATTACH] Processing attachments for expense {expense.id}")
        attachment_count = 0

        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()
            if filename:
                attachment_count += 1
                filename = self._decode_header(filename)
                content = part.get_payload(decode=True)
                content_type = part.get_content_type()

                logger.info(f"[ATTACH] Found attachment: {filename}, type={content_type}, size={len(content)} bytes")

                # Save attachment first
                attachment, file_path = self._save_attachment(expense, filename, content, content_type)

                # Process PDFs and images for expense data extraction
                is_pdf = content_type == 'application/pdf' or filename.lower().endswith('.pdf')
                is_image = content_type.startswith('image/') or filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))

                if is_pdf or is_image:
                    file_type = "PDF" if is_pdf else "Image"
                    logger.info(f"[{file_type}] Queuing {file_type.lower()} attachment for OCR: {filename}")
                    try:
                        # Queue OCR processing in background (Kafka or inline)
                        # We use the attachment object returned by _save_attachment
                        queue_or_process_attachment(
                            self.db,
                            self.tenant_id,
                            expense.id,
                            attachment.id,
                            file_path
                        )
                    except Exception as e:
                        logger.error(f"[{file_type}] Failed to queue OCR for {filename}: {e}")

        logger.info(f"[ATTACH] Processed {attachment_count} attachments for expense {expense.id}")

    def _decode_header(self, header_value):
        if not header_value: return ""
        decoded_list = decode_header(header_value)
        decoded_str = ""
        for bytes_str, encoding in decoded_list:
            if isinstance(bytes_str, bytes):
                if encoding:
                    try:
                        decoded_str += bytes_str.decode(encoding, errors="ignore")
                    except:
                        decoded_str += bytes_str.decode("utf-8", errors="ignore")
                else:
                    decoded_str += bytes_str.decode("utf-8", errors="ignore")
            else:
                decoded_str += str(bytes_str)
        return decoded_str

    def _save_attachment(self, expense: Expense, filename: str, content: bytes, content_type: str) -> str:
        """Save attachment to cloud storage (if enabled) or local storage, and return file path."""
        # Define local storage path
        base_path = os.getenv("STORAGE_PATH", "data")
        storage_dir = os.path.join(base_path, "tenants", str(self.tenant_id), "expenses", str(expense.id))
        os.makedirs(storage_dir, exist_ok=True)

        local_file_path = os.path.join(storage_dir, filename)

        # Always save locally first (for OCR processing)
        with open(local_file_path, "wb") as f:
            f.write(content)

        # Try to upload to cloud storage if enabled
        cloud_file_path = None
        try:
            from commercial.cloud_storage.config import get_cloud_storage_config
            cloud_config = get_cloud_storage_config()

            if cloud_config and cloud_config.enabled:
                logger.info(f"[CLOUD] Uploading attachment to cloud storage: {filename}")
                from commercial.cloud_storage.service import CloudStorageService

                cloud_storage_service = CloudStorageService(self.db, cloud_config)

                # Upload to cloud
                import asyncio
                result = asyncio.run(cloud_storage_service.store_file(
                    file_content=content,
                    tenant_id=str(self.tenant_id),
                    item_id=expense.id,
                    attachment_type="expenses",
                    original_filename=filename,
                    user_id=self.user_id,
                    metadata={
                        'source': 'email_attachment',
                        'content_type': content_type,
                        'expense_id': expense.id
                    }
                ))

                if result.success:
                    cloud_file_path = result.file_key
                    logger.info(f"[CLOUD] Successfully uploaded to cloud: {cloud_file_path}")
                else:
                    logger.warning(f"[CLOUD] Cloud upload failed: {result.error_message}, using local storage")
        except Exception as e:
            logger.warning(f"[CLOUD] Cloud storage upload failed: {e}, using local storage")

        # Create attachment record with cloud path if available
        attachment = ExpenseAttachment(
            expense_id=expense.id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            file_path=cloud_file_path or local_file_path,  # Use cloud path if available
            uploaded_by=self.user_id
        )
        self.db.add(attachment)
        self.db.commit()

        # Return both attachment and local path for OCR processing
        return attachment, local_file_path
