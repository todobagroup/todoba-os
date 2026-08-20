import json

import pytest

import backend.config as config


def _set_legacy_trusted_agent_config(
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
        "TODOBA_EXECUTION_TARGETS_JSON",
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
        "agent-secret-a",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT",
        "account-a",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_MISSION_SIGNING_SECRET",
        "execution-key-a",
    )

    monkeypatch.setattr(
        config,
        "TODOBA_CONTROL_MISSION_SIGNING_SECRET",
        "control-key-a",
    )


def _set_multi_agent_config(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        config,
        "TODOBA_TRUSTED_AGENTS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "agent_secret": "agent-secret-a",
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
                    "agent_secret": "agent-secret-b",
                    "account_fingerprint": "account-b",
                    "execution_mission_signing_secret": (
                        "execution-key-b"
                    ),
                    "control_mission_signing_secret": (
                        "control-key-b"
                    ),
                },
                {
                    "agent_id": "trusted-agent-003",
                    "agent_secret": "agent-secret-c",
                    "account_fingerprint": "account-c",
                    "execution_mission_signing_secret": (
                        "execution-key-c"
                    ),
                    "control_mission_signing_secret": (
                        "control-key-c"
                    ),
                },
            ]
        ),
        raising=False,
    )


def test_execution_targets_fall_back_to_legacy_single_agent(
    monkeypatch,
) -> None:
    _set_legacy_trusted_agent_config(
        monkeypatch
    )

    targets = config.get_execution_targets()

    assert targets == (
        {
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "account-a",
        },
    )


def test_execution_targets_accept_multi_target_json(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "account_fingerprint": "account-a",
                },
                {
                    "agent_id": "trusted-agent-003",
                    "account_fingerprint": "account-c",
                },
            ]
        ),
        raising=False,
    )

    targets = config.get_execution_targets()

    assert targets == (
        {
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "account-a",
        },
        {
            "agent_id": "trusted-agent-003",
            "account_fingerprint": "account-c",
        },
    )


def test_execution_targets_preserve_configured_order(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-003",
                    "account_fingerprint": "account-c",
                },
                {
                    "agent_id": "trusted-agent-001",
                    "account_fingerprint": "account-a",
                },
            ]
        ),
        raising=False,
    )

    targets = config.get_execution_targets()

    assert [
        target["agent_id"]
        for target in targets
    ] == [
        "trusted-agent-003",
        "trusted-agent-001",
    ]


def test_execution_targets_require_routing_config_for_multi_agent(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        "",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="TODOBA_EXECUTION_TARGETS_JSON.*required",
    ):
        config.get_execution_targets()


def test_execution_targets_reject_unknown_agent(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-999",
                    "account_fingerprint": "account-z",
                },
            ]
        ),
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not a configured Trusted Agent",
    ):
        config.get_execution_targets()


def test_execution_targets_reject_account_mismatch(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "account_fingerprint": "account-b",
                },
            ]
        ),
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="account_fingerprint",
    ):
        config.get_execution_targets()


def test_execution_targets_reject_duplicate_agent(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        json.dumps(
            [
                {
                    "agent_id": "trusted-agent-001",
                    "account_fingerprint": "account-a",
                },
                {
                    "agent_id": "trusted-agent-001",
                    "account_fingerprint": "account-a",
                },
            ]
        ),
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="Duplicate execution target",
    ):
        config.get_execution_targets()


def test_execution_targets_reject_invalid_json(
    monkeypatch,
) -> None:
    _set_multi_agent_config(
        monkeypatch
    )

    monkeypatch.setattr(
        config,
        "TODOBA_EXECUTION_TARGETS_JSON",
        "{invalid-json",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="TODOBA_EXECUTION_TARGETS_JSON",
    ):
        config.get_execution_targets()