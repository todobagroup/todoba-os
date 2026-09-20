from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

OWNER_PATH = (
    ROOT
    / "backend"
    / "commercial"
    / "customer_commercial_pending_exposure_containment_service.py"
)

MAIN_PATH = ROOT / "backend" / "main.py"


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )


def test_pending_exposure_containment_owner_exists():
    assert OWNER_PATH.is_file()


def test_containment_owner_uses_existing_control_mission_authority():
    source = _source(OWNER_PATH)

    assert "ControlMissionService" in source
    assert "ControlMission" in source
    assert "ControlAction.CANCEL_ALL_PENDING" in source
    assert ".create_mission(" in source

    # P9F2B does not gain direct MT5 authority.
    for forbidden in (
        "order_send",
        "TRADE_ACTION_REMOVE",
        "MetaTrader5",
        "mt5.",
    ):
        assert forbidden not in source


def test_containment_identity_comes_from_commercial_deployment_binding():
    source = _source(OWNER_PATH)

    assert "deployment_binding_store" in source
    assert "get_by_deployment_id" in source
    assert "binding.agent_id" in source
    assert "binding.account_fingerprint" in source

    assert "binding.agent_id" in source
    assert "binding.account_fingerprint" in source

    # No caller-supplied commercial identity.
    tree = ast.parse(
        source,
        filename=str(OWNER_PATH),
    )

    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name
        == "CustomerCommercialPendingExposureContainmentService"
    )

    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "issue"
    )

    parameters = {
        arg.arg
        for arg in (
            list(method.args.args)
            + list(method.args.kwonlyargs)
        )
    }

    assert "trigger_id" in parameters
    assert "deployment_id" in parameters

    assert "agent_id" not in parameters
    assert "account_fingerprint" not in parameters
    assert "commercial_entitlement_id" not in parameters
    assert "cycle_id" not in parameters
    assert "symbol" not in parameters
    assert "magic_number" not in parameters
    assert "requested_by_sender_id" not in parameters
    assert "sequence" not in parameters
    assert "customer_id" not in parameters


def test_containment_requires_upgrade_required_decision():
    source = _source(OWNER_PATH)

    assert "CustomerCommercialCapacityDecision" in source
    assert "UPGRADE_REQUIRED" in source
    assert "decision.status" in source
    assert "!=" in source


def test_main_composes_containment_with_existing_control_mission_service():
    source = _source(MAIN_PATH)

    assert (
        "CustomerCommercialPendingExposureContainmentService"
        in source
    )

    assert (
        "control_mission_service=control_mission_service"
        in source
    )


def test_containment_does_not_mutate_pending_repository_as_cancel_proof():
    source = _source(OWNER_PATH)

    for forbidden in (
        "PendingOrderRepository",
        "pending_order_repository",
        ".remove(",
        ".delete(",
    ):
        assert forbidden not in source
