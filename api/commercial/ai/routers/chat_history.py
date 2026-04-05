# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import AIChatHistory, Settings
from core.routers.auth import get_current_user
from commercial.ai.routers.chat_models import ChatMessageRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat/message")
def save_ai_chat_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        chat_message = AIChatHistory(
            user_id=current_user.id,
            tenant_id=getattr(current_user, 'tenant_id', None),
            message=request.message,
            sender=request.sender,
            created_at=datetime.now(timezone.utc)
        )
        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)
        return {"success": True, "id": chat_message.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save AI chat message: {str(e)}"
        )

@router.get("/chat/history")
def get_ai_chat_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        # Validate pagination parameters
        limit = max(1, min(100, limit))  # Clamp between 1 and 100
        offset = max(0, offset)

        # Get retention period from core.settings (default 7 days, max 30 days)
        # Use the same approach as settings router - get from key-value store
        retention_setting = db.query(Settings).filter(Settings.key == "ai_chat_history_retention_days").first()
        retention_days = 7  # default
        if retention_setting and retention_setting.value:
            try:
                retention_days = int(retention_setting.value)
                # Ensure retention is within allowed range (1-30 days)
                retention_days = max(1, min(30, retention_days))
            except (ValueError, TypeError):
                retention_days = 7

        try:
            user_id = current_user.id
            logger.info(f"AI Chat History: retention_days={retention_days}, user_id={user_id}, limit={limit}, offset={offset}")
        except AttributeError as e:
            logger.error(f"AI Chat History: current_user has no id attribute: {e}, user_attrs={dir(current_user)}")
            raise HTTPException(status_code=500, detail="User authentication error")

        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        # Get total count for pagination info
        total_count = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == current_user.id,
            AIChatHistory.created_at >= cutoff_date
        ).count()

        # Get chat history within retention period, ordered by most recent first, then paginate
        history = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == current_user.id,
            AIChatHistory.created_at >= cutoff_date
        ).order_by(AIChatHistory.created_at.desc()).offset(offset).limit(limit).all()

        # For initial load (offset=0), reverse to get chronological order (oldest first in the batch)
        # For pagination, keep descending order since we're prepending
        if offset == 0:
            history = list(reversed(history))

        # Purge old messages (older than retention period) - only on first request
        if offset == 0:
            deleted_count = db.query(AIChatHistory).filter(
                AIChatHistory.user_id == current_user.id,
                AIChatHistory.created_at < cutoff_date
            ).delete()

            if deleted_count > 0:
                db.commit()
                logger.info(f"Purged {deleted_count} old AI chat messages for user {current_user.id}")

        return [{
            "id": msg.id,
            "message": msg.message,
            "sender": msg.sender,
            "created_at": msg.created_at.isoformat()
        } for msg in history]
    except Exception as e:
        logger.error(f"AI Chat History error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get AI chat history: {str(e)}"
        )
