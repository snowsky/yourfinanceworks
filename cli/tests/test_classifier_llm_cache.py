"""Disk-backed LLM cache for DocumentClassifier."""

from __future__ import annotations

import json
import sys
import types

import pytest

from cli.finance_agent_cli.config import Profile
from cli.finance_agent_cli.document_classifier import (
    LLM_CACHE_FILENAME,
    DocumentClassifier,
)


def _profile(tmp_path, *, llm_model: str | None = "gpt-4o-mini"):
    return Profile(
        name="test",
        base_url="http://localhost:8000",
        api_base_url="http://localhost:8000/api/v1",
        auth_type="none",
        email=None,
        password=None,
        token=None,
        yfw_api_key=None,
        llm_provider="openai" if llm_model else None,
        llm_model=llm_model,
        llm_api_key=None,
        llm_base_url=None,
        interval_seconds=300,
        drift_threshold=1.0,
        refresh_prices_on_monitor=False,
        state_path=tmp_path / "state.json",
        token_path=tmp_path / "token.json",
        history_path=tmp_path / "history.jsonl",
        snapshot_dir=tmp_path / "snapshots",
    )


def _install_fake_litellm(monkeypatch, *, label: str, call_counter: list[int]):
    """Replace litellm with a fake module whose completion() returns `label`."""
    module = types.ModuleType("litellm")

    class _Choice:
        def __init__(self, content):
            self.message = types.SimpleNamespace(content=content)

    class _Response:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    def fake_completion(**_kwargs):
        call_counter.append(1)
        return _Response(label)

    module.completion = fake_completion  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", module)


def test_llm_cache_hit_avoids_second_completion_call(tmp_path, monkeypatch):
    file_path = tmp_path / "ambiguous.pdf"
    file_path.write_bytes(b"unparseable")  # extract_sample returns "" -> low keyword score
    calls: list[int] = []
    _install_fake_litellm(monkeypatch, label="invoice", call_counter=calls)

    classifier = DocumentClassifier(_profile(tmp_path))
    first = classifier.classify(file_path)
    classifier_again = DocumentClassifier(_profile(tmp_path))  # fresh instance, shared on-disk cache
    second = classifier_again.classify(file_path)

    assert first.document_type == "invoice"
    assert second.document_type == "invoice"
    assert len(calls) == 1, "second classify must be served from cache"


def test_cache_key_depends_on_model_name(tmp_path, monkeypatch):
    file_path = tmp_path / "ambiguous.pdf"
    file_path.write_bytes(b"unparseable")
    calls: list[int] = []
    _install_fake_litellm(monkeypatch, label="invoice", call_counter=calls)

    DocumentClassifier(_profile(tmp_path, llm_model="gpt-4o-mini")).classify(file_path)
    DocumentClassifier(_profile(tmp_path, llm_model="gpt-4o")).classify(file_path)

    assert len(calls) == 2, "different model names must miss the cache"


def test_cache_disabled_silently_on_corrupt_file(tmp_path, monkeypatch, caplog):
    file_path = tmp_path / "ambiguous.pdf"
    file_path.write_bytes(b"unparseable")
    cache_path = tmp_path / LLM_CACHE_FILENAME
    cache_path.write_text("{not valid json")
    calls: list[int] = []
    _install_fake_litellm(monkeypatch, label="invoice", call_counter=calls)

    import logging

    with caplog.at_level(logging.WARNING, logger="finance_agent_cli.classifier"):
        result = DocumentClassifier(_profile(tmp_path)).classify(file_path)

    assert result.document_type == "invoice"
    assert len(calls) == 1
    assert any("Could not load classify cache" in record.message for record in caplog.records)


def test_no_cache_lookup_when_no_llm_model_configured(tmp_path):
    file_path = tmp_path / "holdings.csv"
    file_path.write_text("symbol,quantity,market value\nAAPL,10,1900\n")

    result = DocumentClassifier(_profile(tmp_path, llm_model=None)).classify(file_path)

    assert result.document_type == "portfolio"
    # Keyword match should give >= 2 score, so cache file is never created.
    assert not (tmp_path / LLM_CACHE_FILENAME).exists()


def test_cache_file_written_after_successful_classification(tmp_path, monkeypatch):
    file_path = tmp_path / "ambiguous.pdf"
    file_path.write_bytes(b"unparseable")
    calls: list[int] = []
    _install_fake_litellm(monkeypatch, label="expense", call_counter=calls)

    DocumentClassifier(_profile(tmp_path)).classify(file_path)

    cache_path = tmp_path / LLM_CACHE_FILENAME
    assert cache_path.exists()
    payload = json.loads(cache_path.read_text())
    assert "expense" in payload.values()
