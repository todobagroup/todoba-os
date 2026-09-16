from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationRecord,
    CustomerRegistrationStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)


class CustomerPaymentSettlementRegistrationConvergenceService:
    """
    Narrow offline convergence owner for historical customers whose
    authoritative payment-settlement lineage predates the commercial
    registration invariant.

    Input authority:
        settlement_id only

    Trust chain:
        settlement
            -> commercial order
            -> customer identity
            -> payment-derived setup activation
            -> customer registration

    This owner does not:
        - accept caller-supplied customer_id
        - verify or settle payment
        - create or mutate setup activation
        - create customer identity
        - mutate commercial order
        - expose an HTTP boundary
    """

    _REGISTRATION_REQUEST_PREFIX = (
        "payment-settlement-registration-"
    )
    _ACTIVATION_REQUEST_PREFIX = (
        "payment-settlement-activation-"
    )

    def __init__(
        self,
        *,
        settlement_store: CustomerPaymentSettlementStore,
        order_store: CustomerCommercialOrderStore,
        customer_identity_registry: CustomerIdentityRegistry,
        setup_activation_store: CustomerSetupActivationStore,
        registration_store: CustomerRegistrationStore,
    ) -> None:
        if not isinstance(
            settlement_store,
            CustomerPaymentSettlementStore,
        ):
            raise TypeError(
                "settlement_store must be "
                "CustomerPaymentSettlementStore."
            )

        if not isinstance(
            order_store,
            CustomerCommercialOrderStore,
        ):
            raise TypeError(
                "order_store must be "
                "CustomerCommercialOrderStore."
            )

        if not isinstance(
            customer_identity_registry,
            CustomerIdentityRegistry,
        ):
            raise TypeError(
                "customer_identity_registry must be "
                "CustomerIdentityRegistry."
            )

        if not isinstance(
            setup_activation_store,
            CustomerSetupActivationStore,
        ):
            raise TypeError(
                "setup_activation_store must be "
                "CustomerSetupActivationStore."
            )

        if not isinstance(
            registration_store,
            CustomerRegistrationStore,
        ):
            raise TypeError(
                "registration_store must be "
                "CustomerRegistrationStore."
            )

        if not settlement_store.is_ready():
            raise RuntimeError(
                "Customer payment settlement store "
                "is not initialized."
            )

        if not order_store.is_ready():
            raise RuntimeError(
                "Customer commercial order store "
                "is not initialized."
            )

        if not customer_identity_registry.is_ready():
            raise RuntimeError(
                "Customer identity registry "
                "is not initialized."
            )

        if not setup_activation_store.is_ready():
            raise RuntimeError(
                "Customer setup activation store "
                "is not initialized."
            )

        if not registration_store.is_ready():
            raise RuntimeError(
                "Customer registration store "
                "is not initialized."
            )

        self._settlement_store = settlement_store
        self._order_store = order_store
        self._customer_identity_registry = (
            customer_identity_registry
        )
        self._setup_activation_store = (
            setup_activation_store
        )
        self._registration_store = registration_store

    def converge(
        self,
        *,
        settlement_id: str,
    ) -> CustomerRegistrationRecord:
        normalized_settlement_id = (
            self._normalize_required_string(
                settlement_id,
                name="settlement_id",
            )
        )

        settlement = self._settlement_store.get(
            settlement_id=normalized_settlement_id,
        )

        if settlement is None:
            raise ValueError(
                "Payment settlement is not authoritative."
            )

        if (
            settlement.settlement_id
            != normalized_settlement_id
            or settlement.status
            is not CustomerPaymentSettlementStatus.SETTLED
        ):
            raise ValueError(
                "Payment settlement is not settled "
                "authoritative truth."
            )

        order = self._order_store.get(
            order_id=settlement.order_id,
        )

        if order is None:
            raise ValueError(
                "Commercial order is not authoritative."
            )

        if (
            order.order_id != settlement.order_id
            or order.customer_id != settlement.customer_id
            or order.amount_minor != settlement.amount_minor
            or order.currency != settlement.currency
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "Payment settlement does not match "
                "authoritative commercial order."
            )

        identity = self._customer_identity_registry.get(
            customer_id=settlement.customer_id,
        )

        if (
            identity is None
            or identity.customer_id != settlement.customer_id
        ):
            raise ValueError(
                "Customer identity is not authoritative."
            )

        activation_request_id = (
            self._ACTIVATION_REQUEST_PREFIX
            + normalized_settlement_id
        )

        activation = (
            self._setup_activation_store
            .get_by_activation_request_id(
                activation_request_id=(
                    activation_request_id
                )
            )
        )

        if activation is None:
            raise ValueError(
                "Payment-derived setup activation "
                "is not authoritative."
            )

        if (
            activation.activation_request_id
            != activation_request_id
            or activation.customer_id
            != settlement.customer_id
            or activation.status
            is not CustomerSetupActivationStatus.ACTIVE
            or activation.deployment_id is not None
        ):
            raise ValueError(
                "Payment-derived setup activation "
                "does not match authoritative "
                "settlement lineage."
            )

        existing = (
            self._registration_store.get_by_customer_id(
                customer_id=settlement.customer_id,
            )
        )

        if existing is not None:
            return existing

        registration_request_id = (
            self._REGISTRATION_REQUEST_PREFIX
            + normalized_settlement_id
        )

        record = CustomerRegistrationRecord(
            registration_request_id=(
                registration_request_id
            ),
            customer_id=settlement.customer_id,
        )

        stored = self._registration_store.register(
            record
        )

        if (
            stored.registration_request_id
            != registration_request_id
            or stored.customer_id
            != settlement.customer_id
        ):
            raise RuntimeError(
                "Customer registration convergence "
                "returned mismatched authoritative truth."
            )

        return stored

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized
