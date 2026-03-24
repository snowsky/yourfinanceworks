"""
Service for managing DocumentEmailReference — the junction table that links
RawEmail rows to any document type (invoice, expense, bank_statement,
investment_portfolio).
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import DocumentEmailReference, RawEmail

VALID_DOCUMENT_TYPES = frozenset(
    {"invoice", "expense", "bank_statement", "investment_portfolio"}
)


class DocumentEmailReferenceService:
    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id

    def add_reference(
        self,
        raw_email_id: int,
        document_type: str,
        document_id: int,
        link_type: str = "manual",
        notes: Optional[str] = None,
    ) -> DocumentEmailReference:
        """Create a link. Idempotent — returns existing row if already linked."""
        if document_type not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"Invalid document_type: {document_type!r}")

        existing = (
            self.db.query(DocumentEmailReference)
            .filter_by(
                raw_email_id=raw_email_id,
                document_type=document_type,
                document_id=document_id,
            )
            .first()
        )
        if existing:
            return existing

        ref = DocumentEmailReference(
            raw_email_id=raw_email_id,
            document_type=document_type,
            document_id=document_id,
            link_type=link_type,
            notes=notes,
            created_by_user_id=self.user_id,
        )
        self.db.add(ref)
        self.db.commit()
        self.db.refresh(ref)
        return ref

    def remove_reference(
        self,
        raw_email_id: int,
        document_type: str,
        document_id: int,
    ) -> bool:
        """Delete a link. Returns True if deleted, False if not found."""
        ref = (
            self.db.query(DocumentEmailReference)
            .filter_by(
                raw_email_id=raw_email_id,
                document_type=document_type,
                document_id=document_id,
            )
            .first()
        )
        if not ref:
            return False
        self.db.delete(ref)
        self.db.commit()
        return True

    def get_email_references(
        self,
        document_type: str,
        document_id: int,
    ) -> List[dict]:
        """Return all emails linked to a document, with email metadata."""
        rows = (
            self.db.query(DocumentEmailReference, RawEmail)
            .join(RawEmail, DocumentEmailReference.raw_email_id == RawEmail.id)
            .filter(
                DocumentEmailReference.document_type == document_type,
                DocumentEmailReference.document_id == document_id,
            )
            .order_by(RawEmail.date.desc())
            .all()
        )
        return [_serialize_reference(ref, email) for ref, email in rows]

    def get_documents_for_email(self, raw_email_id: int) -> List[dict]:
        """Return all documents linked to a given email."""
        refs = (
            self.db.query(DocumentEmailReference)
            .filter_by(raw_email_id=raw_email_id)
            .all()
        )
        return [_serialize_document_link(r) for r in refs]


def _serialize_reference(ref: DocumentEmailReference, email: RawEmail) -> dict:
    return {
        "reference_id": ref.id,
        "raw_email_id": email.id,
        "subject": email.subject,
        "sender": email.sender,
        "date": email.date.isoformat() if email.date else None,
        "snippet": (email.raw_content or "")[:300],
        "link_type": ref.link_type,
        "notes": ref.notes,
        "created_at": ref.created_at.isoformat() if ref.created_at else None,
    }


def _serialize_document_link(ref: DocumentEmailReference) -> dict:
    return {
        "reference_id": ref.id,
        "document_type": ref.document_type,
        "document_id": ref.document_id,
        "link_type": ref.link_type,
        "notes": ref.notes,
        "created_at": ref.created_at.isoformat() if ref.created_at else None,
    }
