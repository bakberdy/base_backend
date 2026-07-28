from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROLLOUT = PROJECT_ROOT / "deploy" / "ec2" / "rollout.sh"
REPOSITORY = "227755137079.dkr.ecr.eu-central-1.amazonaws.com/template-backend"
PREVIOUS = REPOSITORY + "@sha256:" + "a" * 64
HEALTHY = REPOSITORY + "@sha256:" + "b" * 64
UNHEALTHY = REPOSITORY + "@sha256:" + "c" * 64


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def rollout_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    app_directory = tmp_path / "opt" / "template-backend-development"
    state_directory = app_directory / ".deployment"
    state_directory.mkdir(parents=True)
    (state_directory / "current-image").write_text(PREVIOUS + "\n", encoding="utf-8")
    bootstrap = tmp_path / "bootstrap.sh"
    probe = tmp_path / "health.sh"
    write_executable(
        bootstrap,
        '#!/usr/bin/env bash\nset -eu\nprintf "%s\\n" "$2" >"${APP_BASE_DIRECTORY}/candidate"\n',
    )
    write_executable(
        probe,
        '#!/usr/bin/env bash\nset -eu\ncandidate="$(<"${APP_BASE_DIRECTORY}/candidate")"\n'
        '[[ "${candidate}" != *"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" ]]\n',
    )
    environment = os.environ | {
        "APP_BASE_DIRECTORY": str(tmp_path / "opt"),
        "AWS_REGION": "eu-central-1",
        "PROJECT_NAME": "template-backend",
        "ROLLOUT_BOOTSTRAP_SCRIPT": str(bootstrap),
        "ROLLOUT_HEALTH_PROBE": str(probe),
    }
    return environment, state_directory


def test_successful_rollout_saves_previous_and_current_digest(tmp_path: Path) -> None:
    environment, state_directory = rollout_environment(tmp_path)

    result = subprocess.run(
        ["bash", str(ROLLOUT), "deploy", "development", HEALTHY],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "DEPLOYMENT_STATUS=success" in result.stdout
    assert (state_directory / "previous-image").read_text(encoding="utf-8").strip() == PREVIOUS
    assert (state_directory / "current-image").read_text(encoding="utf-8").strip() == HEALTHY


def test_failed_health_automatically_restores_previous_digest(tmp_path: Path) -> None:
    environment, state_directory = rollout_environment(tmp_path)

    result = subprocess.run(
        ["bash", str(ROLLOUT), "deploy", "development", UNHEALTHY],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "DEPLOYMENT_STATUS=rolled_back" in result.stdout
    assert (state_directory / "current-image").read_text(encoding="utf-8").strip() == PREVIOUS


def test_manual_rollback_accepts_only_an_exact_digest(tmp_path: Path) -> None:
    environment, state_directory = rollout_environment(tmp_path)
    (state_directory / "current-image").write_text(HEALTHY + "\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(ROLLOUT), "rollback", "development", PREVIOUS],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "DEPLOYMENT_STATUS=rolled_back" in result.stdout
    assert (state_directory / "current-image").read_text(encoding="utf-8").strip() == PREVIOUS
