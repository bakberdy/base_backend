from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tool" / "ci"))

import ecr_image_policy  # noqa: E402

TOP_DIGEST = "sha256:" + "a" * 64
PLATFORM_DIGEST = "sha256:" + "b" * 64
ATTESTATION_DIGEST = "sha256:" + "c" * 64


def test_resolve_attested_linux_amd64_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    manifests = {
        TOP_DIGEST: {
            "manifests": [
                {
                    "digest": PLATFORM_DIGEST,
                    "platform": {"os": "linux", "architecture": "amd64"},
                },
                {
                    "digest": ATTESTATION_DIGEST,
                    "annotations": {
                        "vnd.docker.reference.digest": PLATFORM_DIGEST,
                        "vnd.docker.reference.type": "attestation-manifest",
                    },
                    "platform": {"os": "unknown", "architecture": "unknown"},
                },
            ]
        },
        ATTESTATION_DIGEST: {
            "layers": [
                {"annotations": {"in-toto.io/predicate-type": "https://spdx.dev/Document"}},
                {"annotations": {"in-toto.io/predicate-type": "https://slsa.dev/provenance/v0.2"}},
            ]
        },
    }
    monkeypatch.setattr(
        ecr_image_policy,
        "image_manifest",
        lambda _repository, digest, _media_types: manifests[digest],
    )

    digest, predicates = ecr_image_policy.resolve_attested_platform("template-backend", TOP_DIGEST)

    assert digest == PLATFORM_DIGEST
    assert predicates == [
        "https://slsa.dev/provenance/v0.2",
        "https://spdx.dev/Document",
    ]


def test_fixable_high_finding_is_blocked() -> None:
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2099-0001",
                        "Severity": "HIGH",
                        "FixedVersion": "2.0.0",
                    }
                ]
            }
        ]
    }

    with pytest.raises(RuntimeError, match="CVE-2099-0001"):
        ecr_image_policy.enforce_findings(report)


def test_unfixed_critical_finding_remains_visible_but_does_not_block() -> None:
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2099-0002",
                        "Severity": "CRITICAL",
                        "FixedVersion": "",
                    }
                ]
            }
        ]
    }

    blocked, applied = ecr_image_policy.enforce_findings(report)

    assert blocked == []
    assert applied == []


def test_trivy_report_must_reference_deployable_platform_digest(tmp_path: Path) -> None:
    report = tmp_path / "trivy.json"
    report.write_text(
        '{"SchemaVersion":2,"ArtifactName":"repository@sha256:' + "d" * 64 + '","Results":[]}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="not linked"):
        ecr_image_policy.load_trivy_report(report, PLATFORM_DIGEST)


def test_trivy_report_accepts_deployable_platform_digest(tmp_path: Path) -> None:
    report = tmp_path / "trivy.json"
    report.write_text(
        '{"SchemaVersion":2,"ArtifactName":"repository@' + PLATFORM_DIGEST + '","Results":[]}',
        encoding="utf-8",
    )

    parsed, report_digest = ecr_image_policy.load_trivy_report(report, PLATFORM_DIGEST)

    assert parsed["ArtifactName"] == f"repository@{PLATFORM_DIGEST}"
    assert report_digest.startswith("sha256:")
