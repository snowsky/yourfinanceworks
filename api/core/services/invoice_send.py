"""Pure helpers for sending an invoice to a client.

Kept free of DB/HTTP so the status-transition and copy-to-sender rules can be
unit-tested directly; the email router wires them to the request.
"""

from typing import List, Optional

# Only these advance to ``sent`` on a successful send; paid/partially_paid/
# overdue/sent/cancelled/pending_approval/rejected are already in-flight,
# terminal, or blocked and must be left untouched.
_PRE_SEND_STATUSES = frozenset({"draft", "approved"})


def status_after_send(current: str) -> str:
    """Status an invoice should hold after a successful send."""
    return "sent" if current in _PRE_SEND_STATUSES else current


def resolve_send_bcc(send_copy: bool, sender_email: Optional[str]) -> List[str]:
    """BCC list for a copy-to-sender send: the sender's own address when
    ``send_copy`` is on and a usable address exists, else empty."""
    if send_copy and sender_email and sender_email.strip():
        return [sender_email.strip()]
    return []
