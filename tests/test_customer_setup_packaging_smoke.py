"""
Tests for TODOBA Windows Customer Setup Packaging Proof.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import tempfile

import pytest

import scripts.build_customer_setup_packaging_proof as build_module
import scripts.customer_setup_packaging_smoke as smoke_module


def test_packaging_smoke_loads_required_runtime(
) -> None:
    result = (
        smoke_module.run_packaging_smoke()
    )

    assert (
        result[0]
        == "TODOBA_PACKAGING_SMOKE=GREEN"
    )

    assert any(
        value.startswith(
            "FROZEN="
        )
        for value in result
    )

    assert any(
        value.startswith(
            "TCL=8.6"
        )
        for value in result
    )

    assert (
        "TK=8.6"
        in result
    )

    assert any(
        value.startswith(
            "METATRADER5="
        )
        for value in result
    )

    assert (
        "CUSTOMER_SETUP_LAUNCHER=READY"
        in result
    )


def test_packaging_smoke_does_not_run_customer_flow(
    monkeypatch,
) -> None:
    def forbidden_run(
        self,
    ):
        del self

        raise AssertionError(
            "Packaging smoke must not run "
            "customer Setup."
        )

    monkeypatch.setattr(
        smoke_module.CustomerSetupLauncher,
        "run",
        forbidden_run,
    )

    result = (
        smoke_module.run_packaging_smoke()
    )

    assert (
        "TODOBA_PACKAGING_SMOKE=GREEN"
        in result
    )


def test_packaging_smoke_uses_non_real_bootstrap_values(
) -> None:
    assert (
        smoke_module._SMOKE_BASE_URL
        == "https://packaging-proof.invalid"
    )

    assert (
        smoke_module._SMOKE_LAUNCH_CREDENTIAL
        == "packaging-proof-not-a-real-credential"
    )


def test_packaging_smoke_source_has_no_network_call(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup_packaging_smoke.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        1,
                    )[0]
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        1,
                    )[0]
                )

    assert {
        "httpx",
        "requests",
        "urllib3",
    }.isdisjoint(
        imported_roots
    )


def test_packaging_smoke_does_not_call_launcher_run(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup_packaging_smoke.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    launcher_run_calls = [
        node
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr == "run"
        )
    ]

    assert launcher_run_calls == []


def test_packaging_smoke_contains_no_real_customer_identity(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup_packaging_smoke.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "customer_id=",
        "deployment_id=",
        "agent_id=",
        "account_fingerprint=",
        "registration_request_id=",
        "grant_request_id=",
        "handoff_credential=",
    )

    for token in forbidden:
        assert token not in source


@pytest.mark.parametrize(
    "forbidden_token",
    (
        ".exchange(",
        ".provision(",
        ".download_package(",
        ".install(",
        ".mainloop(",
    ),
)
def test_packaging_smoke_has_no_customer_action(
    forbidden_token,
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup_packaging_smoke.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert forbidden_token not in source


def test_build_recipe_locks_validated_pyinstaller_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        build_module,
        "_read_pyinstaller_version",
        lambda: "6.22.2",
    )

    build_module._validate_build_environment()


def test_build_recipe_rejects_other_pyinstaller_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        build_module,
        "_read_pyinstaller_version",
        lambda: "6.22.1",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported PyInstaller version",
    ):
        build_module._validate_build_environment()


def test_build_recipe_collects_mt5_and_numpy(
) -> None:
    command = (
        build_module._build_command()
    )

    assert command[:3] == (
        sys.executable,
        "-m",
        "PyInstaller",
    )

    assert "--onedir" in command
    assert "--console" in command
    assert "--clean" in command

    collect_positions = [
        index
        for index, value in enumerate(
            command
        )
        if value == "--collect-all"
    ]

    collected_packages = {
        command[index + 1]
        for index in collect_positions
    }

    assert collected_packages == {
        "MetaTrader5",
        "numpy",
    }

    hidden_index = command.index(
        "--hidden-import"
    )

    assert (
        command[hidden_index + 1]
        == "numpy._core.multiarray"
    )


def test_build_recipe_places_artifacts_outside_repository(
) -> None:
    command = (
        build_module._build_command()
    )

    proof_root = (
        build_module._proof_root().resolve()
    )

    repository_root = (
        build_module._repository_root().resolve()
    )

    assert (
        proof_root.parent
        == Path(
            tempfile.gettempdir()
        ).resolve()
    )

    assert (
        repository_root
        not in proof_root.parents
    )

    for option in (
        "--distpath",
        "--workpath",
        "--specpath",
    ):
        option_index = (
            command.index(
                option
            )
        )

        configured_path = Path(
            command[
                option_index + 1
            ]
        ).resolve()

        assert (
            proof_root
            in configured_path.parents
        )


def test_packaging_proof_accepts_required_frozen_markers(
) -> None:
    build_module._validate_smoke_output(
        (
            "TODOBA_PACKAGING_SMOKE=GREEN",
            "FROZEN=1",
            "TCL=8.6.15",
            "TK=8.6",
            "METATRADER5=5.0.5735",
            "CUSTOMER_SETUP_LAUNCHER=READY",
        )
    )


def test_packaging_proof_rejects_missing_frozen_marker(
) -> None:
    with pytest.raises(
        RuntimeError,
        match="missing required marker",
    ):
        build_module._validate_smoke_output(
            (
                "TODOBA_PACKAGING_SMOKE=GREEN",
                "FROZEN=0",
                "TCL=8.6.15",
                "TK=8.6",
                "METATRADER5=5.0.5735",
                "CUSTOMER_SETUP_LAUNCHER=READY",
            )
        )


def test_run_packaging_proof_executes_gates_in_order(
    monkeypatch,
    tmp_path,
) -> None:
    events = []

    executable_path = (
        tmp_path
        / "TODOBA_Packaging_Smoke.exe"
    )

    monkeypatch.setattr(
        build_module,
        "_validate_build_environment",
        lambda: events.append(
            "validate"
        ),
    )

    monkeypatch.setattr(
        build_module,
        "_prepare_proof_root",
        lambda: events.append(
            "prepare"
        ),
    )

    monkeypatch.setattr(
        build_module,
        "_run_build",
        lambda: events.append(
            "build"
        ),
    )

    def run_smoke():
        events.append(
            "smoke"
        )

        return (
            "TODOBA_PACKAGING_SMOKE=GREEN",
            "FROZEN=1",
            "TCL=8.6.15",
            "TK=8.6",
            "METATRADER5=5.0.5735",
            "CUSTOMER_SETUP_LAUNCHER=READY",
        )

    monkeypatch.setattr(
        build_module,
        "_run_packaged_smoke",
        run_smoke,
    )

    original_validate = (
        build_module._validate_smoke_output
    )

    def validate_output(
        output_lines,
    ):
        events.append(
            "validate_output"
        )

        original_validate(
            output_lines
        )

    monkeypatch.setattr(
        build_module,
        "_validate_smoke_output",
        validate_output,
    )

    monkeypatch.setattr(
        build_module,
        "_packaged_executable_path",
        lambda: executable_path,
    )

    result = (
        build_module.run_packaging_proof()
    )

    assert result == executable_path

    assert events == [
        "validate",
        "prepare",
        "build",
        "smoke",
        "validate_output",
    ]


def test_build_owner_source_has_no_network_client(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "build_customer_setup_packaging_proof.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        1,
                    )[0]
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        1,
                    )[0]
                )

    assert {
        "httpx",
        "requests",
        "urllib3",
    }.isdisjoint(
        imported_roots
    )
