"""
TODOBA Trusted Agent Provisioned Runtime Binding Tests

CAP 3H proof:

A provisioned Trusted Agent deployment must bind runtime
identity and MT5 account ownership to deployment-generated
constants rather than mutable operator input.

Required properties:

- provisioned Agent ID is not a mutable EA input
- authentication uses the provisioned Agent ID
- mission validation uses the provisioned Agent ID
- startup reads the actual MT5 account fingerprint
- startup rejects an account mismatch before polling starts
"""

import re
from pathlib import Path

from scripts.provision_trusted_agent_deployment import (
    provision_trusted_agent_deployment,
)


ROOT_DIR = Path(__file__).resolve().parents[1]

MQL5_SOURCE_ROOT = (
    ROOT_DIR
    / "MQL5"
)


AGENT_ID = "trusted-agent-runtime-proof"

ACCOUNT_FINGERPRINT = (
    "proof-broker:880001"
)

AGENT_SECRET = (
    "proof-runtime-agent-secret"
)

EXECUTION_SECRET = (
    "proof-runtime-execution-secret"
)

CONTROL_SECRET = (
    "proof-runtime-control-secret"
)


def provision_runtime(
    tmp_path: Path,
) -> Path:
    return provision_trusted_agent_deployment(
        mql5_source_root=MQL5_SOURCE_ROOT,
        output_root=(
            tmp_path
            / "deployments"
        ),
        agent_id=AGENT_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
        agent_secret=AGENT_SECRET,
        execution_mission_signing_secret=(
            EXECUTION_SECRET
        ),
        control_mission_signing_secret=(
            CONTROL_SECRET
        ),
    )


def read_provisioned_agent(
    deployment_root: Path,
) -> str:
    agent_path = (
        deployment_root
        / "MQL5"
        / "Experts"
        / "TODOBA_Trusted_Agent.mq5"
    )

    assert agent_path.is_file()

    return agent_path.read_text(
        encoding="utf-8"
    )


def read_provisioned_credentials(
    deployment_root: Path,
) -> str:
    credential_path = (
        deployment_root
        / "MQL5"
        / "Include"
        / "TODOBAExecution"
        / "TODOBAAgentCredentials.mqh"
    )

    assert credential_path.is_file()

    return credential_path.read_text(
        encoding="utf-8"
    )


def extract_function(
    source: str,
    *,
    start_marker: str,
    end_marker: str,
) -> str:
    start = source.index(
        start_marker
    )

    end = source.index(
        end_marker,
        start,
    )

    return source[
        start:end
    ]


def compact(
    source: str,
) -> str:
    return "".join(
        source.split()
    )


def test_provisioned_agent_uses_immutable_deployment_identity(
    tmp_path: Path,
) -> None:
    deployment_root = provision_runtime(
        tmp_path
    )

    agent_source = read_provisioned_agent(
        deployment_root
    )

    credentials = (
        read_provisioned_credentials(
            deployment_root
        )
    )

    assert (
        f'const string TODOBA_AGENT_ID = "{AGENT_ID}";'
        in credentials
    )

    assert (
        "input string AgentId"
        not in agent_source
    )

    authentication_function = (
        extract_function(
            agent_source,
            start_marker=(
                "string BuildAuthenticationHeaders("
            ),
            end_marker=(
                "string UtcNowIso8601()"
            ),
        )
    )

    assert re.search(
        r"\+\s*TODOBA_AGENT_ID\b",
        authentication_function,
    )

    poll_cloud = extract_function(
        agent_source,
        start_marker="void PollCloud()",
        end_marker="void PollControlCloud()",
    )

    assert re.search(
        (
            r"TODOBAExecutionMissionValidator"
            r"::Validate\(\s*"
            r"mission\s*,\s*"
            r"TODOBA_AGENT_ID\s*"
            r"\)"
        ),
        poll_cloud,
    )

    assert (
        "AgentId"
        not in authentication_function
    )

    assert not re.search(
        r"\bAgentId\b",
        poll_cloud,
    )


def test_provisioned_agent_rejects_wrong_mt5_account_before_timer_start(
    tmp_path: Path,
) -> None:
    deployment_root = provision_runtime(
        tmp_path
    )

    agent_source = read_provisioned_agent(
        deployment_root
    )

    credentials = (
        read_provisioned_credentials(
            deployment_root
        )
    )

    assert (
        "const string "
        "TODOBA_EXPECTED_ACCOUNT_FINGERPRINT = "
        f'"{ACCOUNT_FINGERPRINT}";'
        in credentials
    )

    on_init = extract_function(
        agent_source,
        start_marker="int OnInit()",
        end_marker="void OnDeinit(",
    )

    normalized = compact(
        on_init
    )

    actual_account_index = (
        normalized.index(
            "TODOBAAccountFingerprint::Build()"
        )
    )

    expected_account_index = (
        normalized.index(
            "TODOBA_EXPECTED_ACCOUNT_FINGERPRINT"
        )
    )

    account_mismatch_index = (
        normalized.index(
            "!=TODOBA_EXPECTED_ACCOUNT_FINGERPRINT"
        )
    )

    fail_closed_index = (
        normalized.index(
            "returnINIT_FAILED;",
            account_mismatch_index,
        )
    )

    timer_start_index = (
        normalized.index(
            "EventSetTimer("
        )
    )

    assert (
        actual_account_index
        < timer_start_index
    )

    assert (
        expected_account_index
        < timer_start_index
    )

    assert (
        account_mismatch_index
        < fail_closed_index
        < timer_start_index
    )
