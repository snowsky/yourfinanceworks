"""Robust JSON extraction from LLM responses.

The previous approach used a non-greedy regex ``\\[[\\s\\S]*?\\]`` and ``re.findall`` to
pull a JSON array out of the model's text. Because the match is non-greedy it stops at the
FIRST ``]`` — so any ``]`` inside a transaction value (e.g. a description like ``"misc [x]"``)
or a nested array truncates the match, ``json.loads`` then fails, and transactions are
silently dropped.

``extract_json_payload`` instead uses ``json.JSONDecoder.raw_decode``, which understands
nested brackets and ignores trailing prose, so the whole array is recovered intact.
"""

import json
import re
from typing import Any, Optional

# Strip ```json / ``` code fences before scanning.
_FENCE_RE = re.compile(r"```(?:json)?", re.IGNORECASE)


def _score(value: Any, span: int) -> tuple:
    """Rank a decoded candidate. The transaction payload is a non-empty list of objects;
    prefer that, then any list, then an object, breaking ties by how much text it spanned
    (the outermost / most complete structure)."""
    if isinstance(value, list) and value and all(isinstance(e, dict) for e in value):
        rank = 3
    elif isinstance(value, list):
        rank = 2
    elif isinstance(value, dict):
        rank = 1
    else:
        rank = 0
    return (rank, span)


def extract_json_payload(text: str) -> Optional[Any]:
    """Return the most likely JSON payload in ``text``, or ``None``.

    Scans every ``[``/``{`` and uses ``raw_decode`` (nesting-aware, tolerates trailing
    prose), then picks the best candidate by :func:`_score` — so a stray ``[42]`` or
    ``{...}`` in the prose loses to the real array of transaction objects.
    """
    if not text:
        return None
    cleaned = _FENCE_RE.sub("", text).strip()
    decoder = json.JSONDecoder()
    best_value: Optional[Any] = None
    best_score: Optional[tuple] = None
    for idx, ch in enumerate(cleaned):
        if ch not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(cleaned, idx)
        except json.JSONDecodeError:
            continue
        score = _score(value, end - idx)
        if best_score is None or score > best_score:
            best_score, best_value = score, value
    return best_value
