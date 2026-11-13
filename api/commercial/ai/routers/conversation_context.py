"""Bounded conversation context from the authenticated user's tenant database."""
from datetime import datetime, timedelta, timezone

from core.models.models_per_tenant import AIChatHistory, Settings


def load_conversation_context(db, user_id: int, current_message: str) -> list[dict]:
    setting = db.query(Settings).filter(Settings.key == 'ai_chat_history_retention_days').first()
    try:
        days = max(1, min(30, int(setting.value))) if setting else 7
    except (TypeError, ValueError):
        days = 7
    rows = db.query(AIChatHistory).filter(
        AIChatHistory.user_id == user_id,
        AIChatHistory.created_at >= datetime.now(timezone.utc) - timedelta(days=days),
    ).order_by(AIChatHistory.created_at.desc(), AIChatHistory.id.desc()).limit(13).all()
    # The UI persists the current question before calling /chat.
    if rows and rows[0].sender == 'user' and rows[0].message == current_message:
        rows = rows[1:]
    result = []
    remaining = 12000
    for row in rows[:12]:
        if row.sender not in ('user', 'ai') or not row.message or remaining <= 0:
            continue
        content = row.message[:min(2000, remaining)]
        remaining -= len(content)
        result.append({'role': 'assistant' if row.sender == 'ai' else 'user', 'content': content})
    return list(reversed(result))
