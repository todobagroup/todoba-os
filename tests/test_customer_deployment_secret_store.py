import base64
import json

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
    CustomerDeploymentSecretStore,
)


def build_secrets(
    *,
    deployment_id: str = "deployment-001",
    agent_secret: str = "agent-secret-001",
    execution_secret: str = "execution-secret-001",
    control_secret: str = "control-secret-001",
) -> CustomerDeploymentSecrets:
    return CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret=agent_secret,
        execution_mission_signing_secret=(
            execution_secret
        ),
        control_mission_signing_secret=(
            control_secret
        ),
    )


def build_master_key() -> bytes:
    return AESGCM.generate_key(
        bit_length=256
    )


def test_store_requires_explicit_initialization(
    tmp_path,
) -> None:
    store = CustomerDeploymentSecretStore(
        tmp_path / "customer_deployment_secrets.json",
        master_key=build_master_key(),
    )

    assert not store.is_ready()

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.size()


def test_initialize_empty_creates_durable_store(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=build_master_key(),
    )

    store.initialize_empty()

    assert store.is_ready()
    assert store.size() == 0
    assert storage_path.is_file()

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload == {
        "version": 1,
        "deployments": [],
    }


def test_register_persists_ciphertext_and_restores(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    master_key = build_master_key()

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=master_key,
    )
    store.initialize_empty()

    secrets = build_secrets()

    store.register(
        secrets
    )

    raw_storage = storage_path.read_text(
        encoding="utf-8"
    )

    assert "agent-secret-001" not in raw_storage
    assert "execution-secret-001" not in raw_storage
    assert "control-secret-001" not in raw_storage

    payload = json.loads(
        raw_storage
    )

    assert payload["version"] == 1
    assert len(
        payload["deployments"]
    ) == 1

    record = payload[
        "deployments"
    ][0]

    assert set(
        record.keys()
    ) == {
        "deployment_id",
        "nonce",
        "ciphertext",
    }

    assert record[
        "deployment_id"
    ] == "deployment-001"

    restored = CustomerDeploymentSecretStore(
        storage_path,
        master_key=master_key,
    )

    restored_secrets = restored.get(
        deployment_id="deployment-001"
    )

    assert restored_secrets is not None

    assert restored_secrets.same_secret_material(
        secrets
    )


def test_wrong_master_key_is_rejected(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=build_master_key(),
    )
    store.initialize_empty()

    store.register(
        build_secrets()
    )

    with pytest.raises(
        ValueError,
        match="authentication failed",
    ):
        CustomerDeploymentSecretStore(
            storage_path,
            master_key=build_master_key(),
        )


def test_ciphertext_tampering_is_rejected(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    master_key = build_master_key()

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=master_key,
    )
    store.initialize_empty()

    store.register(
        build_secrets()
    )

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    record = payload[
        "deployments"
    ][0]

    ciphertext = bytearray(
        base64.b64decode(
            record[
                "ciphertext"
            ],
            validate=True,
        )
    )

    ciphertext[
        0
    ] ^= 1

    record[
        "ciphertext"
    ] = base64.b64encode(
        bytes(
            ciphertext
        )
    ).decode(
        "ascii"
    )

    storage_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="authentication failed",
    ):
        CustomerDeploymentSecretStore(
            storage_path,
            master_key=master_key,
        )


def test_identical_registration_is_idempotent(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=build_master_key(),
    )
    store.initialize_empty()

    secrets = build_secrets()

    first = store.register(
        secrets
    )

    durable_before = (
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    second = store.register(
        secrets
    )

    durable_after = (
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert first.same_secret_material(
        secrets
    )

    assert second.same_secret_material(
        secrets
    )

    assert store.size() == 1
    assert durable_after == durable_before


def test_conflicting_secret_replacement_is_rejected(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=build_master_key(),
    )
    store.initialize_empty()

    original = build_secrets()

    store.register(
        original
    )

    durable_before = (
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    conflicting = build_secrets(
        agent_secret="different-agent-secret",
    )

    with pytest.raises(
        ValueError,
        match="different secret material",
    ):
        store.register(
            conflicting
        )

    assert store.size() == 1

    assert (
        storage_path.read_text(
            encoding="utf-8"
        )
        == durable_before
    )

    restored = store.get(
        deployment_id="deployment-001"
    )

    assert restored is not None

    assert restored.same_secret_material(
        original
    )


def test_secret_repr_is_redacted(
    tmp_path,
) -> None:
    secrets = build_secrets()

    representation = repr(
        secrets
    )

    assert "deployment-001" in representation

    assert "agent-secret-001" not in representation

    assert (
        "execution-secret-001"
        not in representation
    )

    assert (
        "control-secret-001"
        not in representation
    )

    assert "<redacted>" in representation


def test_register_write_failure_does_not_advance_memory(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=build_master_key(),
    )
    store.initialize_empty()

    durable_before = (
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    secrets = build_secrets()

    def fail_write(
        secrets_by_deployment,
    ) -> None:
        raise OSError(
            "simulated encrypted store write failure"
        )

    monkeypatch.setattr(
        store,
        "_write_secrets",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated encrypted store write failure",
    ):
        store.register(
            secrets
        )

    assert store.size() == 0

    assert store.get(
        deployment_id="deployment-001"
    ) is None

    assert (
        storage_path.read_text(
            encoding="utf-8"
        )
        == durable_before
    )

def test_secret_material_is_preserved_exactly(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployment_secrets.json"
    )

    master_key = build_master_key()

    store = CustomerDeploymentSecretStore(
        storage_path,
        master_key=master_key,
    )
    store.initialize_empty()

    secrets = build_secrets(
        agent_secret="  agent-??-001  ",
        execution_secret=(
            "\texecution-???-secret\n"
        ),
        control_secret=(
            " control-??-secret "
        ),
    )

    store.register(
        secrets
    )

    raw_storage = storage_path.read_text(
        encoding="utf-8"
    )

    assert secrets.agent_secret not in raw_storage

    assert (
        secrets.execution_mission_signing_secret
        not in raw_storage
    )

    assert (
        secrets.control_mission_signing_secret
        not in raw_storage
    )

    restored_store = (
        CustomerDeploymentSecretStore(
            storage_path,
            master_key=master_key,
        )
    )

    restored = restored_store.get(
        deployment_id="deployment-001"
    )

    assert restored is not None

    assert (
        restored.agent_secret
        == "  agent-??-001  "
    )

    assert (
        restored.execution_mission_signing_secret
        == "\texecution-???-secret\n"
    )

    assert (
        restored.control_mission_signing_secret
        == " control-??-secret "
    )

    assert restored.same_secret_material(
        secrets
    )
