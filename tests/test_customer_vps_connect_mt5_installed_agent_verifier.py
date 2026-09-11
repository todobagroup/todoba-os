from pathlib import Path

import pytest

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)

from backend.commercial.customer_vps_connect_mt5_installed_agent_verifier import (
    CustomerVPSConnectMT5InstalledAgentVerifier,
)


LOGIN = 12345678
SERVER = "Broker-Pro"
FINGERPRINT = f"{SERVER}:{LOGIN}"


def _preflight(
    *,
    terminal_path,
    data_path,
):
    return CustomerMT5SetupPreflightResult(
        terminal_path=str(terminal_path),
        installation_path=str(
            Path(terminal_path).parent
        ),
        data_path=str(data_path),
        portable=False,
        login=LOGIN,
        server=SERVER,
        margin_mode=2,
        account_fingerprint=FINGERPRINT,
    )


def test_verifies_agent_only_inside_authoritative_data_path(
    tmp_path,
):
    installation = tmp_path / "MT5"
    installation.mkdir()

    terminal = installation / "terminal64.exe"
    terminal.write_bytes(b"terminal")

    data = tmp_path / "DATA"
    experts = data / "MQL5" / "Experts"
    experts.mkdir(parents=True)

    agent = experts / "TODOBA_Trusted_Agent.ex5"
    agent.write_bytes(b"agent")

    verifier = (
        CustomerVPSConnectMT5InstalledAgentVerifier()
    )

    result = verifier.verify(
        preflight_result=_preflight(
            terminal_path=terminal,
            data_path=data,
        )
    )

    assert result.terminal_path == str(terminal)
    assert result.data_path == str(data.resolve())
    assert result.account_fingerprint == FINGERPRINT
    assert result.installed_path == str(agent.resolve())


def test_missing_agent_fails_closed(
    tmp_path,
):
    installation = tmp_path / "MT5"
    installation.mkdir()

    terminal = installation / "terminal64.exe"
    terminal.write_bytes(b"terminal")

    data = tmp_path / "DATA"
    (data / "MQL5" / "Experts").mkdir(
        parents=True
    )

    verifier = (
        CustomerVPSConnectMT5InstalledAgentVerifier()
    )

    with pytest.raises(
        FileNotFoundError,
        match="Agent",
    ):
        verifier.verify(
            preflight_result=_preflight(
                terminal_path=terminal,
                data_path=data,
            )
        )


def test_installed_agent_symlink_fails_closed(
    tmp_path,
):
    installation = tmp_path / "MT5"
    installation.mkdir()

    terminal = installation / "terminal64.exe"
    terminal.write_bytes(b"terminal")

    data = tmp_path / "DATA"
    experts = data / "MQL5" / "Experts"
    experts.mkdir(parents=True)

    outside = tmp_path / "outside.ex5"
    outside.write_bytes(b"agent")

    agent = experts / "TODOBA_Trusted_Agent.ex5"

    try:
        agent.symlink_to(outside)
    except OSError:
        pytest.skip(
            "symlink creation unavailable"
        )

    verifier = (
        CustomerVPSConnectMT5InstalledAgentVerifier()
    )

    with pytest.raises(
        RuntimeError,
        match="symbolic link",
    ):
        verifier.verify(
            preflight_result=_preflight(
                terminal_path=terminal,
                data_path=data,
            )
        )


def test_verifier_has_no_install_or_process_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_mt5_installed_agent_verifier.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "write_bytes",
        "write_text",
        "os.rename",
        "replace(",
        "subprocess",
        "Popen",
        "login(",
        "password",
        "purchase",
        "migrate",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source


def test_verifier_returns_standard_installation_evidence(
    tmp_path,
):
    from backend.commercial.customer_mt5_ex5_installer_service import (
        CustomerMT5EX5InstallationResult,
    )

    installation = tmp_path / "MT5"
    installation.mkdir()

    terminal = installation / "terminal64.exe"
    terminal.write_bytes(b"terminal")

    data = tmp_path / "DATA"
    experts = data / "MQL5" / "Experts"
    experts.mkdir(parents=True)

    agent = experts / "TODOBA_Trusted_Agent.ex5"
    agent.write_bytes(b"trusted-agent")

    verifier = (
        CustomerVPSConnectMT5InstalledAgentVerifier()
    )

    result = verifier.verify(
        preflight_result=_preflight(
            terminal_path=terminal,
            data_path=data,
        )
    )

    assert isinstance(
        result,
        CustomerMT5EX5InstallationResult,
    )

    assert result.artifact_size_bytes == len(
        b"trusted-agent"
    )

    assert len(
        result.artifact_sha256
    ) == 64

    assert result.already_present is True

