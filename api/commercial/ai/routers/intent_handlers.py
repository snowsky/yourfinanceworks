# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.
"""AI chat intent dispatcher.

Every intent that used to live in a large if/elif chain here is now a
self-contained handler under ``commercial.ai.routers.intents``. This module
is the thin shim that wires the incoming dispatch call into the registry.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def dispatch_intent(
    intent: str,
    tools: Any,
    message: str,
    lower_message: str,
    ai_config: Any,
    page_context: Optional[Dict[str, Any]],
    db: Session,
    tool_options: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Route a classified intent through the registry.

    Returns the MCP envelope dict produced by the handler, or ``None`` when
    no handler is registered for the intent or when the handler chose to
    fall back to the plain-LLM path.
    """
    from commercial.ai.routers.intent_registry import IntentContext
    from commercial.ai.routers.intents import default_registry

    ctx = IntentContext(
        intent=intent,
        message=message,
        lower_message=lower_message,
        tools=tools,
        ai_config=ai_config,
        page_context=page_context,
        db=db,
        tool_options=tool_options,
    )
    return await default_registry.dispatch(ctx)
