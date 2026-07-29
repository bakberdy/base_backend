#!/usr/bin/env python3
"""Validate immutable deployment inputs and stored security evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
REFERENCE_PATTERN = re.compile(
    r"^(?P<repository>[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com(?:\.cn)?/"
    r"[a-z0-9._/-]+)@(?P<digest>sha256:[0-9a-f]{64})$"
)
EVIDENCE_ID_PATTERN = re.compile(
    r"^(?P<run_id>[0-9]+):(?P<run_attempt>[0-9]+):"
    r"(?P<digest>sha256:[0-9a-f]{64})$"
)


def validate_inputs(source_sha: str, image_reference: str, evidence_id: str) -> dict[str, str]:
    if not SHA_PATTERN.fullmatch(source_sha):
        raise ValueError("source_sha must be a full lowercase Git SHA")
    reference = REFERENCE_PATTERN.fullmatch(image_reference)
    if reference is None:
        raise ValueError("image_reference must be a private ECR repository@sha256 digest")
    evidence = EVIDENCE_ID_PATTERN.fullmatch(evidence_id)
    if evidence is None:
        raise ValueError("security_evidence_id must be run_id:run_attempt:sha256 digest")
    return {
        "repository": reference["repository"],
        "image_digest": reference["digest"],
        "evidence_run_id": evidence["run_id"],
        "evidence_run_attempt": evidence["run_attempt"],
        "evidence_digest": evidence["digest"],
    }


def verify_evidence(
    path: Path,
    source_sha: str,
    image_reference: str,
    expected_digest: str,
) -> dict[str, Any]:
    evidence_bytes = path.read_bytes()
    actual_digest = "sha256:" + hashlib.sha256(evidence_bytes).hexdigest()
    if actual_digest != expected_digest:
        raise ValueError("security evidence content hash does not match security_evidence_id")
    evidence = json.loads(evidence_bytes)
    expected = {
        "source_sha": source_sha,
        "image_reference": image_reference,
        "signing_status": "COMPLETE",
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ValueError(f"security evidence {key} does not match deployment input")
    if not str(evidence.get("scanner", "")).startswith("Trivy "):
        raise ValueError("security evidence was not produced by the authoritative Trivy scanner")
    if not DIGEST_PATTERN.fullmatch(str(evidence.get("scan_report_digest", ""))):
        raise ValueError("security evidence has no valid Trivy report digest")
    predicates = set(evidence.get("attestation_predicate_types", []))
    if "https://spdx.dev/Document" not in predicates or not any(
        value.startswith("https://slsa.dev/provenance/") for value in predicates
    ):
        raise ValueError("security evidence must include SPDX SBOM and SLSA provenance")
    return evidence


def append_github_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--image-reference", required=True)
    parser.add_argument("--security-evidence-id", required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    try:
        values = validate_inputs(
            args.source_sha,
            args.image_reference,
            args.security_evidence_id,
        )
        if args.evidence is not None:
            verify_evidence(
                args.evidence,
                args.source_sha,
                args.image_reference,
                values["evidence_digest"],
            )
        if args.github_output is not None:
            append_github_output(args.github_output, values)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Deployment policy failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
