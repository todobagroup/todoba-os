from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _run_config_probe(
    *,
    environment: dict[str, str],
) -> list[str]:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from backend import config; "
                "print(config.ENV_FILE.resolve()); "
                "print(config.TODOBA_API_HOST)"
            ),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        completed.stdout
        + completed.stderr
    )

    return [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def test_external_runtime_config_file_is_authoritative(
    tmp_path: Path,
):
    external_env = (
        tmp_path
        / "production.env"
    )

    external_env.write_text(
        "TODOBA_API_HOST=203.0.113.77\n",
        encoding="utf-8",
    )

    environment = os.environ.copy()

    environment.pop(
        "TODOBA_API_HOST",
        None,
    )

    environment["TODOBA_ENV_FILE"] = str(
        external_env.resolve()
    )

    output = _run_config_probe(
        environment=environment,
    )

    assert output == [
        str(
            external_env.resolve()
        ),
        "203.0.113.77",
    ]


def test_default_runtime_config_file_remains_repository_env():
    environment = os.environ.copy()

    environment.pop(
        "TODOBA_ENV_FILE",
        None,
    )

    output = _run_config_probe(
        environment=environment,
    )

    expected_env = (
        REPOSITORY_ROOT
        / ".env"
    ).resolve()

    assert output[0] == str(
        expected_env
    )


def test_relative_external_runtime_config_file_is_rejected():
    environment = os.environ.copy()

    environment["TODOBA_ENV_FILE"] = (
        "relative"
        + os.sep
        + "production.env"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend import config",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0

    combined_output = (
        completed.stdout
        + completed.stderr
    )

    assert (
        "TODOBA_ENV_FILE must be an absolute path."
        in combined_output
    )