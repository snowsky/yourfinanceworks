"""Release the tenant DB connection before slow LLM round-trips.

ai_chat holds one tenant pool connection for the whole request. Routing every
litellm call through llm_acompletion() returns that connection to the pool
during the (multi-second) model call so it isn't held idle, preventing pool
exhaustion under concurrent chats.
"""

from types import SimpleNamespace

from litellm import acompletion


def materialize_ai_config(cfg) -> SimpleNamespace:
    """Copy the resolved AI config into a plain object so later attribute access
    cannot trigger an ORM re-query (which would re-check-out the connection).

    Intentionally carries ONLY the four fields the chat path reads when building
    LLM kwargs; other AIConfig attributes (is_active/is_default/id/…) are dropped.
    """
    return SimpleNamespace(
        provider_name=getattr(cfg, "provider_name", None),
        model_name=getattr(cfg, "model_name", None),
        api_key=getattr(cfg, "api_key", None),
        provider_url=getattr(cfg, "provider_url", None),
    )


async def llm_acompletion(db, **kwargs):
    """Return the tenant connection to the pool, then run the LLM call."""
    if db is not None:
        db.rollback()  # ends the open read txn -> connection released to the pool
    return await acompletion(**kwargs)
