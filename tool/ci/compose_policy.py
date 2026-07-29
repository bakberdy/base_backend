#!/usr/bin/env python3
"""Validate rendered Compose configuration for dangerous runtime privileges."""

from __future__ import annotations

import json
import sys
from typing import Any

SENSITIVE_BIND_SOURCES = {
    "/",
    "/etc",
    "/proc",
    "/sys",
    "/var/run",
    "/var/run/docker.sock",
}


def validate_service(name: str, service: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if service.get("privileged") is True:
        errors.append(f"{name}: privileged containers are forbidden")
    for field in ("ipc", "network_mode", "pid"):
        if service.get(field) == "host":
            errors.append(f"{name}: {field}=host is forbidden")
    if "ALL" in service.get("cap_add", []):
        errors.append(f"{name}: cap_add ALL is forbidden")
    unsafe_security_options = {"apparmor=unconfined", "seccomp=unconfined"}
    for option in service.get("security_opt", []):
        if option in unsafe_security_options:
            errors.append(f"{name}: security_opt {option} is forbidden")
    for volume in service.get("volumes", []):
        if volume.get("type") != "bind":
            continue
        source = volume.get("source")
        if source in SENSITIVE_BIND_SOURCES or source.startswith(("/proc/", "/sys/")):
            errors.append(f"{name}: sensitive host bind {source} is forbidden")
        if not volume.get("read_only", False):
            errors.append(f"{name}: host bind {source} must be read-only")
    return errors


def main() -> int:
    try:
        compose = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"invalid rendered Compose JSON: {error}", file=sys.stderr)
        return 1
    services = compose.get("services")
    if not isinstance(services, dict) or not services:
        print("rendered Compose configuration has no services", file=sys.stderr)
        return 1
    errors = [
        error for name, service in services.items() for error in validate_service(name, service)
    ]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Compose security policy passed for {len(services)} services.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
