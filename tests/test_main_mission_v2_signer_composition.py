from backend import main
from backend.trading.control.control_mission_signer import (
    ControlMissionSigner,
)
from backend.trading.control.control_mission_signer_v2 import (
    ControlMissionSignerV2,
)
from backend.trading.execution.execution_mission_signer import (
    ExecutionMissionSigner,
)
from backend.trading.execution.execution_mission_signer_v2 import (
    ExecutionMissionSignerV2,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


def test_main_composes_v1_and_v2_mission_signers_side_by_side() -> None:
    assert isinstance(
        main.execution_mission_signer,
        ExecutionMissionSigner,
    )

    assert isinstance(
        main.execution_mission_signer_v2,
        ExecutionMissionSignerV2,
    )

    assert isinstance(
        main.control_mission_signer,
        ControlMissionSigner,
    )

    assert isinstance(
        main.control_mission_signer_v2,
        ControlMissionSignerV2,
    )

    assert (
        main.execution_mission_signer
        is not main.execution_mission_signer_v2
    )

    assert (
        main.control_mission_signer
        is not main.control_mission_signer_v2
    )

    assert (
        main.execution_mission_signer_v2
        is not main.control_mission_signer_v2
    )


def test_main_composes_separate_signing_key_domains() -> None:
    assert isinstance(
        main.execution_signing_key_registry,
        TrustedAgentSigningKeyRegistry,
    )

    assert isinstance(
        main.control_signing_key_registry,
        TrustedAgentSigningKeyRegistry,
    )

    assert (
        main.execution_signing_key_registry
        is not main.control_signing_key_registry
    )

    deployments = (
        main.customer_deployment_registry.all()
    )

    assert deployments

    for deployment in deployments:
        secrets = (
            main.customer_deployment_secret_store.get(
                deployment_id=(
                    deployment.deployment_id
                )
            )
        )

        assert secrets is not None

        assert (
            main.execution_signing_key_registry.get_secret(
                agent_id=deployment.agent_id
            )
            == (
                secrets
                .execution_mission_signing_secret
            )
        )

        assert (
            main.control_signing_key_registry.get_secret(
                agent_id=deployment.agent_id
            )
            == (
                secrets
                .control_mission_signing_secret
            )
        )


def test_main_signers_use_their_own_signing_domain() -> None:
    assert (
        main.execution_mission_signer._signing_key_registry
        is main.execution_signing_key_registry
    )

    assert (
        main.execution_mission_signer_v2._signing_key_registry
        is main.execution_signing_key_registry
    )

    assert (
        main.control_mission_signer._signing_key_registry
        is main.control_signing_key_registry
    )

    assert (
        main.control_mission_signer_v2._signing_key_registry
        is main.control_signing_key_registry
    )