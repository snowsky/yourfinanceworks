"""Onboarding assistant status: is AI usable, and has the card been dismissed."""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ASSISTANT_DISMISS_KEY = "onboarding_assistant"


class OnboardingAssistantService:
    def __init__(self, db: Session):
        self.db = db

    def status(self) -> dict:
        return {"ai_configured": self._ai_configured(), "dismissed": self._is_dismissed()}

    def dismiss(self) -> dict:
        from core.models.models_per_tenant import Settings

        record = self.db.query(Settings).filter(Settings.key == ASSISTANT_DISMISS_KEY).first()
        if record is None:
            record = Settings(key=ASSISTANT_DISMISS_KEY, value={"dismissed": True}, category="onboarding")
            self.db.add(record)
        else:
            record.value = {"dismissed": True}
        self.db.commit()
        return {"ai_configured": self._ai_configured(), "dismissed": True}

    def _ai_configured(self) -> bool:
        # Mirror the resolution /ai/chat uses (chat.py:48-100): a usable DB config, else env.
        from core.models.models_per_tenant import AIConfig

        default = (
            self.db.query(AIConfig)
            .filter(AIConfig.is_default == True, AIConfig.is_active == True)  # noqa: E712
            .first()
        )
        if default is not None:
            return True
        any_active = self.db.query(AIConfig).filter(AIConfig.is_active == True).first()  # noqa: E712
        if any_active is not None:
            return True
        return self._env_ai_configured()

    def _env_ai_configured(self) -> bool:
        try:
            from commercial.ai.services.ai_config_service import AIConfigService
        except Exception:
            return False
        try:
            return bool(AIConfigService.get_ai_config(self.db, component="chat", require_ocr=False))
        except Exception as exc:
            logger.warning("env AI config check failed: %s", exc)
            return False

    def _is_dismissed(self) -> bool:
        from core.models.models_per_tenant import Settings

        record = self.db.query(Settings).filter(Settings.key == ASSISTANT_DISMISS_KEY).first()
        return bool(record and record.value and record.value.get("dismissed") is True)
