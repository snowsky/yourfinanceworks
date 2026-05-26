from cli.finance_agent_cli.api_client import InvestmentAPIClient
from cli.finance_agent_cli.config import Profile


class FakeResponse:
    status_code = 201
    content = b"{}"

    def json(self):
        return {"job_id": "job_123"}


class FakeHttpClient:
    def __init__(self):
        self.post_calls = []
        self.request_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse()

    def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        return FakeResponse()

    def close(self):
        pass


class FakeRequestHttpClient:
    def __init__(self):
        self.request_calls = []

    def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        return FakeResponse()

    def close(self):
        pass


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


def test_upload_batch_files_uses_authenticated_endpoint_without_yfw_api_key(tmp_path):
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"receipt")
    fake_http = FakeHttpClient()
    client = InvestmentAPIClient(_profile(tmp_path), http_client=fake_http)

    payload = client.upload_batch_files([path], document_types=["expense"])

    assert payload == {"job_id": "job_123"}
    url, kwargs = fake_http.post_calls[0]
    assert url == "http://localhost:8000/api/v1/external-transactions/batch-processing/upload-authenticated"
    assert "X-API-Key" not in kwargs["headers"]


def test_ai_chat_uses_web_assistant_endpoint(tmp_path):
    fake_http = FakeHttpClient()
    client = InvestmentAPIClient(_profile(tmp_path), http_client=fake_http)

    client.ai_chat("list expenses", config_id=9, page_context={"route": "/expenses"})

    method, url, kwargs = fake_http.request_calls[0]
    assert method == "POST"
    assert url == "http://localhost:8000/api/v1/ai/chat"
    assert kwargs["json"] == {
        "message": "list expenses",
        "config_id": 9,
        "page_context": {"route": "/expenses"},
    }


def test_cached_token_is_sent_when_auth_type_is_none(tmp_path):
    profile = _profile(tmp_path)
    profile.token_path.write_text(
        """
        {
          "token": "cached-token",
          "expires": "2999-01-01T00:00:00+00:00"
        }
        """
    )
    fake_http = FakeRequestHttpClient()
    client = InvestmentAPIClient(profile, http_client=fake_http)

    client.list_portfolios()

    _method, _url, kwargs = fake_http.request_calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer cached-token"


def test_list_document_resources_use_expected_paths(tmp_path):
    fake_http = FakeRequestHttpClient()
    client = InvestmentAPIClient(_profile(tmp_path), http_client=fake_http)

    client.list_expenses()
    client.list_invoices()
    client.list_statements()

    paths = [url.removeprefix("http://localhost:8000/api/v1") for _method, url, _kwargs in fake_http.request_calls]
    assert paths == ["/expenses/", "/invoices/", "/statements/"]
