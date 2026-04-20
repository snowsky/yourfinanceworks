from cli.finance_agent_cli.app import build_parser


def test_build_parser_supports_monitor_command():
    parser = build_parser()
    args = parser.parse_args(["portfolio", "monitor", "--once", "--interval", "60"])

    assert args.resource == "portfolio"
    assert args.action == "monitor"
    assert args.once is True
    assert args.interval == 60


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
