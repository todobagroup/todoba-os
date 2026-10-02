from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
)
from backend.commercial.customer_commercial_current_billing_cycle_service import (
    CustomerCommercialCurrentBillingCycleService,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    PaymentRail,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingService,
    PayPalOrderCreationResult,
)
from backend.commercial.customer_paypal_order_http_client import (
    CustomerPayPalOrderHttpClient,
)
from backend.commercial.customer_paypal_payment_initiation_service import (
    CustomerPayPalPaymentInitiationResult,
    CustomerPayPalPaymentInitiationService,
)


def _typed_mock(owner_type):
    return Mock(spec=owner_type)


def test_paypal_payment_initiation_result_contract():
    annotations = (
        CustomerPayPalPaymentInitiationResult.__annotations__
    )

    assert set(annotations) == {
        "order",
        "payment_intent",
        "paypal_order",
        "binding",
    }


def test_paypal_payment_initiation_derives_all_payment_truth_server_side():
    balance = Decimal("1000.00")

    quote = CustomerCommercialAccountPriceBook.quote(
        authoritative_cycle_balance_usd=balance
    )

    current_cycle = _typed_mock(
        CustomerCommercialCurrentBillingCycleService
    )
    order_service = _typed_mock(
        CustomerCommercialOrderService
    )
    intent_service = _typed_mock(
        CustomerPaymentIntentService
    )
    paypal_client = _typed_mock(
        CustomerPayPalOrderHttpClient
    )
    binding_service = _typed_mock(
        CustomerPayPalOrderBindingService
    )

    customer = _typed_mock(
        CustomerIdentity
    )
    customer.customer_id = "customer-001"

    current_cycle.resolve_current.return_value = (
        SimpleNamespace(
            authoritative_cycle_balance_usd=balance,
            licensed_account_cap_usd=(
                quote.licensed_account_cap_usd
            ),
            standard_monthly_price_usd=(
                quote.standard_monthly_price_usd
            ),
        )
    )

    amount_minor = (
        quote.standard_monthly_price_usd
        * 100
    )

    order = SimpleNamespace(
        order_id="order-001",
        amount_minor=amount_minor,
        currency="USD",
    )

    intent = SimpleNamespace(
        payment_intent_id="payment-intent-001",
    )

    paypal_order = PayPalOrderCreationResult(
        paypal_order_id="paypal-order-001",
        paypal_request_id="payment-intent-001",
        custom_id="payment-intent-001",
        amount_minor=amount_minor,
        currency="USD",
        approval_url=(
            "https://www.sandbox.paypal.com/"
            "checkoutnow?token=paypal-order-001"
        ),
    )

    binding = SimpleNamespace(
        payment_intent_id="payment-intent-001",
        order_id="order-001",
        paypal_order_id="paypal-order-001",
        amount_minor=amount_minor,
        currency="USD",
    )

    order_service.create.return_value = order
    intent_service.create.return_value = intent
    paypal_client.create_order.return_value = (
        paypal_order
    )
    binding_service.bind.return_value = binding

    service = CustomerPayPalPaymentInitiationService(
        current_billing_cycle_service=current_cycle,
        order_service=order_service,
        payment_intent_service=intent_service,
        paypal_order_client=paypal_client,
        paypal_binding_service=binding_service,
    )

    result = service.initiate(
        initiation_request_id="request-001",
        authenticated_customer=customer,
    )

    current_cycle.resolve_current.assert_called_once_with(
        customer_id="customer-001"
    )

    order_service.create.assert_called_once_with(
        order_request_id="request-001:order",
        authorized_customer=customer,
        amount_minor=amount_minor,
        currency="USD",
    )

    intent_service.create.assert_called_once_with(
        payment_intent_request_id="request-001:intent",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    paypal_client.create_order.assert_called_once_with(
        payment_intent_id="payment-intent-001",
        amount_minor=amount_minor,
        currency="USD",
    )

    binding_service.bind.assert_called_once_with(
        authorized_payment_intent=intent,
        paypal_order=paypal_order,
    )

    assert result.order is order
    assert result.payment_intent is intent
    assert result.paypal_order is paypal_order
    assert result.binding is binding


def test_paypal_payment_initiation_rejects_missing_provider_approval_url():
    balance = Decimal("1000.00")

    quote = CustomerCommercialAccountPriceBook.quote(
        authoritative_cycle_balance_usd=balance
    )

    current_cycle = _typed_mock(
        CustomerCommercialCurrentBillingCycleService
    )
    order_service = _typed_mock(
        CustomerCommercialOrderService
    )
    intent_service = _typed_mock(
        CustomerPaymentIntentService
    )
    paypal_client = _typed_mock(
        CustomerPayPalOrderHttpClient
    )
    binding_service = _typed_mock(
        CustomerPayPalOrderBindingService
    )
    customer = _typed_mock(
        CustomerIdentity
    )

    customer.customer_id = "customer-001"

    current_cycle.resolve_current.return_value = (
        SimpleNamespace(
            authoritative_cycle_balance_usd=balance,
            licensed_account_cap_usd=(
                quote.licensed_account_cap_usd
            ),
            standard_monthly_price_usd=(
                quote.standard_monthly_price_usd
            ),
        )
    )

    amount_minor = (
        quote.standard_monthly_price_usd
        * 100
    )

    order_service.create.return_value = (
        SimpleNamespace(
            order_id="order-001",
            amount_minor=amount_minor,
            currency="USD",
        )
    )

    intent_service.create.return_value = (
        SimpleNamespace(
            payment_intent_id="payment-intent-001",
        )
    )

    paypal_client.create_order.return_value = (
        PayPalOrderCreationResult(
            paypal_order_id="paypal-order-001",
            paypal_request_id="payment-intent-001",
            custom_id="payment-intent-001",
            amount_minor=amount_minor,
            currency="USD",
        )
    )

    service = CustomerPayPalPaymentInitiationService(
        current_billing_cycle_service=current_cycle,
        order_service=order_service,
        payment_intent_service=intent_service,
        paypal_order_client=paypal_client,
        paypal_binding_service=binding_service,
    )

    try:
        service.initiate(
            initiation_request_id="request-001",
            authenticated_customer=customer,
        )
    except RuntimeError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError(
            "Missing PayPal approval URL must fail."
        )

    binding_service.bind.assert_not_called()
