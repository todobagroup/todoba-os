from backend.commercial.customer_paypal_payment_initiation_api import (
    CustomerPayPalPaymentInitiationRequest,
    CustomerPayPalPaymentInitiationResponse,
)


def test_paypal_initiation_request_has_only_request_identity():
    fields = set(
        CustomerPayPalPaymentInitiationRequest.model_fields
    )

    assert fields == {
        "initiation_request_id",
    }


def test_paypal_initiation_response_contains_only_checkout_truth():
    fields = set(
        CustomerPayPalPaymentInitiationResponse.model_fields
    )

    assert fields == {
        "payment_intent_id",
        "order_id",
        "paypal_order_id",
        "approval_url",
        "amount_minor",
        "currency",
    }


def test_paypal_initiation_request_forbids_business_authority():
    forbidden = {
        "customer_id",
        "amount_minor",
        "currency",
        "payment_rail",
        "payment_intent_id",
        "paypal_order_id",
    }

    assert not (
        forbidden
        & set(
            CustomerPayPalPaymentInitiationRequest.model_fields
        )
    )
