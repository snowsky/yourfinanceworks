"""Debug mode must not weaken the browser session boundary."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse

from handler_loader import load_functions


@pytest.mark.parametrize("debug", [False, True])
def test_cookie_mutation_rejects_untrusted_origin_even_in_debug(debug):
    calls = []
    async def next_handler(request):
        calls.append(request)
        return "accepted"
    namespace = dict(
        debug_mode=debug, _CSRF_SAFE_METHODS={"GET", "HEAD", "OPTIONS"},
        _AUTH_COOKIE_NAME="auth_token", allowed_origins=["https://app.example.invalid"],
        JSONResponse=JSONResponse, logger=SimpleNamespace(warning=lambda *_: None),
    )
    load_functions("api/main.py", ["_origin_is_trusted", "csrf_protection"], namespace)
    request = SimpleNamespace(
        method="POST", cookies={"auth_token": "dummy-cookie"},
        headers={"origin": "https://untrusted.example.invalid"},
        url=SimpleNamespace(path="/api/v1/clients/"),
    )
    response = asyncio.run(namespace["csrf_protection"](request, next_handler))
    assert response.status_code == 403
    assert not calls


@pytest.mark.parametrize("debug", ["true", "false"])
def test_debug_does_not_replace_explicit_origins_with_wildcard(debug):
    # Run the actual startup policy block, without importing main or its DB setup.
    from handler_loader import ROOT
    source = (ROOT / "api/main.py").read_text()
    block = source[source.index('debug_env ='):source.index('# Log CORS configuration')]
    env = {"DEBUG": debug, "ALLOWED_ORIGINS": "https://app.example.invalid"}
    namespace = {"os": SimpleNamespace(getenv=lambda key, default=None: env.get(key, default))}
    exec(block, namespace)
    assert namespace["allowed_origins"] == ["https://app.example.invalid"]
    assert namespace["allow_credentials"] is True


def test_browser_policy_defaults_to_production():
    from handler_loader import ROOT
    source = (ROOT / "api/main.py").read_text()
    block = source[source.index('debug_env ='):source.index('# Log CORS configuration')]
    namespace = {"os": SimpleNamespace(getenv=lambda key, default=None: default)}
    exec(block, namespace)
    assert namespace["dev_env"] == "production"
    assert "*" not in namespace["allowed_origins"]


def test_wildcard_cannot_be_configured_as_browser_trust():
    from handler_loader import ROOT
    source = (ROOT / "api/main.py").read_text()
    block = source[source.index('debug_env ='):source.index('# Log CORS configuration')]
    env = {"ALLOWED_ORIGINS": "*", "DEBUG": "true"}
    with pytest.raises(ValueError, match="explicit trusted origins"):
        exec(block, {"os": SimpleNamespace(getenv=lambda key, default=None: env.get(key, default))})


def test_trusted_cookie_origin_remains_usable():
    async def next_handler(request):
        return "accepted"
    namespace = dict(
        _CSRF_SAFE_METHODS={"GET", "HEAD", "OPTIONS"}, _AUTH_COOKIE_NAME="auth_token",
        allowed_origins=["https://app.example.invalid"], JSONResponse=JSONResponse,
        logger=SimpleNamespace(warning=lambda *_: None),
    )
    load_functions("api/main.py", ["_origin_is_trusted", "csrf_protection"], namespace)
    request = SimpleNamespace(
        method="POST", cookies={"auth_token": "dummy-cookie"},
        headers={"origin": "https://app.example.invalid"},
        url=SimpleNamespace(path="/api/v1/clients/"),
    )
    assert asyncio.run(namespace["csrf_protection"](request, next_handler)) == "accepted"
