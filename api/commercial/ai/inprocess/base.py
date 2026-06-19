"""In-process API client for the AI chat path.

Implements the AuthenticatedAPIClient method surface by talking directly to the
models/services using the chat request's existing tenant session — no JWT, no
httpx, no second DB connection. Methods not yet migrated delegate to a lazily
built AuthenticatedAPIClient (self-HTTP) so the full surface keeps working.
"""

import logging
from datetime import timedelta

from core.routers.auth import create_access_token
from commercial.ai.routers.auth_client import AuthenticatedAPIClient

logger = logging.getLogger(__name__)

_SELF_BASE_URL = "http://localhost:8000/api/v1"


class InProcessAPIClient:
    def __init__(self, db, current_user):
        self._db = db
        self._current_user = current_user
        self._fallback = None

    def _get_fallback(self) -> AuthenticatedAPIClient:
        if self._fallback is None:
            token = create_access_token(
                data={"sub": self._current_user.email},
                expires_delta=timedelta(minutes=30),
            )
            self._fallback = AuthenticatedAPIClient(base_url=_SELF_BASE_URL, jwt_token=token)
        return self._fallback

    def __getattr__(self, name):
        # Only reached for attributes NOT found normally (i.e. not yet migrated).
        if name.startswith("_"):
            raise AttributeError(name)
        logger.debug("InProcessAPIClient: delegating '%s' to HTTP fallback", name)
        return getattr(self._get_fallback(), name)
