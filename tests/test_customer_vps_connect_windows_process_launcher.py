from pathlib import Path

import pytest

import backend.commercial.customer_vps_connect_windows_process_launcher as module

from backend.commercial.customer_vps_connect_windows_process_launcher import (
    CustomerVPSConnectWindowsProcessLauncher,
)


def test_launch_uses_exact_argv_without_shell(
    monkeypatch,
    tmp_path,
):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"terminal")

    calls = []

    class FakeProcess:
        pid = 4321

    def fake_popen(
        argv,
        **kwargs,
    ):
        calls.append(
            (
                argv,
                kwargs,
            )
        )
        return FakeProcess()

    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        fake_popen,
    )

    launcher = (
        CustomerVPSConnectWindowsProcessLauncher()
    )

    process_id = launcher.launch(
        executable=str(terminal),
        arguments=(
            r"/config:C:\TODOBA\TODOBA_VPS_Startup.ini",
        ),
    )

    assert process_id == 4321

    assert calls == [
        (
            [
                str(terminal),
                r"/config:C:\TODOBA\TODOBA_VPS_Startup.ini",
            ],
            {},
        )
    ]


def test_missing_executable_fails_closed(
    tmp_path,
):
    launcher = (
        CustomerVPSConnectWindowsProcessLauncher()
    )

    with pytest.raises(
        FileNotFoundError,
    ):
        launcher.launch(
            executable=str(
                tmp_path
                / "terminal64.exe"
            ),
            arguments=(
                r"/config:C:\TODOBA\startup.ini",
            ),
        )


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("",),
        ("   ",),
        ("x\n/portable",),
    ],
)
def test_invalid_arguments_fail_closed(
    tmp_path,
    arguments,
):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"terminal")

    launcher = (
        CustomerVPSConnectWindowsProcessLauncher()
    )

    with pytest.raises(
        ValueError,
    ):
        launcher.launch(
            executable=str(terminal),
            arguments=arguments,
        )


def test_process_adapter_has_no_shell_or_shutdown_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_windows_process_launcher.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "shell=True",
        "os.system",
        "terminate(",
        "kill(",
        "login(",
        "password",
        "migrate",
        "purchase",
    ):
        assert forbidden not in source
