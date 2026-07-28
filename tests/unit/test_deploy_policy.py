from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tool" / "ci"))

import deploy_policy  # noqa: E402

SOURCE_SHA = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64
IMAGE_REFERENCE = "227755137079.dkr.ecr.eu-central-1.amazonaws.com/template-backend@" + IMAGE_DIGEST


def evidence_file(tmp_path: Path) -> tuple[Path, str]:
    evidence = {
        "source_sha": SOURCE_SHA,
        "image_reference": IMAGE_REFERENCE,
        "scanner": "Trivy 0.72.0",
        "scan_report_digest": "sha256:" + "c" * 64,
        "signing_status": "COMPLETE",
        "attestation_predicate_types": [
            "https://spdx.dev/Document",
            "https://slsa.dev/provenance/v0.2",
        ],
    }
    path = tmp_path / "evidence.json"
    content = json.dumps(evidence, sort_keys=True).encode()
    path.write_bytes(content)
    return path, "sha256:" + hashlib.sha256(content).hexdigest()


def test_validate_exact_digest_contract() -> None:
    values = deploy_policy.validate_inputs(
        SOURCE_SHA,
        IMAGE_REFERENCE,
        "123:2:sha256:" + "d" * 64,
    )

    assert values["image_digest"] == IMAGE_DIGEST
    assert values["evidence_run_id"] == "123"


def test_tag_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="repository@sha256"):
        deploy_policy.validate_inputs(
            SOURCE_SHA,
            "227755137079.dkr.ecr.eu-central-1.amazonaws.com/template-backend:latest",
            "123:2:sha256:" + "d" * 64,
        )


def test_evidence_is_bound_to_source_image_and_hash(tmp_path: Path) -> None:
    path, digest = evidence_file(tmp_path)

    result = deploy_policy.verify_evidence(path, SOURCE_SHA, IMAGE_REFERENCE, digest)

    assert result["scanner"] == "Trivy 0.72.0"


def test_tampered_evidence_is_rejected(tmp_path: Path) -> None:
    path, digest = evidence_file(tmp_path)
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="content hash"):
        deploy_policy.verify_evidence(path, SOURCE_SHA, IMAGE_REFERENCE, digest)
