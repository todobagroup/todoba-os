from pathlib import Path
import ast


_MAIN = Path(
    "backend/main.py"
)

_SOURCE = _MAIN.read_text(
    encoding="utf-8-sig"
)

_TREE = ast.parse(
    _SOURCE
)


def _function(name):
    for node in _TREE.body:
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
            return node

    raise AssertionError(
        f"Missing function: {name}"
    )


def _segment(node):
    result = ast.get_source_segment(
        _SOURCE,
        node,
    )

    assert result is not None
    return result


def test_main_imports_paypal_verified_capture_production_owners():
    required = (
        "get_paypal_runtime_config",
        "CustomerPayPalWebhookVerificationClient",
        "CustomerPayPalCaptureHttpClient",
        "CustomerPayPalCaptureVerificationAdapter",
        "CustomerPayPalVerifiedCaptureIngressService",
        "create_customer_paypal_verified_capture_ingress_router",
    )

    for symbol in required:
        assert symbol in _SOURCE


def test_main_has_dedicated_paypal_verified_capture_composer():
    node = _function(
        "_compose_customer_paypal_verified_capture_ingress"
    )

    source = _segment(
        node
    )

    required = (
        "get_paypal_runtime_config",
        "CustomerPayPalWebhookVerificationClient",
        "CustomerPayPalCaptureHttpClient",
        "CustomerPayPalCaptureVerificationAdapter",
        "CustomerPayPalVerifiedCaptureIngressService",
        "create_customer_paypal_verified_capture_ingress_router",
        "customer_paypal_order_binding_store",
        "customer_payment_evidence_store",
        "customer_payment_intent_store",
        "customer_commercial_order_store",
        "customer_payment_settlement_orchestration_service",
        "app.include_router",
    )

    for symbol in required:
        assert symbol in source


def test_paypal_composer_reuses_generic_payment_services():
    node = _function(
        "_compose_customer_paypal_verified_capture_ingress"
    )

    source = _segment(
        node
    )

    assert "CustomerPaymentIntentService(" in source
    assert "CustomerPaymentEvidenceService(" in source

    assert (
        "payment_intent_store="
        in source
    )

    assert (
        "payment_evidence_store="
        in source
    )


def test_paypal_composer_does_not_initialize_or_mutate_payment_stores():
    node = _function(
        "_compose_customer_paypal_verified_capture_ingress"
    )

    source = _segment(
        node
    )

    forbidden = (
        ".initialize_empty(",
        ".open_or_initialize(",
        ".open_existing(",
        "CustomerPaymentSettlementService(",
        "CustomerPaymentSettlementStore(",
    )

    for token in forbidden:
        assert token not in source


def test_paypal_composer_has_no_literal_credentials():
    node = _function(
        "_compose_customer_paypal_verified_capture_ingress"
    )

    source = _segment(
        node
    ).lower()

    forbidden = (
        "paypal-client-secret",
        "client_secret=" + '"',
        "webhook_id=" + '"',
    )

    for token in forbidden:
        assert token not in source


def test_lifespan_composes_paypal_after_payment_runtime():
    lifespan = _function(
        "lifespan"
    )

    source = _segment(
        lifespan
    )

    payment_index = source.index(
        "_compose_customer_payment_runtime"
    )

    paypal_index = source.index(
        "_compose_customer_paypal_verified_capture_ingress"
    )

    assert paypal_index > payment_index


def test_paypal_composition_is_inside_payment_startup_isolation():
    lifespan = _function(
        "lifespan"
    )

    source = _segment(
        lifespan
    )

    paypal_index = source.index(
        "_compose_customer_paypal_verified_capture_ingress"
    )

    except_index = source.index(
        "except RuntimeError as payment_startup_error"
    )

    assert paypal_index < except_index
