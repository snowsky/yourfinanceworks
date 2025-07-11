from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from fastapi import status

from models.database import get_db
from models.models import ClientNote, User, Client
from schemas.crm import ClientNoteCreate, ClientNote as ClientNoteSchema
from routers.auth import get_current_user

router = APIRouter(prefix="/crm", tags=["crm"])

@router.post("/clients/{client_id}/notes", response_model=ClientNoteSchema)
def create_note_for_client(
    client_id: int,
    note: ClientNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if client exists and belongs to the current user's tenant
    db_client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == current_user.tenant_id
    ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    db_note = ClientNote(
        **note.dict(),
        client_id=client_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

@router.put("/clients/{client_id}/notes/{note_id}", response_model=ClientNoteSchema)
def update_note_for_client(
    client_id: int,
    note_id: int,
    note: ClientNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if client exists and belongs to the current user's tenant
    db_client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == current_user.tenant_id
    ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check if note exists and belongs to the client and tenant
    db_note = db.query(ClientNote).filter(
        ClientNote.id == note_id,
        ClientNote.client_id == client_id,
        ClientNote.tenant_id == current_user.tenant_id
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Update the note
    db_note.note = note.note
    db_note.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(db_note)
    return db_note

@router.delete("/clients/{client_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note_for_client(
    client_id: int,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if client exists and belongs to the current user's tenant
    db_client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == current_user.tenant_id
    ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check if note exists and belongs to the client and tenant
    db_note = db.query(ClientNote).filter(
        ClientNote.id == note_id,
        ClientNote.client_id == client_id,
        ClientNote.tenant_id == current_user.tenant_id
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Delete the note
    db.delete(db_note)
    db.commit()

@router.get("/clients/{client_id}/notes", response_model=List[ClientNoteSchema])
def get_notes_for_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if client exists and belongs to the current user's tenant
    db_client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == current_user.tenant_id
    ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    notes = db.query(ClientNote).filter(ClientNote.client_id == client_id).all()
    return notes
