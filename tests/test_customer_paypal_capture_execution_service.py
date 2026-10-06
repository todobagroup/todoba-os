import inspect

from backend.commercial.customer_paypal_capture_execution_api import (
    CustomerPayPalCaptureExecutionRequest,
    CustomerPayPalCaptureExecutionResponse,
)
from backend.commercial.customer_paypal_capture_execution_service import (
    CustomerPayPalCaptureExecutionService,
)
from backend.commercial.customer_paypal_order_http_client import (
    CustomerPayPalOrderHttpClient,
)


def test_capture_execution_owner_exists():
    assert CustomerPayPalCaptureExecutionService is not None


def test_capture_execution_request_has_only_intent_identity():
    assert set(
        CustomerPayPalCaptureExecutionRequest.model_fields
    ) == {
        "payment_intent_id",
    }


def test_capture_execution_request_forbids_provider_authority():
    forbidden = {
        "customer_id",
        "order_id",
        "paypal_order_id",
        "paypal_request_id",
        "capture_id",
        "amount_minor",
        "currency",
        "payment_rail",
        "provider_status",
    }

    assert not (
        forbidden
        & set(
            CustomerPayPalCaptureExecutionRequest.model_fields
        )
    )


def test_capture_execution_response_contains_no_payment_truth():
    assert set(
        CustomerPayPalCaptureExecutionResponse.model_fields
    ) == {
        "payment_intent_id",
        "order_id",
        "paypal_order_id",
        "provider_status",
    }


def test_order_client_owns_capture_order_transport():
    method = getattr(
        CustomerPayPalOrderHttpClient,
        "capture_order",
        None,
    )

    assert callable(method)

    signature = inspect.signature(method)

    assert set(signature.parameters) == {
        "self",
        "paypal_order_id",
        "paypal_request_id",
    }


def test_capture_execution_uses_customer_and_intent_only():
    signature = inspect.signature(
        CustomerPayPalCaptureExecutionService.capture
    )

    assert set(signature.parameters) == {
        "self",
        "payment_intent_id",
        "authenticated_customer",
    }