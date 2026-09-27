#!/usr/bin/env python3
"""Pull Oura Ring and Eight Sleep data into timestamped JSON files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from collectors import CollectorError
from collectors.eight_sleep import EightSleepClient
from collectors.oura import OuraClient

ROOT = Path(__file__).resolve().parent


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _date_range(args: argparse.Namespace) -> tuple[date, date]:
    end = args.end or date.today()
    if args.start:
        start = args.start
    else:
        lookback = int(os.environ.get("LOOKBACK_DAYS", "7"))
        start = end - timedelta(days=max(lookback - 1, 0))
    if start > end:
        raise SystemExit("start date must be on or before end date")
    return start, end


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def main() -> int:
    load_dotenv(ROOT / ".env")
    # Prefer refreshed tokens written by OuraClient
    load_dotenv(ROOT / "tokens" / "oura.env", override=True)

    parser = argparse.ArgumentParser(
        description="Collect Oura Ring and Eight Sleep sleep/health data."
    )
    parser.add_argument(
        "--source",
        choices=("all", "oura", "eight"),
        default="all",
        help="Which source(s) to pull (default: all)",
    )
    parser.add_argument("--start", type=_parse_date, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=_parse_date, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "data")),
        help="Directory for JSON output (default: data/)",
    )
    args = parser.parse_args()
    start, end = _date_range(args)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    errors: list[str] = []

    if args.source in ("all", "oura"):
        try:
            oura = OuraClient.from_env(token_path=ROOT / "tokens" / "oura.env")
            payload = oura.collect(start_date=start, end_date=end)
            _write_json(out_dir / f"oura_{stamp}.json", payload)
            _write_json(out_dir / "oura_latest.json", payload)
        except CollectorError as exc:
            errors.append(f"Oura: {exc}")
            print(f"Oura failed: {exc}", file=sys.stderr)

    if args.source in ("all", "eight"):
        try:
            eight = EightSleepClient.from_env()
            payload = eight.collect(start_date=start, end_date=end)
            _write_json(out_dir / f"eight_sleep_{stamp}.json", payload)
            _write_json(out_dir / "eight_sleep_latest.json", payload)
        except CollectorError as exc:
            errors.append(f"Eight Sleep: {exc}")
            print(f"Eight Sleep failed: {exc}", file=sys.stderr)

    if errors and args.source == "all" and len(errors) == 2:
        return 1
    if errors and args.source != "all":
        return 1
    if errors:
        print("Completed with partial failures.", file=sys.stderr)
        return 2
    print(f"Done ({start.isoformat()} → {end.isoformat()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
