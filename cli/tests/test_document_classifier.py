import logging

from cli.finance_agent_cli.config import Profile
from cli.finance_agent_cli.document_classifier import DocumentClassifier


def _profile(tmp_path):
    return Profile(
        name="test",
        base_url="http://localhost:8000",
        api_base_url="http://localhost:8000/api/v1",
        auth_type="none",
        email=None,
        password=None,
        token=None,
        yfw_api_key=None,
        llm_provider=None,
        llm_model=None,
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


def test_classifier_detects_portfolio_csv(tmp_path):
    path = tmp_path / "holdings.csv"
    path.write_text("symbol,quantity,market value\nAAPL,10,1900\n")

    document = DocumentClassifier(_profile(tmp_path)).classify(path)

    assert document.document_type == "portfolio"
    assert document.confidence > 0


def test_classifier_scans_supported_files_only(tmp_path):
    (tmp_path / "receipt.pdf").write_text("receipt subtotal paid")
    (tmp_path / "notes.txt").write_text("ignore")

    files = DocumentClassifier(_profile(tmp_path)).scan(tmp_path)

    assert [path.name for path in files] == ["receipt.pdf"]


def test_classifier_logs_warning_when_csv_read_fails(tmp_path, caplog, monkeypatch):
    path = tmp_path / "broken.csv"
    path.write_text("symbol,quantity\nAAPL,10\n")

    def boom(*_args, **_kwargs):
        raise OSError("simulated read failure")

    monkeypatch.setattr("pathlib.Path.open", boom)

    with caplog.at_level(logging.WARNING, logger="finance_agent_cli.classifier"):
        DocumentClassifier(_profile(tmp_path)).classify(path)

    assert any(
        "Could not read CSV" in record.message and "broken.csv" in record.message
        for record in caplog.records
    )
