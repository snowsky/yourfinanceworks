from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from fastapi import status

from models.database import get_master_db, set_tenant_context
from models.models import MasterUser
from models.models_per_tenant import ClientNote, Client
from schemas.crm import ClientNoteCreate, ClientNote as ClientNoteSchema
from routers.auth import get_current_user
from services.tenant_database_manager import tenant_db_manager
from utils.audit import log_audit_event

router = APIRouter(prefix="/crm", tags=["crm"])

@router.post("/clients/{client_id}/notes", response_model=ClientNoteSchema)
async def create_client_note(
    client_id: int,
    note: ClientNoteCreate,
    current_user: MasterUser = Depends(get_current_user)
):
    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = SessionLocal()
    
    try:
        # Check if client exists
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        db_note = ClientNote(
            **note.model_dump(),
            client_id=client_id,
            user_id=current_user.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(db_note)
        db.commit()
        db.refresh(db_note)
        # Audit log
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="client_note",
            resource_id=str(db_note.id),
            resource_name=f"Client {client_id} Note",
            details=note.model_dump(),
            status="success",
        )
        return db_note
    finally:
        db.close()

@router.put("/clients/{client_id}/notes/{note_id}", response_model=ClientNoteSchema)
async def update_client_note(
    client_id: int,
    note_id: int,
    note: ClientNoteCreate,
    current_user: MasterUser = Depends(get_current_user)
):
    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = SessionLocal()
    
    try:
        # Check if client exists
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Check if note exists and belongs to the client
        db_note = db.query(ClientNote).filter(
            ClientNote.id == note_id,
            ClientNote.client_id == client_id
        ).first()
        if not db_note:
            raise HTTPException(status_code=404, detail="Note not found")

        # Update the note
        db_note.note = note.note
        db_note.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(db_note)
        # Audit log update
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="client_note",
            resource_id=str(db_note.id),
            resource_name=f"Client {client_id} Note",
            details={"note": note.note},
            status="success",
        )
        return db_note
    finally:
        db.close()

@router.delete("/clients/{client_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_note(
    client_id: int,
    note_id: int,
    current_user: MasterUser = Depends(get_current_user)
):
    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = SessionLocal()
    
    try:
        # Check if client exists
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Check if note exists and belongs to the client
        db_note = db.query(ClientNote).filter(
            ClientNote.id == note_id,
            ClientNote.client_id == client_id
        ).first()
        if not db_note:
            raise HTTPException(status_code=404, detail="Note not found")

        # Delete the note
        db.delete(db_note)
        db.commit()
        # Audit log delete
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="client_note",
            resource_id=str(db_note.id),
            resource_name=f"Client {client_id} Note",
            details={"message": "Client note deleted"},
            status="success",
        )
    finally:
        db.close()

@router.get("/clients/{client_id}/notes", response_model=List[ClientNoteSchema])
async def get_client_notes(
    client_id: int,
    current_user: MasterUser = Depends(get_current_user)
):
    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = SessionLocal()
    
    try:
        # Check if client exists
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        notes = db.query(ClientNote).filter(ClientNote.client_id == client_id).all()
        return notes
    finally:
        db.close()