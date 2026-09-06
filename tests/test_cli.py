from threegpp.cli import build_parser


def test_ingest_cli_is_discovery_only_by_default() -> None:
    args = build_parser().parse_args(
        ["ingest-meeting", "--wg", "RAN2", "--meeting", "131"]
    )
    assert args.download_artifacts is False
    assert args.enrich_tdocs is False
