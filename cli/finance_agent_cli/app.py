from __future__ import annotations

import argparse
import json
import os
import getpass
import socket
import ssl
import threading
import time
import webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib import parse
from urllib import error, request


def resolve_config_path() -> Path:
    env_path = os.environ.get("FINANCE_AGENT_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    home_path = Path.home() / ".finance-agent" / "config.json"
    try:
        home_path.parent.mkdir(parents=True, exist_ok=True)
        if not home_path.exists():
            home_path.touch(exist_ok=True)
        return home_path
    except OSError:
        fallback_dir = Path.cwd() / ".finance-agent"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "config.json"


def fallback_config_path() -> Path:
    fallback_dir = Path.cwd() / ".finance-agent"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir / "config.json"


CONFIG_PATH = resolve_config_path()
CONFIG_DIR = CONFIG_PATH.parent


def load_config() -> dict[str, Any]:
    config_path = CONFIG_PATH
    if not config_path.exists():
        return {"active_profile": None, "profiles": {}}

    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        alt_path = fallback_config_path()
        if alt_path != config_path and alt_path.exists():
            try:
                return json.loads(alt_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"active_profile": None, "profiles": {}}


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config, indent=2) + "\n"
    try:
        CONFIG_PATH.write_text(payload)
    except OSError:
        alt_path = fallback_config_path()
        alt_path.write_text(payload)


def get_active_profile(config: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    profile_name = config.get("active_profile")
    if not profile_name:
        return None, None
    return profile_name, config.get("profiles", {}).get(profile_name)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def api_url(base_url: str, path: str) -> str:
    return f"{normalize_base_url(base_url)}{path}"


def auth_headers(profile: dict[str, Any] | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if not profile:
        return headers

    auth_type = profile.get("auth_type")
    if auth_type == "api_key" and profile.get("api_key"):
        headers["X-API-Key"] = profile["api_key"]
        return headers

    token = profile.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def build_ssl_context(profile: dict[str, Any] | None) -> ssl.SSLContext | None:
    if not profile:
        return ssl.create_default_context()

    if profile.get("tls_insecure"):
        return ssl._create_unverified_context()

    ca_bundle = profile.get("ca_bundle")
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)

    return ssl.create_default_context()


def http_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    request_headers = headers or {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(url=url, data=data, headers=request_headers, method=method)
    try:
        with request.urlopen(req, timeout=60, context=build_ssl_context(profile)) as response:
            body = response.read().decode("utf-8")
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body or exc.reason
        return exc.code, parsed
    except error.URLError as exc:
        return 0, str(exc.reason)


def extract_chat_text(response: dict[str, Any] | list[Any] | str) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, list):
        return json.dumps(response, indent=2)

    for key in ("response", "message", "result", "content", "answer"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return json.dumps(response, indent=2)


def describe_error(status_code: int, response: dict[str, Any] | list[Any] | str) -> str:
    if isinstance(response, dict) and response.get("cloudflare_error"):
        error_code = response.get("error_code", "unknown")
        error_name = response.get("error_name", "unknown")
        detail = response.get("detail", "Cloudflare blocked this request.")
        return (
            f"Cloudflare blocked the CLI request ({status_code}, {error_code}: {error_name}).\n"
            f"{detail}\n"
            "This deployment is rejecting non-browser clients. "
            "Use an API host that allows CLI traffic, or ask the site owner to allowlist the CLI/API path."
        )

    return extract_chat_text(response)


def allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def run_browser_login_flow(
    base_url: str,
    profile: dict[str, Any],
    login_path: str,
    timeout_seconds: int,
    open_browser: bool,
) -> tuple[bool, str]:
    callback_state = {"token": None, "error": None}
    callback_event = threading.Event()
    port = allocate_loopback_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = parse.urlparse(self.path)
            params = parse.parse_qs(parsed.query)
            token = (
                params.get("access_token", [None])[0]
                or params.get("token", [None])[0]
                or params.get("api_key", [None])[0]
            )
            err = params.get("error", [None])[0]

            if token:
                callback_state["token"] = token
                message = "Login complete. You can close this browser tab."
                status = 200
            else:
                callback_state["error"] = err or "No token was returned to the CLI callback."
                message = "Login did not return a token. You can close this browser tab."
                status = 400

            body = (
                "<html><body style='font-family: sans-serif; padding: 24px;'>"
                f"<h2>{message}</h2>"
                "</body></html>"
            ).encode("utf-8")

            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            callback_event.set()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 0.5

    def serve() -> None:
        while not callback_event.is_set():
            server.handle_request()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    auth_url = (
        f"{normalize_base_url(base_url)}{login_path}"
        f"?redirect_uri={parse.quote(redirect_uri, safe='')}"
        f"&cli=1"
    )

    print("Browser login")
    print(f"- Redirect URI: {redirect_uri}")
    print(f"- Login URL: {auth_url}")

    if open_browser:
        opened = webbrowser.open(auth_url)
        if not opened:
            print("Could not open the browser automatically. Open the URL manually.")
    else:
        print("Open the login URL manually in your browser.")

    if not callback_event.wait(timeout_seconds):
        callback_state["error"] = f"Timed out waiting for browser login after {timeout_seconds} seconds."

    callback_event.set()
    thread.join(timeout=1)
    server.server_close()

    if callback_state["token"]:
        profile["auth_type"] = "bearer"
        profile["access_token"] = callback_state["token"]
        profile.pop("api_key", None)
        return True, "Browser login completed and token saved."

    return False, callback_state["error"] or "Browser login failed."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finance-agent",
        description="Finance agent CLI scaffold for local and remote operation.",
    )

    subparsers = parser.add_subparsers(dest="command")

    up_parser = subparsers.add_parser("up", help="Start the local stack.")
    up_parser.add_argument("--profile", default="dev")
    up_parser.add_argument("--build", action="store_true")
    up_parser.add_argument("--detach", action="store_true", default=True)

    down_parser = subparsers.add_parser("down", help="Stop the local stack.")
    down_parser.add_argument("--volumes", action="store_true")

    connect_parser = subparsers.add_parser("connect", help="Connect to an existing backend.")
    connect_parser.add_argument("--base-url", required=True)
    connect_parser.add_argument("--profile", default="default")
    connect_parser.add_argument("--mode", choices=["local", "remote"], default="remote")
    connect_parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification.")
    connect_parser.add_argument("--ca-bundle", help="Path to a custom CA bundle for TLS verification.")

    auth_parser = subparsers.add_parser("auth", help="Manage authentication.")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command")

    auth_login_parser = auth_subparsers.add_parser("login", help="Login with interactive auth.")
    auth_login_parser.add_argument("--base-url")
    auth_login_parser.add_argument("--profile")
    auth_login_parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification.")
    auth_login_parser.add_argument("--ca-bundle", help="Path to a custom CA bundle for TLS verification.")

    auth_browser_login_parser = auth_subparsers.add_parser("browser-login", help="Login via a browser callback flow.")
    auth_browser_login_parser.add_argument("--base-url")
    auth_browser_login_parser.add_argument("--profile")
    auth_browser_login_parser.add_argument("--login-path", default="/api/v1/auth/cli/login")
    auth_browser_login_parser.add_argument("--timeout", type=int, default=180)
    auth_browser_login_parser.add_argument("--no-open", action="store_true", help="Print the URL instead of opening a browser.")

    auth_api_key_parser = auth_subparsers.add_parser("api-key", help="Manage API keys.")
    auth_api_key_subparsers = auth_api_key_parser.add_subparsers(dest="api_key_command")
    auth_api_key_set_parser = auth_api_key_subparsers.add_parser("set", help="Set an API key.")
    auth_api_key_set_parser.add_argument("--api-key", required=True)
    auth_api_key_set_parser.add_argument("--profile", default="default")
    auth_api_key_set_parser.add_argument("--base-url")
    auth_api_key_set_parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification.")
    auth_api_key_set_parser.add_argument("--ca-bundle", help="Path to a custom CA bundle for TLS verification.")

    auth_subparsers.add_parser("whoami", help="Show current auth status.")
    auth_subparsers.add_parser("logout", help="Clear saved auth state.")

    run_parser = subparsers.add_parser("run", help="Run a finance-agent task.")
    run_parser.add_argument("task")
    run_parser.add_argument("--tenant")
    run_parser.add_argument("--agent", default="auto")
    run_parser.add_argument("--json", action="store_true")
    run_parser.add_argument("--wait", action="store_true")

    runs_parser = subparsers.add_parser("runs", help="Inspect agent runs.")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command")
    runs_list_parser = runs_subparsers.add_parser("list", help="List agent runs.")
    runs_list_parser.add_argument("--tenant")
    runs_list_parser.add_argument("--status")
    runs_get_parser = runs_subparsers.add_parser("get", help="Fetch a run.")
    runs_get_parser.add_argument("run_id")
    runs_tail_parser = runs_subparsers.add_parser("tail", help="Tail a run trace.")
    runs_tail_parser.add_argument("run_id")
    runs_replay_parser = runs_subparsers.add_parser("replay", help="Replay a run.")
    runs_replay_parser.add_argument("run_id")

    approvals_parser = subparsers.add_parser("approvals", help="Manage approvals.")
    approvals_subparsers = approvals_parser.add_subparsers(dest="approvals_command")
    approvals_list_parser = approvals_subparsers.add_parser("list", help="List approvals.")
    approvals_list_parser.add_argument("--tenant")
    approvals_approve_parser = approvals_subparsers.add_parser("approve", help="Approve an action.")
    approvals_approve_parser.add_argument("approval_id")
    approvals_approve_parser.add_argument("--reason")
    approvals_reject_parser = approvals_subparsers.add_parser("reject", help="Reject an action.")
    approvals_reject_parser.add_argument("approval_id")
    approvals_reject_parser.add_argument("--reason")

    subparsers.add_parser("doctor", help="Check local or remote connectivity.")

    return parser


def print_shell_banner(config: dict[str, Any]) -> None:
    profile_name, profile = get_active_profile(config)
    if profile_name and profile:
        base_url = profile.get("base_url", "unset")
        print(f"Connected to: {profile_name} ({base_url})")
    else:
        print("Connected to: none")
    print("Type /help for shell commands, or /exit to quit.")


def execute_prompt(
    prompt: str,
    config: dict[str, Any],
    tenant: str | None = None,
    agent: str = "auto",
    as_json: bool = False,
) -> int:
    profile_name, profile = get_active_profile(config)
    if not profile:
        print("No active profile. Run `connect --base-url ...` first.")
        return 1

    base_url = profile.get("base_url")
    if not base_url:
        print("Active profile has no base URL. Run `connect --base-url ...` first.")
        return 1

    if not (profile.get("access_token") or profile.get("api_key")):
        print("Active profile has no credentials. Run `auth login`, `auth browser-login`, or `auth api-key set` first.")
        return 1

    auth_type = profile.get("auth_type", "none")
    if auth_type == "api_key":
        endpoint_path = "/api/v1/external/agent/run"
        payload: dict[str, Any] = {"prompt": prompt, "config_id": 0}
    else:
        endpoint_path = "/api/v1/ai/chat"
        payload = {"message": prompt, "config_id": 0}

    if tenant:
        payload["page_context"] = {"tenant": tenant, "cli_agent": agent}

    status_code, response = http_json(
        "POST",
        api_url(base_url, endpoint_path),
        headers=auth_headers(profile),
        payload=payload,
        profile=profile,
    )

    if as_json:
        print(
            json.dumps(
                {
                    "profile": profile_name,
                    "base_url": base_url,
                    "status_code": status_code,
                    "response": response,
                },
                indent=2,
            )
        )
        return 0 if 200 <= status_code < 300 else 1

    if 200 <= status_code < 300:
        print(extract_chat_text(response))
        return 0

    print(f"Run failed ({status_code or 'network error'}).")
    print(describe_error(status_code, response))
    return 1


def run_shell() -> int:
    config = load_config()
    print_shell_banner(config)

    while True:
        try:
            raw = input("\n> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 130

        if not raw:
            continue

        if raw in {"/exit", "/quit"}:
            return 0

        if raw == "/help":
            print("Shell commands: /help, /exit, /profile, /trace")
            continue

        if raw == "/profile":
            profile_name, profile = get_active_profile(config)
            if not profile_name or not profile:
                print("No active profile.")
            else:
                print(json.dumps({"profile": profile_name, **profile}, indent=2))
            continue

        if raw == "/trace":
            print("Trace streaming is not implemented yet.")
            continue

        execute_prompt(raw, config)


def handle_connect(args: argparse.Namespace) -> int:
    config = load_config()
    profiles = config.setdefault("profiles", {})
    profiles[args.profile] = {
        "mode": args.mode,
        "base_url": normalize_base_url(args.base_url),
        "auth_type": profiles.get(args.profile, {}).get("auth_type", "none"),
        "tls_insecure": bool(args.insecure),
        "ca_bundle": args.ca_bundle,
    }
    config["active_profile"] = args.profile
    save_config(config)
    print(f'Saved profile "{args.profile}" with base URL {normalize_base_url(args.base_url)}')
    return 0


def handle_auth(args: argparse.Namespace) -> int:
    config = load_config()

    if args.auth_command == "login":
        target_profile = args.profile or config.get("active_profile") or "default"
        profiles = config.setdefault("profiles", {})
        profile = profiles.setdefault(target_profile, {})

        base_url = normalize_base_url(args.base_url or profile.get("base_url", ""))
        if not base_url:
            print("No base URL configured. Run `connect --base-url ...` first or pass `--base-url`.")
            return 1

        if args.insecure:
            profile["tls_insecure"] = True
            profile["ca_bundle"] = None
        elif args.ca_bundle:
            profile["tls_insecure"] = False
            profile["ca_bundle"] = args.ca_bundle

        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
        status_code, response = http_json(
            "POST",
            api_url(base_url, "/api/v1/auth/login"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            payload={"email": email, "password": password},
            profile=profile,
        )

        if status_code != 200 or not isinstance(response, dict) or "access_token" not in response:
            print(f"Login failed ({status_code or 'network error'}).")
            print(describe_error(status_code, response))
            return 1

        profile["base_url"] = base_url
        profile["auth_type"] = "bearer"
        profile["access_token"] = response["access_token"]
        profile.pop("api_key", None)
        config["active_profile"] = target_profile
        save_config(config)
        print(f'Logged in and saved bearer token for profile "{target_profile}"')
        return 0

    if args.auth_command == "browser-login":
        target_profile = args.profile or config.get("active_profile") or "default"
        profiles = config.setdefault("profiles", {})
        profile = profiles.setdefault(target_profile, {})

        base_url = normalize_base_url(args.base_url or profile.get("base_url", ""))
        if not base_url:
            print("No base URL configured. Run `connect --base-url ...` first or pass `--base-url`.")
            return 1

        profile["base_url"] = base_url
        success, message = run_browser_login_flow(
            base_url=base_url,
            profile=profile,
            login_path=args.login_path,
            timeout_seconds=args.timeout,
            open_browser=not args.no_open,
        )
        if not success:
            print(f"Browser login failed. {message}")
            print("The backend must support redirecting back to the CLI callback with `access_token`, `token`, or `api_key` in the query string.")
            return 1

        config["active_profile"] = target_profile
        save_config(config)
        print(f'{message} Profile "{target_profile}" is active.')
        return 0

    if args.auth_command == "api-key" and args.api_key_command == "set":
        profiles = config.setdefault("profiles", {})
        profile = profiles.setdefault(args.profile, {})
        if args.base_url:
            profile["base_url"] = normalize_base_url(args.base_url)
        if args.insecure:
            profile["tls_insecure"] = True
            profile["ca_bundle"] = None
        elif args.ca_bundle:
            profile["tls_insecure"] = False
            profile["ca_bundle"] = args.ca_bundle
        profile["auth_type"] = "api_key"
        profile["api_key"] = args.api_key
        profile.pop("access_token", None)
        config["active_profile"] = args.profile
        save_config(config)
        print(f'API key saved for profile "{args.profile}"')
        return 0

    if args.auth_command == "whoami":
        profile_name, profile = get_active_profile(config)
        if not profile_name or not profile:
            print("No active profile.")
            return 0
        print(
            json.dumps(
                {
                    "active_profile": profile_name,
                    "base_url": profile.get("base_url"),
                    "auth_type": profile.get("auth_type", "none"),
                    "has_token": bool(profile.get("access_token") or profile.get("api_key")),
                    "tls_insecure": bool(profile.get("tls_insecure")),
                    "ca_bundle": profile.get("ca_bundle"),
                },
                indent=2,
            )
        )
        return 0

    if args.auth_command == "logout":
        profile_name, profile = get_active_profile(config)
        if profile_name and profile:
            profile.pop("api_key", None)
            profile.pop("access_token", None)
            profile["auth_type"] = "none"
            save_config(config)
        print("Cleared saved auth state for the active profile.")
        return 0

    print("Unknown auth command.")
    return 1


def handle_up(args: argparse.Namespace) -> int:
    print("Local stack startup is not implemented yet.")
    print(f"profile={args.profile} build={args.build} detach={args.detach}")
    return 0


def handle_down(args: argparse.Namespace) -> int:
    print("Local stack shutdown is not implemented yet.")
    print(f"volumes={args.volumes}")
    return 0


def handle_run(args: argparse.Namespace) -> int:
    config = load_config()
    return execute_prompt(args.task, config, tenant=args.tenant, agent=args.agent, as_json=args.json)


def handle_runs(args: argparse.Namespace) -> int:
    print("Run inspection is not implemented yet.")
    if hasattr(args, "run_id"):
        print(f"run_id={args.run_id}")
    return 0


def handle_approvals(args: argparse.Namespace) -> int:
    print("Approval actions are not implemented yet.")
    if hasattr(args, "approval_id"):
        print(f"approval_id={args.approval_id}")
    return 0


def handle_doctor() -> int:
    config = load_config()
    profile_name, profile = get_active_profile(config)

    print("Doctor")
    print(f"- Config path: {CONFIG_PATH}")
    print(f"- Config exists: {'yes' if CONFIG_PATH.exists() else 'no'}")
    print(f"- Active profile: {profile_name or 'none'}")
    print(f"- Base URL: {profile.get('base_url') if profile else 'unset'}")
    print(f"- Auth configured: {'yes' if profile and (profile.get('access_token') or profile.get('api_key')) else 'no'}")
    print(f"- TLS insecure: {'yes' if profile and profile.get('tls_insecure') else 'no'}")
    print(f"- CA bundle: {profile.get('ca_bundle') if profile and profile.get('ca_bundle') else 'unset'}")
    print(f"- Docker Compose file in repo: {'yes' if Path('docker-compose.yml').exists() else 'no'}")
    print(f"- HOME: {os.environ.get('HOME', 'unset')}")

    if profile and profile.get("base_url"):
        status_code, response = http_json(
            "GET",
            api_url(profile["base_url"], "/api/v1/auth/me"),
            headers=auth_headers(profile),
            profile=profile,
        )
        print(f"- Auth check: {status_code or 'network error'}")
        if status_code and status_code >= 400:
            print(f"- Auth detail: {describe_error(status_code, response)}")
    return 0


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "up":
        return handle_up(args)
    if args.command == "down":
        return handle_down(args)
    if args.command == "connect":
        return handle_connect(args)
    if args.command == "auth":
        return handle_auth(args)
    if args.command == "run":
        return handle_run(args)
    if args.command == "runs":
        return handle_runs(args)
    if args.command == "approvals":
        return handle_approvals(args)
    if args.command == "doctor":
        return handle_doctor()

    return run_shell()


KNOWN_COMMANDS = {"up", "down", "connect", "auth", "run", "runs", "approvals", "doctor"}


def main(argv: list[str] | None = None) -> int:
    raw_args = argv if argv is not None else os.sys.argv[1:]

    # Treat any first token that is not a known subcommand or help flag as a one-shot prompt.
    if raw_args and raw_args[0] not in KNOWN_COMMANDS and raw_args[0] not in {"-h", "--help"}:
        config = load_config()
        return execute_prompt(" ".join(raw_args), config)

    parser = build_parser()
    args = parser.parse_args(raw_args)
    return dispatch(args)
