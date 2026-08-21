"""
TODOBA Trusted Agent Secure Deployment Provisioning Tests

CAP 3H proof:

A Trusted Agent deployment must be generated as an isolated,
agent-specific build workspace.

Required properties:

- deployment identity is explicit
- Agent/account ownership is embedded in the deployment
- authentication and signing domains are agent-specific
- one deployment cannot inherit another deployment's secrets
- the repository-local credential file is never modified
- an existing deployment cannot be silently overwritten

These tests use proof-only fake credentials.
No production credential values belong in this file.
"""

import importlib
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]

MQL5_SOURCE_ROOT = (
    ROOT_DIR
    / "MQL5"
)

REPOSITORY_CREDENTIAL_PATH = (
    MQL5_SOURCE_ROOT
    / "Include"
    / "TODOBAExecution"
    / "TODOBAAgentCredentials.mqh"
)


AGENT_A = "trusted-agent-001"
AGENT_B = "trusted-agent-002"

ACCOUNT_A = "broker-a:100001"
ACCOUNT_B = "broker-b:200002"

AGENT_SECRET_A = (
    "proof-agent-secret-a"
)
AGENT_SECRET_B = (
    "proof-agent-secret-b"
)

EXECUTION_SECRET_A = (
    "proof-execution-secret-a"
)
EXECUTION_SECRET_B = (
    "proof-execution-secret-b"
)

CONTROL_SECRET_A = (
    "proof-control-secret-a"
)
CONTROL_SECRET_B = (
    "proof-control-secret-b"
)


def load_provisioner():
    module = importlib.import_module(
        "scripts.provision_trusted_agent_deployment"
    )

    return (
        module
        .provision_trusted_agent_deployment
    )


def snapshot_repository_credentials():
    if not REPOSITORY_CREDENTIAL_PATH.exists():
        return None

    return (
        REPOSITORY_CREDENTIAL_PATH
        .read_bytes()
    )


def assert_repository_credentials_unchanged(
    before,
) -> None:
    if before is None:
        assert (
            not REPOSITORY_CREDENTIAL_PATH.exists()
        )

        return

    assert (
        REPOSITORY_CREDENTIAL_PATH.exists()
    )

    assert (
        REPOSITORY_CREDENTIAL_PATH.read_bytes()
        == before
    )


def deployment_directory(
    *,
    output_root: Path,
    agent_id: str,
) -> Path:
    return (
        output_root
        / agent_id
    )


def deployment_credential_path(
    *,
    output_root: Path,
    agent_id: str,
) -> Path:
    return (
        deployment_directory(
            output_root=output_root,
            agent_id=agent_id,
        )
        / "MQL5"
        / "Include"
        / "TODOBAExecution"
        / "TODOBAAgentCredentials.mqh"
    )


def provision(
    *,
    output_root: Path,
    agent_id: str,
    account_fingerprint: str,
    agent_secret: str,
    execution_secret: str,
    control_secret: str,
):
    provisioner = load_provisioner()

    return provisioner(
        mql5_source_root=MQL5_SOURCE_ROOT,
        output_root=output_root,
        agent_id=agent_id,
        account_fingerprint=(
            account_fingerprint
        ),
        agent_secret=agent_secret,
        execution_mission_signing_secret=(
            execution_secret
        ),
        control_mission_signing_secret=(
            control_secret
        ),
    )


def assert_identity_header(
    *,
    content: str,
    agent_id: str,
    account_fingerprint: str,
    agent_secret: str,
    execution_secret: str,
    control_secret: str,
) -> None:
    assert (
        f'const string TODOBA_AGENT_ID = "{agent_id}";'
        in content
    )

    assert (
        "const string "
        "TODOBA_EXPECTED_ACCOUNT_FINGERPRINT = "
        f'"{account_fingerprint}";'
        in content
    )

    assert (
        "const string TODOBA_AGENT_SECRET = "
        f'"{agent_secret}";'
        in content
    )

    assert (
        "const string TODOBA_MISSION_SIGNING_SECRET = "
        f'"{execution_secret}";'
        in content
    )

    assert (
        "const string "
        "TODOBA_CONTROL_MISSION_SIGNING_SECRET = "
        f'"{control_secret}";'
        in content
    )


def test_provisioning_creates_isolated_agent_deployment_without_touching_repository_credentials(
    tmp_path: Path,
) -> None:
    repository_credentials_before = (
        snapshot_repository_credentials()
    )

    output_root = (
        tmp_path
        / "deployments"
    )

    provision(
        output_root=output_root,
        agent_id=AGENT_A,
        account_fingerprint=ACCOUNT_A,
        agent_secret=AGENT_SECRET_A,
        execution_secret=EXECUTION_SECRET_A,
        control_secret=CONTROL_SECRET_A,
    )

    deployment_dir = deployment_directory(
        output_root=output_root,
        agent_id=AGENT_A,
    )

    assert deployment_dir.is_dir()

    generated_credentials = (
        deployment_credential_path(
            output_root=output_root,
            agent_id=AGENT_A,
        )
    )

    assert generated_credentials.is_file()

    content = generated_credentials.read_text(
        encoding="utf-8"
    )

    assert_identity_header(
        content=content,
        agent_id=AGENT_A,
        account_fingerprint=ACCOUNT_A,
        agent_secret=AGENT_SECRET_A,
        execution_secret=EXECUTION_SECRET_A,
        control_secret=CONTROL_SECRET_A,
    )

    assert_repository_credentials_unchanged(
        repository_credentials_before
    )


def test_two_provisioned_agents_have_independent_identity_and_secret_domains(
    tmp_path: Path,
) -> None:
    repository_credentials_before = (
        snapshot_repository_credentials()
    )

    output_root = (
        tmp_path
        / "deployments"
    )

    provision(
        output_root=output_root,
        agent_id=AGENT_A,
        account_fingerprint=ACCOUNT_A,
        agent_secret=AGENT_SECRET_A,
        execution_secret=EXECUTION_SECRET_A,
        control_secret=CONTROL_SECRET_A,
    )

    provision(
        output_root=output_root,
        agent_id=AGENT_B,
        account_fingerprint=ACCOUNT_B,
        agent_secret=AGENT_SECRET_B,
        execution_secret=EXECUTION_SECRET_B,
        control_secret=CONTROL_SECRET_B,
    )

    credential_a = (
        deployment_credential_path(
            output_root=output_root,
            agent_id=AGENT_A,
        )
    )

    credential_b = (
        deployment_credential_path(
            output_root=output_root,
            agent_id=AGENT_B,
        )
    )

    assert credential_a != credential_b

    content_a = credential_a.read_text(
        encoding="utf-8"
    )

    content_b = credential_b.read_text(
        encoding="utf-8"
    )

    assert_identity_header(
        content=content_a,
        agent_id=AGENT_A,
        account_fingerprint=ACCOUNT_A,
        agent_secret=AGENT_SECRET_A,
        execution_secret=EXECUTION_SECRET_A,
        control_secret=CONTROL_SECRET_A,
    )

    assert_identity_header(
        content=content_b,
        agent_id=AGENT_B,
        account_fingerprint=ACCOUNT_B,
        agent_secret=AGENT_SECRET_B,
        execution_secret=EXECUTION_SECRET_B,
        control_secret=CONTROL_SECRET_B,
    )

    assert AGENT_B not in content_a
    assert ACCOUNT_B not in content_a
    assert AGENT_SECRET_B not in content_a
    assert EXECUTION_SECRET_B not in content_a
    assert CONTROL_SECRET_B not in content_a

    assert AGENT_A not in content_b
    assert ACCOUNT_A not in content_b
    assert AGENT_SECRET_A not in content_b
    assert EXECUTION_SECRET_A not in content_b
    assert CONTROL_SECRET_A not in content_b

    assert_repository_credentials_unchanged(
        repository_credentials_before
    )


def test_existing_agent_deployment_is_not_silently_overwritten(
    tmp_path: Path,
) -> None:
    repository_credentials_before = (
        snapshot_repository_credentials()
    )

    output_root = (
        tmp_path
        / "deployments"
    )

    provision(
        output_root=output_root,
        agent_id=AGENT_A,
        account_fingerprint=ACCOUNT_A,
        agent_secret=AGENT_SECRET_A,
        execution_secret=EXECUTION_SECRET_A,
        control_secret=CONTROL_SECRET_A,
    )

    credential_path = (
        deployment_credential_path(
            output_root=output_root,
            agent_id=AGENT_A,
        )
    )

    original_content = (
        credential_path.read_bytes()
    )

    with pytest.raises(
        FileExistsError,
        match="deployment already exists",
    ):
        provision(
            output_root=output_root,
            agent_id=AGENT_A,
            account_fingerprint=ACCOUNT_B,
            agent_secret=AGENT_SECRET_B,
            execution_secret=EXECUTION_SECRET_B,
            control_secret=CONTROL_SECRET_B,
        )

    assert (
        credential_path.read_bytes()
        == original_content
    )

    assert_repository_credentials_unchanged(
        repository_credentials_before
    )


def test_agent_id_path_traversal_is_rejected_before_deployment_creation(
    tmp_path: Path,
) -> None:
    output_root = (
        tmp_path
        / "deployments"
    )

    escaped_deployment = (
        tmp_path
        / "escaped-agent"
    )

    with pytest.raises(
        ValueError,
        match="agent_id",
    ):
        provision(
            output_root=output_root,
            agent_id="../escaped-agent",
            account_fingerprint=ACCOUNT_A,
            agent_secret=AGENT_SECRET_A,
            execution_secret=EXECUTION_SECRET_A,
            control_secret=CONTROL_SECRET_A,
        )

    assert not escaped_deployment.exists()


def test_output_root_inside_repository_is_rejected_before_copying_secrets(
    monkeypatch,
) -> None:
    provisioner = load_provisioner()

    repository_root = (
        MQL5_SOURCE_ROOT.parent
    )

    forbidden_output_root = (
        repository_root
        / "CAP3H_FORBIDDEN_DEPLOYMENT_PROOF"
    )

    assert not forbidden_output_root.exists()

    copytree_called = False

    def forbidden_copytree(
        *args,
        **kwargs,
    ):
        nonlocal copytree_called

        copytree_called = True

        raise AssertionError(
            "copytree must not run for an output root "
            "inside the repository."
        )

    monkeypatch.setattr(
        (
            "scripts.provision_trusted_agent_deployment"
            ".shutil.copytree"
        ),
        forbidden_copytree,
    )

    with pytest.raises(
        ValueError,
        match="output_root",
    ):
        provisioner(
            mql5_source_root=MQL5_SOURCE_ROOT,
            output_root=forbidden_output_root,
            agent_id="trusted-agent-forbidden-output-proof",
            account_fingerprint=ACCOUNT_A,
            agent_secret=AGENT_SECRET_A,
            execution_mission_signing_secret=(
                EXECUTION_SECRET_A
            ),
            control_mission_signing_secret=(
                CONTROL_SECRET_A
            ),
        )

    assert copytree_called is False

    assert not forbidden_output_root.exists()


def test_windows_drive_relative_agent_id_is_rejected_before_copying_material(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provisioner = load_provisioner()

    output_root = (
        tmp_path
        / "deployments"
    )

    copytree_called = False

    def forbidden_copytree(
        *args,
        **kwargs,
    ):
        nonlocal copytree_called

        copytree_called = True

        raise AssertionError(
            "copytree must not run for a Windows "
            "drive-relative agent_id."
        )

    monkeypatch.setattr(
        (
            "scripts.provision_trusted_agent_deployment"
            ".shutil.copytree"
        ),
        forbidden_copytree,
    )

    with pytest.raises(
        ValueError,
        match="agent_id",
    ):
        provisioner(
            mql5_source_root=MQL5_SOURCE_ROOT,
            output_root=output_root,
            agent_id="C:cap3h-drive-relative-proof",
            account_fingerprint=ACCOUNT_A,
            agent_secret=AGENT_SECRET_A,
            execution_mission_signing_secret=(
                EXECUTION_SECRET_A
            ),
            control_mission_signing_secret=(
                CONTROL_SECRET_A
            ),
        )

    assert copytree_called is False
