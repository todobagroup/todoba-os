from datetime import UTC
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineStore,
)
from backend.commercial.customer_commercial_capacity_decision_provider import (
    CustomerCommercialCapacityDecisionProvider,
)
from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecision,
    CustomerCommercialCapacityDecisionStatus,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_external_funding_api import (
    create_customer_commercial_external_funding_router,
)
from backend.commercial.customer_commercial_external_funding_convergence_service import (
    CustomerCommercialExternalFundingConvergenceService,
)
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationService,
    CustomerCommercialExternalFundingObservationStore,
)
from backend.commercial.customer_commercial_pending_exposure_containment_service import (
    CustomerCommercialPendingExposureContainmentService,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.lifecycle.mt5_external_funding_classifier import (
    MT5ExternalFundingClassifier,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "external-funding-test-secret"

ACCOUNT = "RoboForex-Pro:68353796"
OTHER_ACCOUNT = "RoboForex-Pro:99999999"

CUSTOMER_ID = "customer-001"
DEPLOYMENT_ID = "deployment-001"
ENTITLEMENT_ID = "commercial-entitlement-001"
CYCLE_ID = "cycle-001"

DEAL_TICKET = 2254467273

PATH = "/commercial/external-funding/evidence"


class StubCommercialDeploymentBindingStore(
    CustomerCommercialDeploymentBindingStore
):
    def __init__(self) -> None:
        pass

    def get_by_agent_account(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ):
        if (
            agent_id == AGENT_ID
            and account_fingerprint == ACCOUNT
        ):
            return CustomerCommercialDeploymentBinding(
                commercial_entitlement_id=ENTITLEMENT_ID,
                customer_id=CUSTOMER_ID,
                deployment_id=DEPLOYMENT_ID,
                agent_id=AGENT_ID,
                account_fingerprint=ACCOUNT,
            )

        return None


class StubCapacityDecisionProvider(
    CustomerCommercialCapacityDecisionProvider
):
    def __init__(self) -> None:
        pass

    def provide(
        self,
        *,
        deployment_id: str,
    ) -> CustomerCommercialCapacityDecision:
        assert deployment_id == DEPLOYMENT_ID

        return CustomerCommercialCapacityDecision(
            commercial_entitlement_id=ENTITLEMENT_ID,
            deployment_id=DEPLOYMENT_ID,
            cycle_id=CYCLE_ID,
            licensed_account_cap_usd=Decimal("10000"),
            operational_grace_limit_usd=Decimal("10500"),
            commercial_capacity_high_water_usd=Decimal("10000"),
            status=(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
        )


class NoOpPendingExposureContainmentService(
    CustomerCommercialPendingExposureContainmentService
):
    def __init__(self) -> None:
        pass

    def issue(
        self,
        *,
        trigger_id: str,
        deployment_id: str,
    ):
        return ()


class StubBillingCycleStore(
    CustomerCommercialBillingCycleBaselineStore
):
    def __init__(self) -> None:
        pass

    def is_ready(self) -> bool:
        return True

    def get(
        self,
        *,
        cycle_id: str,
    ):
        if cycle_id == CYCLE_ID:
            return object()

        return None


def _headers() -> dict[str, str]:
    return {
        "X-TODOBA-Agent-ID": AGENT_ID,
        "Authorization": (
            f"Bearer {AGENT_SECRET}"
        ),
    }


def _payload(
    *,
    account_fingerprint: str = ACCOUNT,
    comment: str = "Deposit to 68353796",
    deal_ticket: int = DEAL_TICKET,
) -> dict[str, object]:
    return {
        "account_fingerprint": (
            account_fingerprint
        ),
        "deal_ticket": deal_ticket,
        "deal_time_msc": 1788882804670,
        "observed_at": (
            "2026-09-08T12:46:44Z"
        ),
        "cashflow_kind": "balance",
        "raw_deal_type": 2,
        "amount": "8000",
        "order_ticket": 0,
        "deal_entry": 0,
        "magic": 0,
        "position_id": 0,
        "deal_reason": 0,
        "volume": 0.0,
        "price": 0.0,
        "symbol": "",
        "external_id": "",
        "comment": comment,
    }


def _build(
    tmp_path: Path,
):
    observation_path = (
        tmp_path
        / "external-funding-observations.json"
    )

    observation_store = (
        CustomerCommercialExternalFundingObservationStore(
            observation_path
        )
    )
    observation_store.initialize_empty()

    observation_service = (
        CustomerCommercialExternalFundingObservationService(
            store=observation_store,
            billing_cycle_store=StubBillingCycleStore(),
        )
    )

    convergence_service = (
        CustomerCommercialExternalFundingConvergenceService(
            deployment_binding_store=(
                StubCommercialDeploymentBindingStore()
            ),
            capacity_decision_provider=(
                StubCapacityDecisionProvider()
            ),
            external_funding_classifier=(
                MT5ExternalFundingClassifier()
            ),
            observation_service=observation_service,
            pending_exposure_containment_service=(
                NoOpPendingExposureContainmentService()
            ),
        )
    )

    agent_binding_store = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "trusted-agent-account-bindings.json"
        )
    )
    agent_binding_store.initialize_empty()

    agent_binding_store.bind(
        agent_id=AGENT_ID,
        account_fingerprint=ACCOUNT,
    )

    account_binding_guard = (
        TrustedAgentAccountBindingGuard(
            agent_binding_store
        )
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_customer_commercial_external_funding_router(
            convergence_service=convergence_service,
            authenticator=authenticator,
            account_binding_guard=account_binding_guard,
        )
    )

    return (
        TestClient(app),
        observation_store,
        observation_path,
    )


def test_bound_authenticated_deposit_is_durably_observed(
    tmp_path: Path,
) -> None:
    (
        client,
        store,
        observation_path,
    ) = _build(
        tmp_path
    )

    response = client.post(
        PATH,
        headers=_headers(),
        json=_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "status": "stored",
        "cycle_id": CYCLE_ID,
        "account_fingerprint": ACCOUNT,
        "deal_ticket": DEAL_TICKET,
        "funding_kind": "external_deposit",
        "amount": "8000",
    }

    stored = store.get_by_replay_identity(
        account_fingerprint=ACCOUNT,
        deal_ticket=DEAL_TICKET,
    )

    assert stored is not None
    assert stored.cycle_id == CYCLE_ID
    assert stored.funding_kind == "external_deposit"
    assert stored.amount == Decimal("8000")

    # Prove the fact is durable, not memory-only.
    restored = (
        CustomerCommercialExternalFundingObservationStore(
            observation_path
        )
    )
    restored.load()

    restored_record = (
        restored.get_by_replay_identity(
            account_fingerprint=ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
    )

    assert restored_record == stored


def test_wrong_account_is_forbidden_without_commercial_write(
    tmp_path: Path,
) -> None:
    client, store, _ = _build(
        tmp_path
    )

    response = client.post(
        PATH,
        headers=_headers(),
        json=_payload(
            account_fingerprint=OTHER_ACCOUNT,
        ),
    )

    assert response.status_code == 403

    assert (
        store.get_by_replay_identity(
            account_fingerprint=OTHER_ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
        is None
    )

    assert (
        store.get_by_replay_identity(
            account_fingerprint=ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
        is None
    )


def test_caller_cannot_supply_commercial_authority(
    tmp_path: Path,
) -> None:
    forbidden_fields = {
        "cycle_id": CYCLE_ID,
        "customer_id": CUSTOMER_ID,
        "deployment_id": DEPLOYMENT_ID,
        "commercial_entitlement_id": (
            ENTITLEMENT_ID
        ),
        "funding_kind": "external_deposit",
    }

    for field_name, value in forbidden_fields.items():
        client, store, _ = _build(
            tmp_path
            / field_name
        )

        payload = _payload()
        payload[field_name] = value

        response = client.post(
            PATH,
            headers=_headers(),
            json=payload,
        )

        assert response.status_code == 422

        assert (
        store.get_by_replay_identity(
            account_fingerprint=ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
        is None
    )


def test_unproven_cashflow_does_not_become_commercial_funding(
    tmp_path: Path,
) -> None:
    client, store, _ = _build(
        tmp_path
    )

    response = client.post(
        PATH,
        headers=_headers(),
        json=_payload(
            comment="Unproven broker cashflow",
        ),
    )

    assert response.status_code == 422

    assert (
        store.get_by_replay_identity(
            account_fingerprint=ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
        is None
    )

    assert (
        store.get_by_replay_identity(
            account_fingerprint=ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
        is None
    )


def test_authentication_failure_does_not_write(
    tmp_path: Path,
) -> None:
    client, store, _ = _build(
        tmp_path
    )

    response = client.post(
        PATH,
        headers={
            "X-TODOBA-Agent-ID": AGENT_ID,
            "Authorization": "Bearer wrong-secret",
        },
        json=_payload(),
    )

    assert response.status_code == 401
    assert (
        store.get_by_replay_identity(
            account_fingerprint=ACCOUNT,
            deal_ticket=DEAL_TICKET,
        )
        is None
    )
