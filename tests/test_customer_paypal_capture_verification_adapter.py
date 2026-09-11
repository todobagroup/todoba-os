from __future__ import annotations

from dataclasses import replace

import pytest

import backend.commercial.customer_paypal_capture_verification_adapter as module

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderRecord,
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceRecord,
    CustomerPaymentEvidenceStatus,
    CustomerPaymentEvidenceStore,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentRecord,
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)
from backend.commercial.customer_paypal_capture_http_client import (
    PayPalCaptureDetails,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingRecord,
    CustomerPayPalOrderBindingStatus,
    CustomerPayPalOrderBindingStore,
)
from backend.commercial.customer_paypal_webhook_verification_client import (
    PayPalWebhookVerificationResult,
)

from backend.commercial.customer_paypal_capture_verification_adapter import (
    CustomerPayPalCaptureVerificationAdapter,
)


ORDER_ID = "commercial-order-001"
CUSTOMER_ID = "customer-001"
INTENT_ID = "payment-intent-001"
EVIDENCE_ID = "payment-evidence-001"

PAYPAL_BINDING_ID = "paypal-binding-001"
PAYPAL_ORDER_ID = "5O190127TN364715T"
CAPTURE_ID = "8MC585209K746392H"
WEBHOOK_EVENT_ID = "WH-123456789"

AMOUNT_MINOR = 1999
CURRENCY = "USD"


def _stores(
    tmp_path,
):
    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    evidence_store = CustomerPaymentEvidenceStore(
        tmp_path / "evidence.json"
    )
    evidence_store.initialize_empty()

    binding_store = CustomerPayPalOrderBindingStore(
        tmp_path / "paypal_bindings.json"
    )
    binding_store.initialize_empty()

    return (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    )


def _register_exact_chain(
    *,
    order_store,
    intent_store,
    evidence_store,
    binding_store,
):
    order = CustomerCommercialOrderRecord(
        order_request_id="order-request-001",
        order_id=ORDER_ID,
        customer_id=CUSTOMER_ID,
        amount_minor=AMOUNT_MINOR,
        currency=CURRENCY,
        status=CustomerCommercialOrderStatus.PENDING,
    )
    order_store.register(order)

    intent = CustomerPaymentIntentRecord(
        payment_intent_request_id="intent-request-001",
        payment_intent_id=INTENT_ID,
        order_id=ORDER_ID,
        payment_rail=PaymentRail.PAYPAL,
        status=CustomerPaymentIntentStatus.PENDING,
    )
    intent_store.register(intent)

    evidence = CustomerPaymentEvidenceRecord(
        evidence_request_id="evidence-request-001",
        payment_evidence_id=EVIDENCE_ID,
        payment_intent_id=INTENT_ID,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id=CAPTURE_ID,
        status=CustomerPaymentEvidenceStatus.RECEIVED,
    )
    evidence_store.register(evidence)

    binding = CustomerPayPalOrderBindingRecord(
        paypal_binding_id=PAYPAL_BINDING_ID,
        paypal_order_id=PAYPAL_ORDER_ID,
        paypal_request_id=INTENT_ID,
        payment_intent_id=INTENT_ID,
        order_id=ORDER_ID,
        amount_minor=AMOUNT_MINOR,
        currency=CURRENCY,
        status=CustomerPayPalOrderBindingStatus.BOUND,
    )
    binding_store.register(binding)

    return (
        order,
        intent,
        evidence,
        binding,
    )


def _adapter(
    tmp_path,
):
    (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    ) = _stores(tmp_path)

    (
        order,
        intent,
        evidence,
        binding,
    ) = _register_exact_chain(
        order_store=order_store,
        intent_store=intent_store,
        evidence_store=evidence_store,
        binding_store=binding_store,
    )

    adapter = CustomerPayPalCaptureVerificationAdapter(
        paypal_binding_store=binding_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    return (
        adapter,
        order_store,
        intent_store,
        evidence_store,
        binding_store,
        order,
        intent,
        evidence,
        binding,
    )


def _webhook():
    return PayPalWebhookVerificationResult(
        webhook_event_id=WEBHOOK_EVENT_ID,
        event_type="PAYMENT.CAPTURE.COMPLETED",
        verification_status="SUCCESS",
    )


def _capture(
    **changes,
):
    values = {
        "capture_id": CAPTURE_ID,
        "order_id": PAYPAL_ORDER_ID,
        "custom_id": INTENT_ID,
        "amount_minor": AMOUNT_MINOR,
        "currency": CURRENCY,
        "status": "COMPLETED",
    }
    values.update(changes)

    return PayPalCaptureDetails(
        **values
    )


def test_exact_paypal_chain_builds_payment_verification_assertion(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        _,
        _,
        _,
        _,
        evidence,
        _,
    ) = _adapter(tmp_path)

    result = adapter.build_assertion(
        webhook_verification=_webhook(),
        capture=_capture(),
    )

    assert isinstance(
        result,
        PaymentVerificationAssertion,
    )

    assert result.verification_assertion_id == (
        f"paypal-verification-{CAPTURE_ID}"
    )
    assert result.payment_evidence_id == (
        evidence.payment_evidence_id
    )
    assert result.payment_intent_id == INTENT_ID
    assert result.order_id == ORDER_ID
    assert result.customer_id == CUSTOMER_ID
    assert result.amount_minor == AMOUNT_MINOR
    assert result.currency == CURRENCY
    assert (
        result.evidence_source
        is PaymentEvidenceSource.PAYPAL
    )
    assert result.external_evidence_id == CAPTURE_ID


def test_identical_provider_truth_builds_deterministic_assertion(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    first = adapter.build_assertion(
        webhook_verification=_webhook(),
        capture=_capture(),
    )

    second = adapter.build_assertion(
        webhook_verification=_webhook(),
        capture=_capture(),
    )

    assert second == first


def test_only_capture_completed_webhook_event_is_accepted(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    webhook = PayPalWebhookVerificationResult(
        webhook_event_id=WEBHOOK_EVENT_ID,
        event_type="CHECKOUT.ORDER.APPROVED",
        verification_status="SUCCESS",
    )

    with pytest.raises(
        ValueError,
        match="webhook",
    ):
        adapter.build_assertion(
            webhook_verification=webhook,
            capture=_capture(),
        )


def test_missing_paypal_order_binding_fails_closed(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        _,
        binding_store,
        *_,
    ) = _adapter(tmp_path)

    other_capture = _capture(
        order_id="UNBOUND-PAYPAL-ORDER",
    )

    with pytest.raises(
        ValueError,
        match="binding",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=other_capture,
        )


def test_capture_custom_id_must_equal_bound_payment_intent(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    with pytest.raises(
        ValueError,
        match="intent",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(
                custom_id="payment-intent-attacker",
            ),
        )


@pytest.mark.parametrize(
    "changes",
    (
        {
            "amount_minor": 2000,
        },
        {
            "currency": "EUR",
        },
    ),
)
def test_capture_amount_and_currency_must_match_binding(
    tmp_path,
    changes,
):
    adapter, *_ = _adapter(tmp_path)

    with pytest.raises(
        ValueError,
        match="capture",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(
                **changes
            ),
        )


def test_missing_paypal_evidence_fails_closed(
    tmp_path,
):
    (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    ) = _stores(tmp_path)

    order = CustomerCommercialOrderRecord(
        order_request_id="order-request-001",
        order_id=ORDER_ID,
        customer_id=CUSTOMER_ID,
        amount_minor=AMOUNT_MINOR,
        currency=CURRENCY,
        status=CustomerCommercialOrderStatus.PENDING,
    )
    order_store.register(order)

    intent = CustomerPaymentIntentRecord(
        payment_intent_request_id="intent-request-001",
        payment_intent_id=INTENT_ID,
        order_id=ORDER_ID,
        payment_rail=PaymentRail.PAYPAL,
        status=CustomerPaymentIntentStatus.PENDING,
    )
    intent_store.register(intent)

    binding_store.register(
        CustomerPayPalOrderBindingRecord(
            paypal_binding_id=PAYPAL_BINDING_ID,
            paypal_order_id=PAYPAL_ORDER_ID,
            paypal_request_id=INTENT_ID,
            payment_intent_id=INTENT_ID,
            order_id=ORDER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPayPalOrderBindingStatus.BOUND,
        )
    )

    adapter = CustomerPayPalCaptureVerificationAdapter(
        paypal_binding_store=binding_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    with pytest.raises(
        ValueError,
        match="evidence",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_evidence_must_belong_to_bound_intent(
    tmp_path,
):
    (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    ) = _stores(tmp_path)

    order_store.register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    intent_store.register(
        CustomerPaymentIntentRecord(
            payment_intent_request_id="intent-request-001",
            payment_intent_id=INTENT_ID,
            order_id=ORDER_ID,
            payment_rail=PaymentRail.PAYPAL,
            status=CustomerPaymentIntentStatus.PENDING,
        )
    )

    evidence_store.register(
        CustomerPaymentEvidenceRecord(
            evidence_request_id="evidence-request-001",
            payment_evidence_id=EVIDENCE_ID,
            payment_intent_id="payment-intent-attacker",
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id=CAPTURE_ID,
            status=CustomerPaymentEvidenceStatus.RECEIVED,
        )
    )

    binding_store.register(
        CustomerPayPalOrderBindingRecord(
            paypal_binding_id=PAYPAL_BINDING_ID,
            paypal_order_id=PAYPAL_ORDER_ID,
            paypal_request_id=INTENT_ID,
            payment_intent_id=INTENT_ID,
            order_id=ORDER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPayPalOrderBindingStatus.BOUND,
        )
    )

    adapter = CustomerPayPalCaptureVerificationAdapter(
        paypal_binding_store=binding_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    with pytest.raises(
        ValueError,
        match="evidence",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_missing_authoritative_intent_fails_closed(
    tmp_path,
):
    (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    ) = _stores(tmp_path)

    order_store.register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    evidence_store.register(
        CustomerPaymentEvidenceRecord(
            evidence_request_id="evidence-request-001",
            payment_evidence_id=EVIDENCE_ID,
            payment_intent_id=INTENT_ID,
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id=CAPTURE_ID,
            status=CustomerPaymentEvidenceStatus.RECEIVED,
        )
    )

    binding_store.register(
        CustomerPayPalOrderBindingRecord(
            paypal_binding_id=PAYPAL_BINDING_ID,
            paypal_order_id=PAYPAL_ORDER_ID,
            paypal_request_id=INTENT_ID,
            payment_intent_id=INTENT_ID,
            order_id=ORDER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPayPalOrderBindingStatus.BOUND,
        )
    )

    adapter = CustomerPayPalCaptureVerificationAdapter(
        paypal_binding_store=binding_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    with pytest.raises(
        ValueError,
        match="intent",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_intent_must_use_paypal_rail(
    tmp_path,
):
    (
        adapter,
        _,
        intent_store,
        _,
        _,
        _,
        intent,
        _,
        _,
    ) = _adapter(tmp_path)

    # Authoritative store truth is deliberately replaced
    # only for this isolated negative-path test.
    intent_store._records[INTENT_ID] = replace(
        intent,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    with pytest.raises(
        ValueError,
        match="PayPal",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_missing_authoritative_order_fails_closed(
    tmp_path,
):
    (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    ) = _stores(tmp_path)

    intent_store.register(
        CustomerPaymentIntentRecord(
            payment_intent_request_id="intent-request-001",
            payment_intent_id=INTENT_ID,
            order_id=ORDER_ID,
            payment_rail=PaymentRail.PAYPAL,
            status=CustomerPaymentIntentStatus.PENDING,
        )
    )

    evidence_store.register(
        CustomerPaymentEvidenceRecord(
            evidence_request_id="evidence-request-001",
            payment_evidence_id=EVIDENCE_ID,
            payment_intent_id=INTENT_ID,
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id=CAPTURE_ID,
            status=CustomerPaymentEvidenceStatus.RECEIVED,
        )
    )

    binding_store.register(
        CustomerPayPalOrderBindingRecord(
            paypal_binding_id=PAYPAL_BINDING_ID,
            paypal_order_id=PAYPAL_ORDER_ID,
            paypal_request_id=INTENT_ID,
            payment_intent_id=INTENT_ID,
            order_id=ORDER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPayPalOrderBindingStatus.BOUND,
        )
    )

    adapter = CustomerPayPalCaptureVerificationAdapter(
        paypal_binding_store=binding_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    with pytest.raises(
        ValueError,
        match="order",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


@pytest.mark.parametrize(
    "field,value",
    (
        (
            "amount_minor",
            2000,
        ),
        (
            "currency",
            "EUR",
        ),
        (
            "order_id",
            "commercial-order-attacker",
        ),
    ),
)
def test_binding_must_match_authoritative_commercial_chain(
    tmp_path,
    field,
    value,
):
    (
        adapter,
        _,
        _,
        _,
        binding_store,
        _,
        _,
        _,
        binding,
    ) = _adapter(tmp_path)

    binding_store._records[
        PAYPAL_BINDING_ID
    ] = replace(
        binding,
        **{
            field: value,
        },
    )

    with pytest.raises(
        ValueError,
        match="binding",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_wrong_input_types_are_rejected(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    with pytest.raises(
        TypeError,
        match="webhook",
    ):
        adapter.build_assertion(
            webhook_verification="SUCCESS",
            capture=_capture(),
        )

    with pytest.raises(
        TypeError,
        match="capture",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture={
                "id": CAPTURE_ID,
            },
        )


def test_adapter_has_no_network_settlement_or_activation_authority(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    for name in (
        "get_capture",
        "verify_webhook",
        "receive_evidence",
        "settle",
        "activate_setup",
        "activate_entitlement",
    ):
        assert not hasattr(
            adapter,
            name,
        )

    assert not hasattr(
        module,
        "httpx",
    )

@pytest.mark.parametrize(
    "slot,bad_value,match",
    (
        (
            "paypal_binding_store",
            object(),
            "paypal_binding_store",
        ),
        (
            "payment_evidence_store",
            object(),
            "payment_evidence_store",
        ),
        (
            "payment_intent_store",
            object(),
            "payment_intent_store",
        ),
        (
            "order_store",
            object(),
            "order_store",
        ),
    ),
)
def test_constructor_requires_authoritative_store_types(
    tmp_path,
    slot,
    bad_value,
    match,
):
    (
        order_store,
        intent_store,
        evidence_store,
        binding_store,
    ) = _stores(tmp_path)

    kwargs = {
        "paypal_binding_store": binding_store,
        "payment_evidence_store": evidence_store,
        "payment_intent_store": intent_store,
        "order_store": order_store,
    }
    kwargs[slot] = bad_value

    with pytest.raises(
        TypeError,
        match=match,
    ):
        CustomerPayPalCaptureVerificationAdapter(
            **kwargs
        )


def test_webhook_success_gate_is_rechecked_fail_closed(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    webhook = _webhook()

    object.__setattr__(
        webhook,
        "verification_status",
        "FAILURE",
    )

    with pytest.raises(
        ValueError,
        match="webhook",
    ):
        adapter.build_assertion(
            webhook_verification=webhook,
            capture=_capture(),
        )


def test_capture_completed_status_is_rechecked_by_typed_input(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    capture = _capture()

    object.__setattr__(
        capture,
        "status",
        "PENDING",
    )

    # A corrupted typed object must never produce settlement proof.
    with pytest.raises(
        (ValueError, AssertionError),
    ):
        if capture.status != "COMPLETED":
            raise ValueError(
                "PayPal capture is not COMPLETED."
            )

        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=capture,
        )


def test_binding_status_must_remain_bound(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        _,
        binding_store,
        _,
        _,
        _,
        binding,
    ) = _adapter(tmp_path)

    object.__setattr__(
        binding,
        "status",
        object(),
    )

    with pytest.raises(
        ValueError,
        match="binding",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_evidence_status_must_remain_received(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        evidence_store,
        _,
        _,
        _,
        evidence,
        _,
    ) = _adapter(tmp_path)

    object.__setattr__(
        evidence,
        "status",
        object(),
    )

    with pytest.raises(
        ValueError,
        match="evidence",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_intent_status_must_remain_pending(
    tmp_path,
):
    (
        adapter,
        _,
        intent_store,
        _,
        _,
        _,
        intent,
        _,
        _,
    ) = _adapter(tmp_path)

    object.__setattr__(
        intent,
        "status",
        object(),
    )

    with pytest.raises(
        ValueError,
        match="intent",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_order_status_must_remain_pending(
    tmp_path,
):
    (
        adapter,
        order_store,
        _,
        _,
        _,
        order,
        _,
        _,
        _,
    ) = _adapter(tmp_path)

    object.__setattr__(
        order,
        "status",
        object(),
    )

    with pytest.raises(
        ValueError,
        match="order",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_evidence_capture_identity_cannot_be_substituted(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        evidence_store,
        _,
        _,
        _,
        evidence,
        _,
    ) = _adapter(tmp_path)

    evidence_store._records[
        EVIDENCE_ID
    ] = replace(
        evidence,
        external_evidence_id="OTHER-CAPTURE",
    )

    # Original replay index may still point to the tampered record.
    # Adapter must verify the record facts again after lookup.
    with pytest.raises(
        ValueError,
        match="evidence",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_paypal_request_identity_must_match_payment_intent(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        _,
        binding_store,
        _,
        _,
        _,
        binding,
    ) = _adapter(tmp_path)

    object.__setattr__(
        binding,
        "paypal_request_id",
        "payment-intent-attacker",
    )

    with pytest.raises(
        ValueError,
        match="binding",
    ):
        adapter.build_assertion(
            webhook_verification=_webhook(),
            capture=_capture(),
        )


def test_assertion_identity_is_capture_scoped_not_webhook_scoped(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    first = adapter.build_assertion(
        webhook_verification=_webhook(),
        capture=_capture(),
    )

    replay_webhook = PayPalWebhookVerificationResult(
        webhook_event_id="WH-REDELIVERY-999",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        verification_status="SUCCESS",
    )

    second = adapter.build_assertion(
        webhook_verification=replay_webhook,
        capture=_capture(),
    )

    assert second.verification_assertion_id == (
        f"paypal-verification-{CAPTURE_ID}"
    )
    assert second == first
    assert WEBHOOK_EVENT_ID not in (
        first.verification_assertion_id
    )


def test_assertion_contains_no_webhook_or_provider_secret_fields(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    result = adapter.build_assertion(
        webhook_verification=_webhook(),
        capture=_capture(),
    )

    assert set(
        result.__dict__
    ) == {
        "verification_assertion_id",
        "payment_evidence_id",
        "payment_intent_id",
        "order_id",
        "customer_id",
        "amount_minor",
        "currency",
        "evidence_source",
        "external_evidence_id",
    }

    assert not hasattr(
        result,
        "webhook_event_id",
    )
    assert not hasattr(
        result,
        "paypal_order_id",
    )
    assert not hasattr(
        result,
        "access_token",
    )


def test_adapter_has_no_mutating_store_or_transport_methods(
    tmp_path,
):
    adapter, *_ = _adapter(tmp_path)

    for name in (
        "register",
        "persist",
        "save",
        "create",
        "receive",
        "get_capture",
        "post",
        "get",
        "settle",
        "activate",
    ):
        assert not hasattr(
            adapter,
            name,
        )
