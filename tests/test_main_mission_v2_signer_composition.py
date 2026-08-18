from backend.main import (
    control_mission_signer,
    control_mission_signer_v2,
    execution_mission_signer,
    execution_mission_signer_v2,
)
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


def test_main_composes_v1_and_v2_mission_signers_side_by_side() -> None:
    assert isinstance(
        execution_mission_signer,
        ExecutionMissionSigner,
    )

    assert isinstance(
        execution_mission_signer_v2,
        ExecutionMissionSignerV2,
    )

    assert isinstance(
        control_mission_signer,
        ControlMissionSigner,
    )

    assert isinstance(
        control_mission_signer_v2,
        ControlMissionSignerV2,
    )

    assert (
        execution_mission_signer
        is not execution_mission_signer_v2
    )

    assert (
        control_mission_signer
        is not control_mission_signer_v2
    )

    assert (
        execution_mission_signer_v2
        is not control_mission_signer_v2
    )