from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timezone
import logging
import os
import re
from pathlib import Path
import uuid
import shutil

from models.database import get_db
from models.models_per_tenant import Expense, ExpenseAttachment, User, Invoice
from models.models import MasterUser
from routers.auth import get_current_user
from schemas.expense import ExpenseCreate, ExpenseUpdate, Expense as ExpenseSchema
from services.currency_service import CurrencyService
from utils.rbac import require_non_viewer
from utils.audit import log_audit_event


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Ensure logs are visible under uvicorn
uvicorn_logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/", response_model=List[ExpenseSchema])
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    invoice_id: Optional[int] = None,
    unlinked_only: bool = False,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    try:
        query = db.query(Expense)
        if category and category != "all":
            query = query.filter(Expense.category == category)
        if invoice_id is not None:
            query = query.filter(Expense.invoice_id == invoice_id)
        if unlinked_only:
            query = query.filter(Expense.invoice_id.is_(None))
        expenses = query.order_by(Expense.expense_date.desc()).offset(skip).limit(limit).all()
        # Add attachment count for preview
        try:
            for ex in expenses:
                ex.attachments_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == ex.id).count()
        except Exception:
            pass
        return expenses
    except Exception as e:
        logger.error(f"Failed to list expenses: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expenses")


@router.get("/{expense_id}", response_model=ExpenseSchema)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    try:
        expense.attachments_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).count()
    except Exception:
        pass
    return expense


@router.post("/", response_model=ExpenseSchema)
async def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "create expenses")
    try:
        currency_service = CurrencyService(db)
        currency_code = expense.currency or "USD"
        if not currency_service.validate_currency_code(currency_code):
            raise HTTPException(status_code=400, detail=f"Invalid currency code: {currency_code}")

        # Convert date to datetime for DB
        expense_dt = expense.expense_date
        if isinstance(expense_dt, date):
            expense_dt = datetime.combine(expense_dt, datetime.min.time()).replace(tzinfo=timezone.utc)

        tax_amount = expense.tax_amount
        total_amount = expense.total_amount
        if tax_amount is None and expense.tax_rate is not None:
            tax_amount = float(expense.amount) * float(expense.tax_rate) / 100.0
        if total_amount is None:
            total_amount = float(expense.amount) + float(tax_amount or 0)

        # Validate invoice exists if provided
        if expense.invoice_id is not None:
            inv = db.query(Invoice).filter(Invoice.id == expense.invoice_id).first()
            if not inv:
                raise HTTPException(status_code=400, detail=f"Invoice {expense.invoice_id} not found")
            uvicorn_logger.info(f"Creating expense linked to invoice_id={expense.invoice_id}")

        db_expense = Expense(
            amount=float(expense.amount),
            currency=currency_code,
            expense_date=expense_dt,
            category=expense.category,
            vendor=expense.vendor,
            tax_rate=float(expense.tax_rate) if expense.tax_rate is not None else None,
            tax_amount=float(tax_amount) if tax_amount is not None else None,
            total_amount=float(total_amount) if total_amount is not None else None,
            payment_method=expense.payment_method,
            reference_number=expense.reference_number,
            status=expense.status or "recorded",
            notes=expense.notes,
            user_id=current_user.id,
            invoice_id=expense.invoice_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="expense",
            resource_id=str(db_expense.id),
            resource_name=f"Expense {db_expense.id}",
            details=expense.dict(),
            status="success",
        )

        return db_expense
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to create expense")


@router.put("/{expense_id}", response_model=ExpenseSchema)
async def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "update expenses")
    try:
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not db_expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        currency_service = CurrencyService(db)
        update_data = expense.dict(exclude_unset=True)

        if "currency" in update_data:
            if not currency_service.validate_currency_code(update_data["currency"]):
                raise HTTPException(status_code=400, detail=f"Invalid currency code: {update_data['currency']}")

        if "expense_date" in update_data and isinstance(update_data["expense_date"], date):
            update_data["expense_date"] = datetime.combine(update_data["expense_date"], datetime.min.time()).replace(tzinfo=timezone.utc)

        # Validate invoice exists if attempting to (re)link
        if "invoice_id" in update_data and update_data["invoice_id"] is not None:
            inv = db.query(Invoice).filter(Invoice.id == int(update_data["invoice_id"])) .first()
            if not inv:
                raise HTTPException(status_code=400, detail=f"Invoice {update_data['invoice_id']} not found")

        # Recalculate tax/total if needed
        amount = float(update_data.get("amount", db_expense.amount))
        tax_rate = update_data.get("tax_rate", db_expense.tax_rate)
        tax_amount = update_data.get("tax_amount", db_expense.tax_amount)
        total_amount = update_data.get("total_amount", db_expense.total_amount)
        if tax_amount is None and tax_rate is not None:
            tax_amount = float(amount) * float(tax_rate) / 100.0
        if total_amount is None:
            total_amount = float(amount) + float(tax_amount or 0)

        update_data["tax_amount"] = tax_amount
        update_data["total_amount"] = total_amount

        # Log invoice link/unlink intent
        if "invoice_id" in update_data:
            uvicorn_logger.info(
                f"Updating expense {expense_id}: invoice_id {db_expense.invoice_id} -> {update_data['invoice_id']}"
            )

        for k, v in update_data.items():
            setattr(db_expense, k, v if k != "amount" else float(v))

        db_expense.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_expense)
        if "invoice_id" in update_data:
            uvicorn_logger.info(f"Updated expense {expense_id} persisted with invoice_id={db_expense.invoice_id}")

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details=expense.dict(exclude_unset=True),
            status="success",
        )

        return db_expense
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to update expense")


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "delete expenses")
    try:
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not db_expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        # If there is a saved receipt, try to remove it from disk
        # Remove any legacy single receipt file if present
        if db_expense.receipt_path and os.path.exists(db_expense.receipt_path):
            try:
                os.remove(db_expense.receipt_path)
            except Exception as e:
                logger.warning(f"Failed to remove legacy receipt file: {e}")

        # Remove all attachment files associated with this expense
        try:
            attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).all()
            for att in attachments:
                if getattr(att, "file_path", None) and os.path.exists(att.file_path):
                    try:
                        os.remove(att.file_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove attachment file {att.file_path}: {e}")
        except Exception as e:
            logger.warning(f"Failed to enumerate attachments for deletion: {e}")

        db.delete(db_expense)
        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details={"message": "Expense deleted"},
            status="success",
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete expense")


@router.post("/{expense_id}/upload-receipt")
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "upload receipts")
    try:
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        allowed_types = {
            'application/pdf': '.pdf',
            'image/jpeg': '.jpg',
            'image/png': '.png',
        }
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="File type not allowed. Supported: PDF, JPG, PNG")

        MAX_BYTES = 10 * 1024 * 1024
        contents = await file.read()
        if len(contents) > MAX_BYTES:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB")
        await file.seek(0)

        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
        tenant_folder = f"tenant_{tenant_id}" if tenant_id else "tenant_unknown"
        receipts_dir = Path("attachments") / tenant_folder / "expenses"
        receipts_dir.mkdir(parents=True, exist_ok=True)

        original_name = file.filename or "receipt"
        base_name = os.path.basename(original_name)
        base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
        name_without_ext = os.path.splitext(base_name)[0][:100]
        ext_from_ct = allowed_types[file.content_type]
        ext_from_name = os.path.splitext(base_name)[1].lower()
        file_extension = ext_from_ct if ext_from_ct else (ext_from_name if ext_from_name in allowed_types.values() else ".bin")

        # Use UUID to avoid filename collisions
        unique_suffix = str(uuid.uuid4())
        filename = f"expense_{expense_id}_{name_without_ext}_{unique_suffix}{file_extension}"
        file_path = receipts_dir / filename

        # Enforce maximum of 5 attachments
        existing_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).count()
        if existing_count >= 5:
            raise HTTPException(status_code=400, detail="Maximum of 5 attachments per expense")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Save as attachment record
        from models.models_per_tenant import ExpenseAttachment as EAtt
        attachment = EAtt(
            expense_id=expense_id,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=os.path.getsize(file_path),
            file_path=str(file_path),
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        expense.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(expense)

        return {
            "message": "Attachment uploaded successfully",
            "filename": file.filename,
            "size": os.path.getsize(file_path),
            "file_path": str(file_path),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload receipt: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload receipt")


@router.get("/{expense_id}/attachments")
async def list_expense_attachments(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).order_by(ExpenseAttachment.uploaded_at.desc()).all()
    return [
        {
            "id": att.id,
            "filename": att.filename,
            "content_type": att.content_type,
            "size_bytes": att.size_bytes,
            "uploaded_at": att.uploaded_at.isoformat() if att.uploaded_at else None,
        }
        for att in attachments
    ]


@router.delete("/{expense_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense_attachment(
    expense_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    att = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id, ExpenseAttachment.expense_id == expense_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    # Try to remove file from disk
    try:
        if att.file_path and os.path.exists(att.file_path):
            os.remove(att.file_path)
    except Exception as e:
        logger.warning(f"Failed to remove attachment file: {e}")
    db.delete(att)
    db.commit()
    return None


@router.get("/{expense_id}/attachments/{attachment_id}/download")
async def download_expense_attachment(
    expense_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    att = db.query(ExpenseAttachment).filter(
        ExpenseAttachment.id == attachment_id,
        ExpenseAttachment.expense_id == expense_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not att.file_path or not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="Attachment file not found")
    media_type = att.content_type or 'application/octet-stream'
    return FileResponse(path=att.file_path, filename=att.filename, media_type=media_type)


