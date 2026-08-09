"""
TODOBA Proof082

API Runtime Configuration Test

Proves that the TODOBA API server:

- remains local-only by default
- uses port 8000 by default
- can be configured for remote server deployment
"""

import importlib

import backend.config as config


def reload_config(
    monkeypatch,
    *,
    host: str | None = None,
    port: str | None = None,
):
    if host is None:
        monkeypatch.delenv(
            "TODOBA_API_HOST",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "TODOBA_API_HOST",
            host,
        )

    if port is None:
        monkeypatch.delenv(
            "TODOBA_API_PORT",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "TODOBA_API_PORT",
            port,
        )

    return importlib.reload(
        config
    )


def test_api_host_defaults_to_localhost(
    monkeypatch,
) -> None:
    loaded = reload_config(
        monkeypatch,
    )

    assert loaded.TODOBA_API_HOST == (
        "127.0.0.1"
    )


def test_api_port_defaults_to_8000(
    monkeypatch,
) -> None:
    loaded = reload_config(
        monkeypatch,
    )

    assert loaded.TODOBA_API_PORT == 8000


def test_api_runtime_can_be_configured_for_server(
    monkeypatch,
) -> None:
    loaded = reload_config(
        monkeypatch,
        host="0.0.0.0",
        port="9000",
    )

    assert loaded.TODOBA_API_HOST == (
        "0.0.0.0"
    )

    assert loaded.TODOBA_API_PORT == 9000