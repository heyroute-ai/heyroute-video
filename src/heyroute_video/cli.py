from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from .doctor import doctor
from .errors import VideoError
from .events import EventSink
from .manifest import load_manifests
from .pipeline import build
from .tts.index import index_tts_doctor


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print one machine-readable result object")
    parser.add_argument("--json-events", action="store_true", help="Print JSONL lifecycle events")
    parser.add_argument("--work-dir", type=Path, help="Override the generated working/output directory")
    parser.add_argument("--output-dir", type=Path, help="Override the generated output directory")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heyroute-video")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor_parser = sub.add_parser("doctor")
    _common(doctor_parser)
    validate = sub.add_parser("validate")
    validate.add_argument("--manifest", required=True, type=Path)
    _common(validate)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--manifest", required=True, type=Path)
    _common(build_parser)
    tts = sub.add_parser("tts")
    tts_sub = tts.add_subparsers(dest="tts_command", required=True)
    tts_doctor = tts_sub.add_parser("doctor")
    tts_doctor.add_argument("--project-path", type=Path)
    _common(tts_doctor)
    bootstrap = tts_sub.add_parser("bootstrap")
    bootstrap.add_argument("--project-path", type=Path)
    _common(bootstrap)
    return parser


def _print_result(result: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _validate(path: Path) -> dict[str, Any]:
    manifests = load_manifests(path.resolve())
    return {"status": "valid", "manifest": str(path.resolve()), "jobs": [manifest.job_id for manifest in manifests]}


def _apply_output_override(manifests: list[Any], args: argparse.Namespace) -> list[Any]:
    override = args.output_dir or args.work_dir
    if not override:
        return manifests
    root = override.resolve()
    updated = []
    for manifest in manifests:
        updated.append(replace(manifest, output=replace(manifest.output, directory=root / manifest.job_id)))
    return updated


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
            _print_result(result, as_json=args.json)
            return 0 if result.get("status") == "ready" else 1
        if args.command == "tts":
            result = index_tts_doctor(args.project_path)
            if args.tts_command == "bootstrap":
                result["message"] = "Bootstrap is intentionally non-destructive; install IndexTTS using its upstream instructions, then rerun doctor."
            _print_result(result, as_json=args.json)
            return 0 if result.get("status") == "ready" else 1
        manifests = _apply_output_override(load_manifests(args.manifest.resolve()), args)
        if args.command == "validate":
            _print_result({"status": "valid", "manifest": str(args.manifest.resolve()), "jobs": [m.job_id for m in manifests]}, as_json=args.json)
            return 0
        sink = EventSink(json_events=args.json_events)
        reports = [build(manifest, sink=sink) for manifest in manifests]
        result = {"status": "success", "jobs": reports}
        if args.json:
            _print_result(result, as_json=True)
        elif not args.json_events:
            _print_result(result, as_json=False)
        return 0
    except VideoError as exc:
        payload = {"status": "failed", "error": exc.as_dict()}
        if getattr(args, "json_events", False):
            EventSink(json_events=True).emit("failed", **payload)
        elif getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"[{exc.code}] {exc.message}", file=sys.stderr)
            if exc.hint:
                print(f"hint: {exc.hint}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        payload = {"status": "failed", "error": {"code": "internal.error", "message": str(exc)}}
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"[internal.error] {exc}", file=sys.stderr)
        return 1
