#!/usr/bin/env python3
"""Fail closed unless one ECR image digest is attested, scanned, and signed."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from security_exceptions import load_registry

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def aws_json(*arguments: str) -> dict[str, Any]:
    result = subprocess.run(
        ["aws", *arguments, "--output", "json", "--no-cli-pager"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message or f"AWS CLI exited with {result.returncode}")
    return json.loads(result.stdout)


def image_manifest(repository: str, digest: str, media_types: list[str]) -> dict[str, Any]:
    response = aws_json(
        "ecr",
        "batch-get-image",
        "--repository-name",
        repository,
        "--image-ids",
        f"imageDigest={digest}",
        "--accepted-media-types",
        *media_types,
    )
    failures = response.get("failures", [])
    if failures or len(response.get("images", [])) != 1:
        raise RuntimeError(f"ECR could not return manifest {digest}: {failures}")
    return json.loads(response["images"][0]["imageManifest"])


def resolve_attested_platform(repository: str, top_digest: str) -> tuple[str, list[str]]:
    index = image_manifest(
        repository,
        top_digest,
        [
            "application/vnd.oci.image.index.v1+json",
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
        ],
    )
    manifests = index.get("manifests")
    if not isinstance(manifests, list):
        raise RuntimeError("release artifact has no BuildKit attestation index")

    platform_digests = [
        descriptor["digest"]
        for descriptor in manifests
        if descriptor.get("platform", {}).get("os") == "linux"
        and descriptor.get("platform", {}).get("architecture") == "amd64"
    ]
    if len(platform_digests) != 1 or not DIGEST_PATTERN.fullmatch(platform_digests[0]):
        raise RuntimeError("release index must contain exactly one linux/amd64 image manifest")
    platform_digest = platform_digests[0]

    attestation_digests = [
        descriptor["digest"]
        for descriptor in manifests
        if descriptor.get("annotations", {}).get("vnd.docker.reference.digest") == platform_digest
        and descriptor.get("annotations", {}).get("vnd.docker.reference.type")
        == "attestation-manifest"
    ]
    if not attestation_digests:
        raise RuntimeError(f"no BuildKit attestations reference {platform_digest}")

    predicate_types: set[str] = set()
    for digest in attestation_digests:
        manifest = image_manifest(
            repository,
            digest,
            ["application/vnd.oci.image.manifest.v1+json"],
        )
        for layer in manifest.get("layers", []):
            predicate = layer.get("annotations", {}).get("in-toto.io/predicate-type")
            if predicate:
                predicate_types.add(predicate)

    has_sbom = "https://spdx.dev/Document" in predicate_types
    has_provenance = any(
        predicate.startswith("https://slsa.dev/provenance/") for predicate in predicate_types
    )
    if not has_sbom or not has_provenance:
        raise RuntimeError(
            f"{platform_digest} must have both SPDX SBOM and SLSA provenance attestations"
        )
    return platform_digest, sorted(predicate_types)


def enforce_findings(report: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    exceptions = {
        entry["id"] for entry in load_registry() if entry["type"] == "image_vulnerability"
    }
    blocked: list[dict[str, str]] = []
    applied: set[str] = set()
    for result in report.get("Results", []):
        for finding in result.get("Vulnerabilities") or []:
            vulnerability_id = finding.get("VulnerabilityID", "unknown")
            fixed_version = finding.get("FixedVersion") or ""
            should_block = finding.get("Severity") in {"CRITICAL", "HIGH"} and bool(
                fixed_version.strip()
            )
            if not should_block:
                continue
            if vulnerability_id in exceptions:
                applied.add(vulnerability_id)
                continue
            blocked.append(
                {
                    "id": vulnerability_id,
                    "severity": finding.get("Severity", "UNKNOWN"),
                    "fixed_version": fixed_version,
                }
            )
    if blocked:
        raise RuntimeError(
            "Trivy policy blocked fixable HIGH/CRITICAL findings: "
            + ", ".join(finding["id"] for finding in blocked)
        )
    return blocked, sorted(applied)


def load_trivy_report(path: Path, platform_digest: str) -> tuple[dict[str, Any], str]:
    report_bytes = path.read_bytes()
    report = json.loads(report_bytes)
    if report.get("SchemaVersion") != 2:
        raise RuntimeError("Trivy report must use schema version 2")
    references = [str(report.get("ArtifactName", ""))]
    references.extend(str(value) for value in report.get("Metadata", {}).get("RepoDigests", []))
    if not any(platform_digest in reference for reference in references):
        raise RuntimeError(
            f"Trivy report is not linked to deployable platform digest {platform_digest}"
        )
    return report, "sha256:" + hashlib.sha256(report_bytes).hexdigest()


def wait_for_signature(
    repository: str,
    digest: str,
    signing_profile_arn: str,
    attempts: int,
    delay: float,
) -> dict[str, Any]:
    for attempt in range(1, attempts + 1):
        result = aws_json(
            "ecr",
            "describe-image-signing-status",
            "--repository-name",
            repository,
            "--image-id",
            f"imageDigest={digest}",
        )
        statuses = [
            status
            for status in result.get("signingStatuses", [])
            if status.get("signingProfileArn") == signing_profile_arn
        ]
        if statuses:
            status = statuses[0].get("status")
            if status == "COMPLETE":
                return statuses[0]
            if status == "FAILED":
                raise RuntimeError(
                    f"managed signing failed: {statuses[0].get('failureReason', 'unknown reason')}"
                )
            if status != "IN_PROGRESS":
                raise RuntimeError(f"ECR returned unknown signing status {status!r}")
        if attempt < attempts:
            time.sleep(delay)
    raise RuntimeError(f"ECR managed signing did not complete for {digest} before timeout")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--repository-uri", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--top-digest", required=True)
    parser.add_argument("--trivy-report", type=Path, required=True)
    parser.add_argument("--trivy-version", required=True)
    parser.add_argument("--signing-profile-arn", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--attempts", type=int, default=60)
    parser.add_argument("--delay", type=float, default=10)
    args = parser.parse_args()

    try:
        if not DIGEST_PATTERN.fullmatch(args.top_digest):
            raise ValueError("top digest is invalid")
        if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha):
            raise ValueError("source SHA must be a full lowercase Git SHA")
        if not args.run_id.isdecimal() or not args.run_attempt.isdecimal():
            raise ValueError("GitHub run ID and attempt must be decimal numbers")
        if not args.signing_profile_arn.startswith("arn:aws:signer:"):
            raise ValueError("AWS_ECR_SIGNING_PROFILE_ARN is missing or invalid")

        platform_digest, predicates = resolve_attested_platform(args.repository, args.top_digest)
        report, report_digest = load_trivy_report(args.trivy_report, platform_digest)
        _, applied_exceptions = enforce_findings(report)
        signing = wait_for_signature(
            args.repository,
            platform_digest,
            args.signing_profile_arn,
            args.attempts,
            args.delay,
        )
        evidence = {
            "schema_version": 1,
            "source_sha": args.source_sha,
            "repository": args.repository,
            "top_digest": args.top_digest,
            "image_digest": platform_digest,
            "image_reference": f"{args.repository_uri}@{platform_digest}",
            "scanner": f"Trivy {args.trivy_version}",
            "scan_completed_at": datetime.now(UTC).isoformat(),
            "scan_report_digest": report_digest,
            "blocking_policy": "HIGH/CRITICAL with a non-empty fixed version",
            "applied_exceptions": applied_exceptions,
            "attestation_predicate_types": predicates,
            "signing_profile_arn": signing["signingProfileArn"],
            "signing_status": signing["status"],
        }
        canonical = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
        args.evidence.write_text(canonical, encoding="utf-8")
        evidence_digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
        evidence_id = f"{args.run_id}:{args.run_attempt}:{evidence_digest}"
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                output.write(f"source_sha={args.source_sha}\n")
                output.write(f"image_digest={platform_digest}\n")
                output.write(f"image_reference={args.repository_uri}@{platform_digest}\n")
                output.write(f"security_evidence_id={evidence_id}\n")
        print(canonical, end="")
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"ECR image policy failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
