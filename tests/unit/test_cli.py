from pathlib import Path
from tempfile import NamedTemporaryFile

from docx import Document as DocxDocument

from markbridge.cli import build_parser


def test_cli_parser_builds_parse_file_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["parse-file", "/tmp/sample.docx", "--llm"])
    assert args.command == "parse-file"
    assert args.path == "/tmp/sample.docx"
    assert args.llm is True


def test_cli_parser_builds_parse_s3_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["parse-s3", "s3://bucket/key.pdf"])
    assert args.command == "parse-s3"
    assert args.s3_uri == "s3://bucket/key.pdf"


def test_cli_parser_builds_runtime_status_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["runtime-status"])
    assert args.command == "runtime-status"


def test_cli_parser_builds_probe_first_formula_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["probe-first-formula", "/tmp/run", "--llm"])
    assert args.command == "probe-first-formula"
    assert args.run_dir == "/tmp/run"
    assert args.llm is True
