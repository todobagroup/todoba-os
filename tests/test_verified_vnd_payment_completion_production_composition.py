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
