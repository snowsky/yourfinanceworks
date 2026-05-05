from cli.finance_agent_cli.app import build_parser


def test_build_parser_supports_monitor_command():
    parser = build_parser()
    args = parser.parse_args(["portfolio", "monitor", "--once", "--interval", "60"])

    assert args.resource == "portfolio"
    assert args.action == "monitor"
    assert args.once is True
    assert args.interval == 60


def test_build_parser_supports_auth_login_command():
    parser = build_parser()
    args = parser.parse_args(["auth", "login", "--email", "user@example.com"])

    assert args.resource == "auth"
    assert args.action == "login"
    assert args.email == "user@example.com"


def test_build_parser_supports_auth_status_command():
    parser = build_parser()
    args = parser.parse_args(["auth", "status"])

    assert args.resource == "auth"
    assert args.action == "status"


def test_build_parser_supports_browser_login_command():
    parser = build_parser()
    args = parser.parse_args(["auth", "browser-login", "--no-open", "--timeout", "30"])

    assert args.resource == "auth"
    assert args.action == "browser-login"
    assert args.no_open is True
    assert args.timeout == 30


def test_build_parser_supports_snapshot_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "portfolio",
            "monitor",
            "--once",
            "--history-path",
            "history.jsonl",
            "--snapshot-dir",
            "snapshots",
        ]
    )

    assert args.history_path == "history.jsonl"
    assert args.snapshot_dir == "snapshots"


def test_build_parser_supports_research_command():
    parser = build_parser()
    args = parser.parse_args(
        ["portfolio", "research", "12", "--lookback-days", "5", "--max-holdings", "4"]
    )

    assert args.resource == "portfolio"
    assert args.action == "research"
    assert args.portfolio_id == 12
    assert args.lookback_days == 5
    assert args.max_holdings == 4


def test_build_parser_supports_document_scan_send():
    parser = build_parser()
    args = parser.parse_args(
        [
            "documents",
            "scan",
            "incoming",
            "--send",
            "--portfolio-id",
            "7",
            "--export-destination-id",
            "3",
        ]
    )

    assert args.resource == "documents"
    assert args.action == "scan"
    assert args.folder == "incoming"
    assert args.send is True
    assert args.portfolio_id == 7
    assert args.export_destination_id == 3


def test_build_parser_supports_agent_chat_message():
    parser = build_parser()
    args = parser.parse_args(["agent", "chat", "create", "organization", "Acme"])

    assert args.resource == "agent"
    assert args.action == "chat"
    assert args.message == ["create", "organization", "Acme"]
