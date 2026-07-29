#!/usr/bin/env python3
"""Validate and consume the versioned CI security exception registry."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "security" / "exceptions.json"
ALLOWED_TYPES = {"configuration", "image_vulnerability", "python_dependency"}
REQUIRED_FIELDS = {"type", "id", "reason", "owner", "task", "expires_on"}


def load_registry() -> list[dict[str, Any]]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("exceptions"), list):
        raise ValueError("security exception registry must use schema_version 1")

    today = dt.datetime.now(dt.UTC).date()
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    exceptions: list[dict[str, Any]] = []
    for index, entry in enumerate(data["exceptions"], start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"exception {index} must be an object")
        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            raise ValueError(f"exception {index} is missing: {', '.join(sorted(missing))}")
        if entry["type"] not in ALLOWED_TYPES:
            raise ValueError(f"exception {index} has unsupported type {entry['type']!r}")
        if not all(isinstance(entry[field], str) and entry[field] for field in REQUIRED_FIELDS):
            raise ValueError(f"exception {index} has an empty or non-string required field")
        if not entry["owner"].startswith("@"):
            raise ValueError(f"exception {entry['id']} owner must be an accountable handle")
        if not entry["task"].startswith("docs/security-remediation.md#"):
            raise ValueError(f"exception {entry['id']} must link to a remediation task")
        expires_on = dt.date.fromisoformat(entry["expires_on"])
        if expires_on < today:
            raise ValueError(f"security exception {entry['id']} expired on {expires_on}")

        paths = entry.get("paths", [])
        if not isinstance(paths, list) or not all(isinstance(path, str) and path for path in paths):
            raise ValueError(f"exception {entry['id']} paths must be a list of non-empty strings")
        if entry["type"] == "configuration" and not paths:
            raise ValueError(f"configuration exception {entry['id']} must be path-scoped")
        key = (entry["type"], entry["id"], tuple(paths))
        if key in seen:
            raise ValueError(f"duplicate security exception: {key}")
        seen.add(key)
        exceptions.append(entry)
    return exceptions


def write_trivy_ignore(exceptions: list[dict[str, Any]], output: Path) -> None:
    lines = ["misconfigurations:"]
    for entry in exceptions:
        if entry["type"] != "configuration":
            continue
        statement = (f"{entry['reason']} Owner: {entry['owner']}. Task: {entry['task']}.").replace(
            '"', '\\"'
        )
        lines.extend(
            [
                f"  - id: {entry['id']}",
                "    paths:",
                *(f'      - "{path}"' for path in entry["paths"]),
                f'    statement: "{statement}"',
                f"    expired_at: {entry['expires_on']}",
            ]
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("python-ids")
    trivy = subparsers.add_parser("trivy-ignore")
    trivy.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        exceptions = load_registry()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"security exception registry error: {error}", file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"Validated {len(exceptions)} active security exceptions.")
    elif args.command == "python-ids":
        for entry in exceptions:
            if entry["type"] == "python_dependency":
                print(entry["id"])
    elif args.command == "trivy-ignore":
        write_trivy_ignore(exceptions, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
