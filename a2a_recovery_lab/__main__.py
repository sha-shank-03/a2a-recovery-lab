"""Offline M2 entry point. Run from the repository root."""

import argparse
import json
from pathlib import Path

from .demo import format_report
from .scenarios import CORE_SCENARIOS, run_scenario, run_suite
from .wire import WireError


def main():
    parser = argparse.ArgumentParser(description="A2A 1.0 deterministic local HTTP recovery lab (M2)")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run a bounded owned-peer recovery scenario or eight-scenario suite")
    choice = demo.add_mutually_exclusive_group()
    choice.add_argument("--scenario", choices=CORE_SCENARIOS)
    choice.add_argument("--suite", choices=["core"])
    demo.add_argument("--seed", type=int, default=7, help="Scope reproducible message IDs; fault stages use fixed gates/counts")
    demo.add_argument("--out", type=Path, required=True, help="New directory for trace, report, and agent databases")
    reader = commands.add_parser("report", help="Read existing evidence; does not execute agents")
    reader.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            report = run_suite(args.out, args.seed) if args.suite else run_scenario(args.scenario or "happy-path", args.out, args.seed)
            print(format_report(report))
            print(f"Report: {(args.out / 'report.json').resolve()}")
            if not args.suite:
                print(f"Trace: {(args.out / 'events.jsonl').resolve()}")
        else:
            report = json.loads(args.path.read_text(encoding="utf-8"))
            print(format_report(report))
            print("Mode: recorded_report_read; no fresh agent execution")
        return 0 if report["verdict"] == "pass" else 1
    except FileExistsError:
        parser.exit(2, "Output directory already exists; choose a new --out directory.\n")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, WireError) as exc:
        parser.exit(2, f"Local lab error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
