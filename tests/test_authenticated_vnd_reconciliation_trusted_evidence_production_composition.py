import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")


def _main_source() -> str:
    return MAIN_PATH.read_text(
        encoding="utf-8-sig"
    )


def _main_tree():
    source = _main_source()

    return (
        source,
        ast.parse(
            source,
            filename=str(MAIN_PATH),
        ),
    )


def _function(name: str):
    source, tree = _main_tree()

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


def test_main_imports_p8d2_trusted_evidence_owners():
    source = _main_source()

    assert (
        "CustomerVndBankEvidencePublicationService"
        in source
    )

    assert (
        "CustomerVndBankReconciliationEvidenceOrchestrationService"
        in source
    )


def test_authenticated_vnd_ingress_composes_publication_and_orchestration():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    assert (
        "CustomerVndBankEvidencePublicationService("
        in ingress_source
    )

    assert (
        "CustomerVndBankReconciliationEvidenceOrchestrationService("
        in ingress_source
    )


def test_evidence_publication_uses_server_owned_payment_services():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    required = (
        "customer_vnd_bank_reconciliation_store",
        "customer_payment_evidence_service",
        "customer_payment_intent_service",
        "customer_commercial_order_service",
    )

    for token in required:
        assert token in ingress_source


def test_orchestrator_wraps_reconciliation_and_publication_owners():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    assert (
        "reconciliation_service="
        in ingress_source
    )

    assert (
        "evidence_publication_service="
        in ingress_source
    )


def test_admin_router_receives_transaction_reference_resolver():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    marker = (
        "create_customer_vnd_bank_reconciliation_admin_router("
    )

    assert marker in ingress_source

    router_offset = ingress_source.index(
        marker
    )

    tail = ingress_source[
        router_offset:
    ]

    assert (
        "transaction_reference_resolver="
        in tail
    )

    assert (
        "bank_transaction_reference_resolver"
        in tail
    )


def test_p8d3_creates_no_payment_stores():
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
        "CustomerVndBankReconciliationStore(",
        "initialize_empty(",
    )

    for token in forbidden:
        assert token not in ingress_source


def test_p8d3_composition_has_no_assertion_settlement_or_activation_authority():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    forbidden = (
        "build_assertion(",
        "settle(",
        "activate(",
        "activate_from_settlement(",
        "complete_verified_payment(",
        "mark_paid(",
    )

    for token in forbidden:
        assert token not in ingress_source


def test_payment_runtime_remains_free_of_authenticated_vnd_ingress_authority():
    source, node = _function(
        "_compose_customer_payment_runtime"
    )

    payment_source = ast.get_source_segment(
        source,
        node,
    )

    forbidden = (
        "CustomerVndBankEvidencePublicationService",
        "CustomerVndBankReconciliationEvidenceOrchestrationService",
        "create_customer_vnd_bank_reconciliation_admin_router",
        "include_router(",
    )

    for token in forbidden:
        assert token not in payment_source



def test_transaction_reference_resolver_wraps_trusted_evidence_orchestrator():
    source, node = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    ingress_source = ast.get_source_segment(
        source,
        node,
    )

    assert ingress_source is not None

    marker = "CustomerBankTransactionReferenceResolver("

    assert marker in ingress_source

    resolver_offset = ingress_source.index(
        marker
    )

    tail = ingress_source[
        resolver_offset:
    ]

    assert (
        "payment_intent_store="
        in tail
    )

    assert (
        "customer_payment_intent_store"
        in tail
    )

    assert (
        "reconciliation_service="
        in tail
    )

    assert (
        "reconciliation_orchestration_service"
        in tail
    )
