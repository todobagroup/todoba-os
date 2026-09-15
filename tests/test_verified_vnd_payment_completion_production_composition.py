import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")


def _source():
    return MAIN_PATH.read_text(
        encoding="utf-8-sig"
    )


def _tree():
    source = _source()

    return (
        source,
        ast.parse(
            source,
            filename=str(MAIN_PATH),
        ),
    )


def _function(name: str):
    source, tree = _tree()

    for node in tree.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        ):
            return (
                source,
                node,
            )

    raise AssertionError(
        f"Missing function: {name}"
    )


def test_main_imports_verified_vnd_completion_owners():
    source = _source()

    assert (
        "CustomerVndBankReconciliationVerificationAdapter"
        in source
    )

    assert (
        "CustomerVndBankPaymentCompletionOrchestrationService"
        in source
    )


def test_authenticated_vnd_ingress_composes_verification_adapter():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    assert (
        "CustomerVndBankReconciliationVerificationAdapter("
        in ingress_source
    )


def test_verification_adapter_uses_server_owned_payment_state():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    required = (
        "customer_vnd_bank_reconciliation_store",
        "customer_payment_evidence_store",
        "customer_payment_intent_store",
        "customer_commercial_order_store",
    )

    for token in required:
        assert token in ingress_source


def test_authenticated_vnd_ingress_composes_payment_completion_orchestrator():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    assert (
        "CustomerVndBankPaymentCompletionOrchestrationService("
        in ingress_source
    )

    assert (
        "verification_adapter="
        in ingress_source
    )

    assert (
        "settlement_orchestration_service="
        in ingress_source
    )


def test_completion_orchestrator_uses_existing_settlement_orchestration():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    assert (
        "customer_payment_settlement_orchestration_service"
        in ingress_source
    )


def test_p8e2_creates_no_payment_stores():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    forbidden = (
        "CustomerCommercialOrderStore(",
        "CustomerPaymentIntentStore(",
        "CustomerPaymentEvidenceStore(",
        "CustomerPaymentSettlementStore(",
        "CustomerVndBankReconciliationStore(",
        "initialize_empty(",
    )

    for token in forbidden:
        assert token not in ingress_source


def test_p8e2_composition_has_no_direct_settlement_or_activation_authority():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    forbidden = (
        ".settle(",
        ".activate(",
        "activate_from_settlement(",
        "complete_verified_payment(",
        "build_assertion(",
        "mark_paid(",
    )

    for token in forbidden:
        assert token not in ingress_source


def test_payment_runtime_remains_free_of_verified_vnd_ingress_authority():
    source, node = _function(
        "_compose_customer_payment_runtime"
    )

    payment_source = ast.get_source_segment(
        source,
        node,
    )

    forbidden = (
        "CustomerVndBankReconciliationVerificationAdapter",
        "CustomerVndBankPaymentCompletionOrchestrationService",
        "create_customer_vnd_bank_reconciliation_admin_router",
        "include_router(",
    )

    for token in forbidden:
        assert token not in payment_source


def test_production_setup_payment_and_authenticated_vnd_ingress_compose_at_runtime(
    monkeypatch,
    tmp_path,
):

    monkeypatch.setenv(
        "TODOBA_VND_BANK_CODE",
        "TESTBANK",
    )
    monkeypatch.setenv(
        "TODOBA_VND_BANK_ACCOUNT_NUMBER",
        "0123456789",
    )
    monkeypatch.setenv(
        "TODOBA_VND_BANK_ACCOUNT_NAME",
        "TODOBA TEST",
    )

    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI

    import backend.main as production

    from backend.commercial.customer_identity_registry import (
        CustomerIdentityRegistry,
    )

    production_root = (
        production.TODOBA_CONTROL_PLANE_DATA_ROOT
    )

    # Redirect every production-owned Path under the real control-plane
    # root into this test's isolated tmp_path. This keeps the actual
    # production durable state completely untouched while exercising
    # the real composition functions.
    redirected = 0

    for name, value in tuple(
        vars(production).items()
    ):
        if not isinstance(value, Path):
            continue

        try:
            relative = value.relative_to(
                production_root
            )
        except ValueError:
            continue

        monkeypatch.setattr(
            production,
            name,
            tmp_path / relative,
        )

        redirected += 1

    assert redirected > 0

    monkeypatch.setattr(
        production,
        "TODOBA_CONTROL_PLANE_DATA_ROOT",
        tmp_path,
    )

    # Official provisioner requires the identity registry to exist
    # before provisioning the rest of the control plane.
    identity_path = (
        production.CUSTOMER_IDENTITY_STORAGE_PATH
    )

    identity_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    identity_registry = CustomerIdentityRegistry(
        identity_path
    )

    identity_registry.initialize_empty()

    provisioner_path = (
        Path(__file__).parents[1]
        / "scripts"
        / "provision_customer_setup_control_plane.py"
    )

    spec = importlib.util.spec_from_file_location(
        "p8e2_runtime_control_plane_provisioner",
        provisioner_path,
    )

    assert spec is not None
    assert spec.loader is not None

    provisioner_module = (
        importlib.util.module_from_spec(spec)
    )

    spec.loader.exec_module(
        provisioner_module
    )

    provisioner_module.provision_customer_setup_control_plane(
        control_plane_root=tmp_path,
        confirm_runtime_stopped=True,
    )

    monkeypatch.setenv(
        "TODOBA_COMMERCIAL_OPERATOR_ID",
        "p8e2-runtime-regression-operator",
    )

    monkeypatch.setenv(
        "TODOBA_COMMERCIAL_OPERATOR_SECRET",
        (
            "p8e2-runtime-regression-secret-"
            "0123456789abcdef"
        ),
    )

    # Isolate composition guards from wider suite ordering.
    monkeypatch.setattr(
        production,
        "_customer_setup_runtime_composed",
        False,
    )

    monkeypatch.setattr(
        production,
        "_customer_payment_runtime_composed",
        False,
    )

    monkeypatch.setattr(
        production,
        "_authenticated_vnd_reconciliation_ingress_composed",
        False,
    )

    app = FastAPI()

    production._compose_customer_setup_runtime(
        app
    )

    production._compose_customer_payment_runtime(
        app
    )

    production._compose_authenticated_vnd_reconciliation_ingress(
        app
    )

    openapi_paths = app.openapi()["paths"]

    assert (
        "/internal/commercial/vnd-bank/reconciliations"
        in openapi_paths
    )

    assert (
        "post"
        in openapi_paths[
            "/internal/commercial/vnd-bank/reconciliations"
        ]
    )

    assert (
        production
        ._authenticated_vnd_reconciliation_ingress_composed
        is True
    )
