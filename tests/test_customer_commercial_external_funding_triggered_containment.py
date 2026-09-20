from datetime import UTC
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

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
from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowEvidence,
)
from backend.trading.lifecycle.mt5_external_funding_classifier import (
    MT5ExternalFundingClassifier,
)


AGENT_ID = "trusted-agent-001"
ACCOUNT = "RoboForex-Pro:68353796"

CUSTOMER_ID = "customer-001"
DEPLOYMENT_ID = "deployment-001"
ENTITLEMENT_ID = "commercial-entitlement-001"
CYCLE_ID = "cycle-001"

DEAL_TICKET = 2254467273


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
        assert agent_id == AGENT_ID
        assert account_fingerprint == ACCOUNT

        return CustomerCommercialDeploymentBinding(
            commercial_entitlement_id=ENTITLEMENT_ID,
            customer_id=CUSTOMER_ID,
            deployment_id=DEPLOYMENT_ID,
            agent_id=AGENT_ID,
            account_fingerprint=ACCOUNT,
        )


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


def _decision(
    status: CustomerCommercialCapacityDecisionStatus,
) -> CustomerCommercialCapacityDecision:
    high_water = (
        Decimal("12000")
        if status
        == CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
        else Decimal("10000")
    )

    return CustomerCommercialCapacityDecision(
        commercial_entitlement_id=ENTITLEMENT_ID,
        deployment_id=DEPLOYMENT_ID,
        cycle_id=CYCLE_ID,
        licensed_account_cap_usd=Decimal("10000"),
        operational_grace_limit_usd=Decimal("10500"),
        commercial_capacity_high_water_usd=high_water,
        status=status,
    )


class SequencedCapacityDecisionProvider(
    CustomerCommercialCapacityDecisionProvider
):
    def __init__(
        self,
        decisions,
    ) -> None:
        self.decisions = list(decisions)
        self.calls: list[str] = []

    def provide(
        self,
        *,
        deployment_id: str,
    ) -> CustomerCommercialCapacityDecision:
        assert deployment_id == DEPLOYMENT_ID

        self.calls.append(deployment_id)

        if not self.decisions:
            raise AssertionError(
                "Unexpected extra capacity decision."
            )

        return self.decisions.pop(0)


class RecordingContainmentService(
    CustomerCommercialPendingExposureContainmentService
):
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, str]
        ] = []

    def issue(
        self,
        *,
        trigger_id: str,
        deployment_id: str,
    ):
        self.calls.append(
            (
                trigger_id,
                deployment_id,
            )
        )

        return ()


def _evidence(
    *,
    amount: Decimal = Decimal("8000"),
    comment: str = "Deposit to 68353796",
) -> MT5AccountCashflowEvidence:
    return MT5AccountCashflowEvidence(
        account_fingerprint=ACCOUNT,
        deal_ticket=DEAL_TICKET,
        deal_time_msc=1788882804670,
        observed_at=datetime(
            2026,
            9,
            8,
            12,
            46,
            44,
            tzinfo=UTC,
        ),
        cashflow_kind="balance",
        raw_deal_type=2,
        amount=amount,
        order_ticket=0,
        deal_entry=0,
        magic=0,
        position_id=0,
        deal_reason=0,
        volume=0.0,
        price=0.0,
        symbol="",
        external_id="",
        comment=comment,
    )


def _observation_service(
    tmp_path: Path,
) -> CustomerCommercialExternalFundingObservationService:
    store = (
        CustomerCommercialExternalFundingObservationStore(
            tmp_path
            / "external-funding-observations.json"
        )
    )
    store.initialize_empty()

    return CustomerCommercialExternalFundingObservationService(
        store=store,
        billing_cycle_store=StubBillingCycleStore(),
    )


def test_external_deposit_recomputes_capacity_after_durable_observation_and_contains(
    tmp_path: Path,
) -> None:
    capacity_provider = SequencedCapacityDecisionProvider(
        (
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .UPGRADE_REQUIRED
            ),
        )
    )

    containment = RecordingContainmentService()

    service = (
        CustomerCommercialExternalFundingConvergenceService(
            deployment_binding_store=(
                StubCommercialDeploymentBindingStore()
            ),
            capacity_decision_provider=capacity_provider,
            external_funding_classifier=(
                MT5ExternalFundingClassifier()
            ),
            observation_service=(
                _observation_service(
                    tmp_path
                )
            ),
            pending_exposure_containment_service=(
                containment
            ),
        )
    )

    observation = service.converge(
        authenticated_agent_id=AGENT_ID,
        evidence=_evidence(),
    )

    assert observation.account_fingerprint == ACCOUNT
    assert observation.deal_ticket == DEAL_TICKET
    assert observation.funding_kind == "external_deposit"

    assert capacity_provider.calls == [
        DEPLOYMENT_ID,
        DEPLOYMENT_ID,
    ]

    assert containment.calls == [
        (
            f"external-funding:{ACCOUNT}:{DEAL_TICKET}",
            DEPLOYMENT_ID,
        )
    ]


def _custom_decision(
    *,
    status: CustomerCommercialCapacityDecisionStatus,
    deployment_id: str = DEPLOYMENT_ID,
    commercial_entitlement_id: str = ENTITLEMENT_ID,
    cycle_id: str = CYCLE_ID,
) -> CustomerCommercialCapacityDecision:
    return CustomerCommercialCapacityDecision(
        commercial_entitlement_id=(
            commercial_entitlement_id
        ),
        deployment_id=deployment_id,
        cycle_id=cycle_id,
        licensed_account_cap_usd=Decimal("10000"),
        operational_grace_limit_usd=Decimal("10500"),
        commercial_capacity_high_water_usd=(
            Decimal("12000")
            if status
            == CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
            else Decimal("10000")
        ),
        status=status,
    )


def _build_service(
    *,
    tmp_path: Path,
    capacity_provider,
    containment,
):
    return CustomerCommercialExternalFundingConvergenceService(
        deployment_binding_store=(
            StubCommercialDeploymentBindingStore()
        ),
        capacity_decision_provider=capacity_provider,
        external_funding_classifier=(
            MT5ExternalFundingClassifier()
        ),
        observation_service=(
            _observation_service(tmp_path)
        ),
        pending_exposure_containment_service=(
            containment
        ),
    )


def test_allow_new_exposure_does_not_issue_containment(
    tmp_path: Path,
) -> None:
    provider = SequencedCapacityDecisionProvider(
        (
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
        )
    )

    containment = RecordingContainmentService()

    service = _build_service(
        tmp_path=tmp_path,
        capacity_provider=provider,
        containment=containment,
    )

    observation = service.converge(
        authenticated_agent_id=AGENT_ID,
        evidence=_evidence(),
    )

    assert observation.funding_kind == "external_deposit"
    assert provider.calls == [
        DEPLOYMENT_ID,
        DEPLOYMENT_ID,
    ]
    assert containment.calls == []


@pytest.mark.parametrize(
    (
        "post_decision",
        "expected_message",
    ),
    (
        (
            _custom_decision(
                status=(
                    CustomerCommercialCapacityDecisionStatus
                    .UPGRADE_REQUIRED
                ),
                deployment_id="deployment-other",
            ),
            "deployment identity is inconsistent",
        ),
        (
            _custom_decision(
                status=(
                    CustomerCommercialCapacityDecisionStatus
                    .UPGRADE_REQUIRED
                ),
                commercial_entitlement_id=(
                    "commercial-entitlement-other"
                ),
            ),
            "entitlement identity is inconsistent",
        ),
        (
            _custom_decision(
                status=(
                    CustomerCommercialCapacityDecisionStatus
                    .UPGRADE_REQUIRED
                ),
                cycle_id="cycle-other",
            ),
            "cycle identity is inconsistent",
        ),
    ),
)
def test_post_observation_identity_drift_fails_closed(
    tmp_path: Path,
    post_decision,
    expected_message: str,
) -> None:
    provider = SequencedCapacityDecisionProvider(
        (
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
            post_decision,
        )
    )

    containment = RecordingContainmentService()

    service = _build_service(
        tmp_path=tmp_path,
        capacity_provider=provider,
        containment=containment,
    )

    with pytest.raises(
        RuntimeError,
        match=expected_message,
    ):
        service.converge(
            authenticated_agent_id=AGENT_ID,
            evidence=_evidence(),
        )

    assert containment.calls == []


def test_identical_broker_replay_uses_same_trigger_identity(
    tmp_path: Path,
) -> None:
    provider = SequencedCapacityDecisionProvider(
        (
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .UPGRADE_REQUIRED
            ),
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            ),
            _decision(
                CustomerCommercialCapacityDecisionStatus
                .UPGRADE_REQUIRED
            ),
        )
    )

    containment = RecordingContainmentService()

    service = _build_service(
        tmp_path=tmp_path,
        capacity_provider=provider,
        containment=containment,
    )

    first = service.converge(
        authenticated_agent_id=AGENT_ID,
        evidence=_evidence(),
    )

    second = service.converge(
        authenticated_agent_id=AGENT_ID,
        evidence=_evidence(),
    )

    assert first == second

    expected_trigger = (
        f"external-funding:{ACCOUNT}:{DEAL_TICKET}"
    )

    assert containment.calls == [
        (
            expected_trigger,
            DEPLOYMENT_ID,
        ),
        (
            expected_trigger,
            DEPLOYMENT_ID,
        ),
    ]
