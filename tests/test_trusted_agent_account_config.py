import pytest

import backend.config as config


def _set_valid_trusted_agent_config(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_ID",
        "trusted-agent-001",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_SECRET",
        "test-agent-secret",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT",
        "account-a",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_MISSION_SIGNING_SECRET",
        "test-execution-signing-secret",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_CONTROL_MISSION_SIGNING_SECRET",
        "test-control-signing-secret",
    )


def test_trusted_agent_config_accepts_account_fingerprint(
    monkeypatch,
):
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    config.validate_trusted_agent_config()


def test_trusted_agent_config_requires_account_fingerprint(
    monkeypatch,
):
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT",
        "",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT "
            "is required"
        ),
    ):
        config.validate_trusted_agent_config()