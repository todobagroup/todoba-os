import json

import pytest

import backend.config as config


def _set_valid_trusted_agent_config(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        "",
        raising=False,
    )

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
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    config.validate_trusted_agent_config()


def test_trusted_agent_config_requires_account_fingerprint(
    monkeypatch,
) -> None:
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


def test_trusted_agent_deployments_fall_back_to_legacy_config(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    deployments = (
        config.get_trusted_agent_deployments()
    )

    assert deployments == (
        {
            "agent_id": "trusted-agent-001",
            "agent_secret": "test-agent-secret",
            "account_fingerprint": "account-a",
            "execution_mission_signing_secret": (
                "test-execution-signing-secret"
            ),
            "control_mission_signing_secret": (
                "test-control-signing-secret"
            ),
        },
    )


def test_trusted_agent_config_accepts_multi_agent_json(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_ID",
        "",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_SECRET",
        "",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT",
        "",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_MISSION_SIGNING_SECRET",
        "",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_CONTROL_MISSION_SIGNING_SECRET",
        "",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "agent_secret": "secret-a",
                    "account_fingerprint": "account-a",
                    "execution_mission_signing_secret": (
                        "execution-key-a"
                    ),
                    "control_mission_signing_secret": (
                        "control-key-a"
                    ),
                },
                {
                    "agent_id": "trusted-agent-002",
                    "agent_secret": "secret-b",
                    "account_fingerprint": "account-b",
                    "execution_mission_signing_secret": (
                        "execution-key-b"
                    ),
                    "control_mission_signing_secret": (
                        "control-key-b"
                    ),
                },
            ]
        ),
        raising=False,
    )

    config.validate_trusted_agent_config()

    deployments = (
        config.get_trusted_agent_deployments()
    )

    assert deployments == (
        {
            "agent_id": "trusted-agent-001",
            "agent_secret": "secret-a",
            "account_fingerprint": "account-a",
            "execution_mission_signing_secret": (
                "execution-key-a"
            ),
            "control_mission_signing_secret": (
                "control-key-a"
            ),
        },
        {
            "agent_id": "trusted-agent-002",
            "agent_secret": "secret-b",
            "account_fingerprint": "account-b",
            "execution_mission_signing_secret": (
                "execution-key-b"
            ),
            "control_mission_signing_secret": (
                "control-key-b"
            ),
        },
    )


def test_trusted_agent_config_rejects_duplicate_multi_agent_ids(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "agent_secret": "secret-a",
                    "account_fingerprint": "account-a",
                    "execution_mission_signing_secret": (
                        "execution-key-a"
                    ),
                    "control_mission_signing_secret": (
                        "control-key-a"
                    ),
                },
                {
                    "agent_id": "trusted-agent-001",
                    "agent_secret": "secret-b",
                    "account_fingerprint": "account-b",
                    "execution_mission_signing_secret": (
                        "execution-key-b"
                    ),
                    "control_mission_signing_secret": (
                        "control-key-b"
                    ),
                },
            ]
        ),
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="Duplicate Trusted Agent ID",
    ):
        config.validate_trusted_agent_config()


def test_trusted_agent_config_rejects_missing_execution_signing_key(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "agent_secret": "secret-a",
                    "account_fingerprint": "account-a",
                    "control_mission_signing_secret": (
                        "control-key-a"
                    ),
                },
            ]
        ),
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="execution_mission_signing_secret",
    ):
        config.validate_trusted_agent_config()


def test_trusted_agent_config_rejects_missing_control_signing_key(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "agent_secret": "secret-a",
                    "account_fingerprint": "account-a",
                    "execution_mission_signing_secret": (
                        "execution-key-a"
                    ),
                },
            ]
        ),
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="control_mission_signing_secret",
    ):
        config.validate_trusted_agent_config()


def test_trusted_agent_config_rejects_invalid_multi_agent_json(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        "{invalid-json",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="TODOBA_TRUSTED_AGENTS_JSON",
    ):
        config.validate_trusted_agent_config()

def test_multi_agent_config_preserves_opaque_secrets_exactly(
    monkeypatch,
) -> None:
    _set_valid_trusted_agent_config(
        monkeypatch
    )

    agent_secret = "  agent-??-secret  "
    execution_secret = (
        "\texecution-???-secret\n"
    )
    control_secret = (
        " control-??-secret "
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        json.dumps(
            [
                {
                    "agent_id": (
                        " trusted-agent-opaque "
                    ),
                    "agent_secret": agent_secret,
                    "account_fingerprint": (
                        " server-opaque:1001 "
                    ),
                    "execution_mission_signing_secret": (
                        execution_secret
                    ),
                    "control_mission_signing_secret": (
                        control_secret
                    ),
                },
            ],
            ensure_ascii=False,
        ),
        raising=False,
    )

    deployments = (
        config.get_trusted_agent_deployments()
    )

    assert len(deployments) == 1

    deployment = deployments[0]

    assert (
        deployment["agent_id"]
        == "trusted-agent-opaque"
    )

    assert (
        deployment["account_fingerprint"]
        == "server-opaque:1001"
    )

    assert (
        deployment["agent_secret"]
        == agent_secret
    )

    assert (
        deployment[
            "execution_mission_signing_secret"
        ]
        == execution_secret
    )

    assert (
        deployment[
            "control_mission_signing_secret"
        ]
        == control_secret
    )
