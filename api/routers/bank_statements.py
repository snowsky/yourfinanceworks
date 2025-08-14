from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List, Dict, Any
from pathlib import Path
import os
import shutil
import uuid
import logging

from models.database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user
from models.models import MasterUser
from utils.rbac import require_non_viewer
from services.bank_statement_service import extract_transactions_from_pdf_paths
from models.models_per_tenant import BankStatement, BankStatementTransaction
from datetime import datetime
from fastapi.responses import FileResponse
from services.ocr_service import publish_bank_statement_task


router = APIRouter(prefix="/bank-statements", tags=["bank-statements"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=Dict[str, Any])
async def upload_bank_statements(
    files: List[UploadFile] = File(..., description="Up to 12 PDF bank statements"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Accept up to 12 PDF files, create one BankStatement per file, store extracted transactions, and return created statements."""
    require_non_viewer(current_user, "upload bank statements")

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if len(files) > 12:
        raise HTTPException(status_code=400, detail="Maximum of 12 files are allowed")

    allowed_types = {"application/pdf"}

    # Save to tenant-scoped folder
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    tenant_folder = f"tenant_{tenant_id}"
    base_dir = Path("attachments") / tenant_folder / "bank_statements"
    base_dir.mkdir(parents=True, exist_ok=True)

    created: List[Dict[str, Any]] = []

    try:
        for f in files:
            if f.content_type not in allowed_types:
                raise HTTPException(status_code=400, detail="Only PDF files are supported")
            contents = await f.read()
            if len(contents) > 20 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Each file must be <= 20 MB")
            await f.seek(0)

            name = (f.filename or "statement.pdf").strip()
            name = os.path.basename(name)
            name = "".join(ch for ch in name if ch.isalnum() or ch in (".", "_", "-"))
            stem, _ext = os.path.splitext(name)
            unique = uuid.uuid4().hex
            stored_filename = f"bs_{stem[:100]}_{unique}.pdf"
            out_path = base_dir / stored_filename
            with open(out_path, "wb") as out:
                shutil.copyfileobj(f.file, out)

            # Create statement in processing state and enqueue OCR task
            statement = BankStatement(
                tenant_id=tenant_id,
                original_filename=name,
                stored_filename=stored_filename,
                file_path=str(out_path),
                status="processing",
                extracted_count=0,
            )
            db.add(statement)
            db.flush()
            # Force async-only: always enqueue, no sync fallback
            try:
                topic_name = os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr")
                logger.info(f"Enqueue bank statement id={statement.id} topic={topic_name}")
                ok = publish_bank_statement_task({
                    "tenant_id": tenant_id,
                    "statement_id": statement.id,
                    "file_path": str(out_path),
                    "ts": datetime.utcnow().isoformat(),
                })
                if not ok:
                    logger.warning(
                        f"Bank enqueue failed servers={os.getenv('KAFKA_BOOTSTRAP_SERVERS')} topic={topic_name}"
                    )
                    raise RuntimeError("Failed to enqueue bank statement task")
                else:
                    logger.info(f"Bank enqueue success id={statement.id} topic={topic_name}")
            except Exception as e:
                # Keep as processing so UI reflects pending state; worker retry/ops will handle later
                pass
            finally:
                # Persist statement in processing state so it appears immediately
                db.commit()
                db.refresh(statement)

            created.append({
                "id": statement.id,
                "original_filename": statement.original_filename,
                "stored_filename": statement.stored_filename,
                "file_path": statement.file_path,
                "status": statement.status,
                "extracted_count": statement.extracted_count,
                "created_at": statement.created_at.isoformat() if statement.created_at else None,
            })

        return {"success": True, "statements": created}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process bank statements: {e}")
    finally:
        # No cleanup: keep uploads under attachments for audit/debug
        pass


@router.get("/", response_model=Dict[str, Any])
@router.get("", response_model=Dict[str, Any])
async def list_bank_statements(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "list bank statements")
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    rows = (
        db.query(BankStatement)
        .filter(BankStatement.tenant_id == tenant_id)
        .order_by(BankStatement.created_at.desc())
        .all()
    )
    return {
        "success": True,
        "statements": [
            {
                "id": s.id,
                "original_filename": s.original_filename,
                "stored_filename": s.stored_filename,
                "file_path": s.file_path,
                "status": s.status,
                "extracted_count": s.extracted_count,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in rows
        ],
    }


@router.get("/{statement_id}", response_model=Dict[str, Any])
async def get_bank_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "view bank statement")
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    txns = (
        db.query(BankStatementTransaction)
        .filter(BankStatementTransaction.statement_id == s.id)
        .order_by(BankStatementTransaction.date.asc(), BankStatementTransaction.id.asc())
        .all()
    )
    return {
        "success": True,
        "statement": {
            "id": s.id,
            "original_filename": s.original_filename,
            "stored_filename": s.stored_filename,
            "file_path": s.file_path,
            "status": s.status,
            "extracted_count": s.extracted_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "description": t.description,
                    "amount": t.amount,
                    "transaction_type": t.transaction_type,
                    "balance": t.balance,
                    "category": t.category,
                    "invoice_id": getattr(t, 'invoice_id', None),
                    "expense_id": getattr(t, 'expense_id', None),
                }
                for t in txns
            ],
        },
    }


@router.post("/{statement_id}/reprocess", response_model=Dict[str, Any])
async def reprocess_bank_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Requeue or inline-process a bank statement again.
    Always publishes a new Kafka task; UI can call this when previous attempt failed.
    """
    require_non_viewer(current_user, "reprocess bank statement")
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    # Mark as processing again
    try:
        s.status = "processing"
        db.commit()
    except Exception:
        db.rollback()

    # Publish Kafka task
    ok = publish_bank_statement_task({
        "tenant_id": tenant_id,
        "statement_id": statement_id,
        "file_path": s.file_path,
        "ts": datetime.utcnow().isoformat(),
    })
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to enqueue reprocess task")
    return {"success": True, "message": "Reprocessing started"}


@router.put("/{statement_id}/transactions", response_model=Dict[str, Any])
async def replace_bank_statement_transactions(
    statement_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "edit bank statement")
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    items = payload.get("transactions", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="transactions must be an array")

    try:
        # Replace transactions: simple strategy but preserve invoice links if provided
        db.query(BankStatementTransaction).filter(BankStatementTransaction.statement_id == s.id).delete()

        count = 0
        for t in items:
            try:
                dt = datetime.fromisoformat(t.get("date", "")).date()
            except Exception:
                dt = datetime.utcnow().date()
            new_txn = BankStatementTransaction(
                statement_id=s.id,
                date=dt,
                description=t.get("description", ""),
                amount=float(t.get("amount", 0)),
                transaction_type=(t.get("transaction_type") if t.get("transaction_type") in ("debit", "credit") else ("debit" if float(t.get("amount", 0)) < 0 else "credit")),
                balance=(float(t["balance"]) if t.get("balance") not in (None, "") else None),
                category=t.get("category") or None,
            )
            inv_id = t.get("invoice_id")
            try:
                new_txn.invoice_id = int(inv_id) if inv_id not in (None, "") else None
            except Exception:
                new_txn.invoice_id = None
            exp_id = t.get("expense_id")
            try:
                new_txn.expense_id = int(exp_id) if exp_id not in (None, "") else None
            except Exception:
                new_txn.expense_id = None
            db.add(new_txn)
            count += 1

        s.extracted_count = count
        db.commit()
        return {"success": True, "updated_count": count}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update transactions: {e}")


@router.get("/{statement_id}/file")
async def download_bank_statement_file(
    statement_id: int,
    inline: bool = False,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return the original uploaded PDF for a bank statement.
    If inline=true, set Content-Disposition to inline; otherwise as attachment.
    """
    require_non_viewer(current_user, "download bank statement file")
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")
    if not s.file_path or not os.path.exists(s.file_path):
        raise HTTPException(status_code=404, detail="File not found")

    headers = None
    if inline:
        headers = {"Content-Disposition": f"inline; filename=\"{s.original_filename}\""}
        return FileResponse(path=s.file_path, media_type="application/pdf", headers=headers)
    # Attachment with filename
    return FileResponse(path=s.file_path, media_type="application/pdf", filename=s.original_filename)


@router.delete("/{statement_id}", response_model=Dict[str, Any])
async def delete_bank_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "delete bank statement")
    try:
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    file_path = s.file_path
    try:
        db.delete(s)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete statement: {e}")

    # Best-effort remove file; ignore errors
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass

    return {"success": True}


