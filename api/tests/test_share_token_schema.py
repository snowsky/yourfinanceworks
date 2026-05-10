from core.schemas.share_token import ALLOWED_RECORD_TYPES, ShareTokenCreate


def test_docvault_items_are_allowed_share_token_records():
    assert "docvault_item" in ALLOWED_RECORD_TYPES

    payload = ShareTokenCreate(
        record_type="docvault_item",
        record_id=123,
        access_type="public",
        expires_in_hours=24,
    )

    assert payload.record_type == "docvault_item"
