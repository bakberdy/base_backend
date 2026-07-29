#!/usr/bin/env python3
"""Run pip-audit with only active, validated baseline exceptions."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from security_exceptions import load_registry


def main() -> int:
    requirements = Path(sys.argv[1] if len(sys.argv) > 1 else "requirements.txt")
    exceptions = [entry for entry in load_registry() if entry["type"] == "python_dependency"]
    command = [
        sys.executable,
        "-m",
        "pip_audit",
        "--strict",
        "--progress-spinner",
        "off",
        "--cache-dir",
        str(Path(tempfile.gettempdir()) / "template-backend-pip-audit"),
        "--requirement",
        str(requirements),
    ]
    for entry in exceptions:
        print(
            f"Temporary dependency exception: {entry['id']} "
            f"(owner {entry['owner']}, expires {entry['expires_on']}, task {entry['task']})"
        )
        command.extend(["--ignore-vuln", entry["id"]])
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
