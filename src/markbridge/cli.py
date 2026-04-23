"""CLI entrypoint for backend-first MarkBridge runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from markbridge.audit import run_document_ir_audit
from markbridge.api.config import get_settings
from markbridge.api.service import MarkBridgePipeline
from markbridge.experiments import run_first_formula_probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="markbridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    local = subparsers.add_parser("parse-file")
    local.add_argument("path")
    local.add_argument("--llm", action="store_true")
    local.add_argument("--parser-hint")

    s3 = subparsers.add_parser("parse-s3")
    s3.add_argument("s3_uri")
    s3.add_argument("--llm", action="store_true")
    s3.add_argument("--parser-hint")

    probe = subparsers.add_parser("probe-first-formula")
    probe.add_argument("run_dir")
    probe.add_argument("--llm", action="store_true")

    audit_ir = subparsers.add_parser("audit-document-ir")
    audit_ir.add_argument("inputs", nargs="+")
    audit_ir.add_argument("--output-dir")
    audit_ir.add_argument("--include-blocks", action="store_true")
    audit_ir.add_argument("--parser-hint")

    subparsers.add_parser("runtime-status")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    service = MarkBridgePipeline(get_settings())

    if args.command == "parse-file":
        path = Path(args.path)
        response = service.submit_local_upload(
            filename=path.name,
            content=path.read_bytes(),
            llm_requested=args.llm,
            parser_hint=args.parser_hint,
        )
    elif args.command == "parse-s3":
        response = service.submit_s3_uri(
            s3_uri=args.s3_uri,
            llm_requested=args.llm,
            parser_hint=args.parser_hint,
        )
    elif args.command == "probe-first-formula":
        response = run_first_formula_probe(
            Path(args.run_dir),
            settings=get_settings(),
            call_llm=args.llm,
        )
    elif args.command == "audit-document-ir":
        response = run_document_ir_audit(
            inputs=list(args.inputs),
            output_dir=Path(args.output_dir) if args.output_dir else None,
            include_blocks=bool(args.include_blocks),
            parser_hint=args.parser_hint,
        )
    else:
        from markbridge.routing.runtime import get_runtime_statuses

        response = {
            "parsers": {
                parser_id: {
                    "installed": status.installed,
                    "enabled": status.enabled,
                    "reason": status.reason,
                    "supported_formats": [item.value for item in status.supported_formats],
                    "route_kind": status.route_kind,
                }
                for parser_id, status in get_runtime_statuses().items()
            }
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return

    body = response.model_dump(mode="json") if hasattr(response, "model_dump") else response
    print(json.dumps(body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
