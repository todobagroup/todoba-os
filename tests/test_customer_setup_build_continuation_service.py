from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
)
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationRecord,
    CustomerSetupBuildContinuationService,
    CustomerSetupBuildContinuationStatus,
    CustomerSetupBuildContinuationStore,
    derive_customer_setup_build_continuation_account_fingerprint,
    derive_customer_setup_build_continuation_issuance_request_id,
    derive_customer_setup_build_continuation_verifier,
)


NOW = datetime(
    2026,
    9,
    1,
    4,
    41,
    53,
    tzinfo=timezone.utc,
)

SETUP_ACTIVATION_ID = (
    "setup-activation-55dbe7b67ebe4fb3b6b4d684c785b973"
)

CUSTOMER_ID = (
    "customer-f9d1ad4fe5a140879ab864874f6e2984"
)

DEPLOYMENT_ID = (
    "deployment-0731d8bf591c4c918e3e27d916d45da4"
)

ACCOUNT_FINGERPRINT = (
    "Exness-MT5Trial6|414282209|XAUUSD247m"
)


class FakeSetupActivationStore:
    def __init__(
        self,
        *,
        status=CustomerSetupActivationStatus.ACTIVE,
        deployment_id=None,
    ) -> None:
        self.record = SimpleNamespace(
            setup_activation_id=SETUP_ACTIVATION_ID,
            customer_id=CUSTOMER_ID,
            deployment_id=deployment_id,
            status=status,
        )

    def get(
        self,
        *,
        setup_activation_id,
    ):
        if (
            setup_activation_id
            != SETUP_ACTIVATION_ID
        ):
            return None

        return self.record


class FakeBuildRequestStore:
    def __init__(
        self,
        *,
        deployment_id=DEPLOYMENT_ID,
        bootstrap_request_id=SETUP_ACTIVATION_ID,
        missing=False,
    ) -> None:
        self._deployment_id = deployment_id
        self._bootstrap_request_id = (
            bootstrap_request_id
        )
        self._missing = missing

    def get(
        self,
        *,
        deployment_id,
    ):
        if self._missing:
            return None

        if deployment_id != self._deployment_id:
            return None

        return CustomerDeploymentPackageBuildRequest(
            deployment_id=(
                self._deployment_id
            ),
            bootstrap_request_id=(
                self._bootstrap_request_id
            ),
        )


def _environment(
    tmp_path: Path,
    *,
    status=CustomerSetupActivationStatus.ACTIVE,
    activation_deployment_id=None,
    build_bootstrap_request_id=(
        SETUP_ACTIVATION_ID
    ),
    build_missing=False,
):
    continuation_store = (
        CustomerSetupBuildContinuationStore(
            tmp_path
            / "customer_setup_build_continuations.json"
        )
    )

    continuation_store.initialize_empty()

    activation_store = (
        FakeSetupActivationStore(
            status=status,
            deployment_id=(
                activation_deployment_id
            ),
        )
    )

    build_request_store = (
        FakeBuildRequestStore(
            bootstrap_request_id=(
                build_bootstrap_request_id
            ),
            missing=build_missing,
        )
    )

    service = (
        CustomerSetupBuildContinuationService(
            continuation_store=(
                continuation_store
            ),
            setup_activation_store=(
                activation_store
            ),
            build_request_store=(
                build_request_store
            ),
        )
    )

    return (
        continuation_store,
        activation_store,
        build_request_store,
        service,
    )


def _issue(
    service,
    *,
    current_time=NOW,
    account_fingerprint=ACCOUNT_FINGERPRINT,
):
    return service.issue(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        deployment_id=DEPLOYMENT_ID,
        account_fingerprint=(
            account_fingerprint
        ),
        current_time=current_time,
    )


def test_issue_creates_narrow_24_hour_continuation(
    tmp_path: Path,
) -> None:
    store, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    assert issued.continuation_credential.startswith(
        "tdbsc1."
        + issued.continuation_id
        + "."
    )

    issued_at = datetime.fromisoformat(
        issued.issued_at.replace(
            "Z",
            "+00:00",
        )
    )

    expires_at = datetime.fromisoformat(
        issued.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    assert (
        expires_at
        - issued_at
        == timedelta(
            hours=24
        )
    )

    record = store.get(
        continuation_id=(
            issued.continuation_id
        )
    )

    assert record is not None

    assert (
        record.setup_activation_id
        == SETUP_ACTIVATION_ID
    )

    assert (
        record.deployment_id
        == DEPLOYMENT_ID
    )

    assert (
        record.status
        is CustomerSetupBuildContinuationStatus.ACTIVE
    )


def test_plaintext_credential_and_account_are_not_persisted(
    tmp_path: Path,
) -> None:
    store, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    persisted = (
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    secret = (
        issued.continuation_credential
        .split(
            "."
        )[2]
    )

    assert (
        issued.continuation_credential
        not in persisted
    )

    assert secret not in persisted

    assert (
        ACCOUNT_FINGERPRINT
        not in persisted
    )

    assert (
        derive_customer_setup_build_continuation_verifier(
            issued.continuation_credential
        )
        in persisted
    )

    assert (
        derive_customer_setup_build_continuation_account_fingerprint(
            ACCOUNT_FINGERPRINT
        )
        in persisted
    )


def test_authorize_returns_authoritative_identity(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    authorized = service.authorize(
        continuation_credential=(
            issued.continuation_credential
        ),
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
        current_time=(
            NOW
            + timedelta(
                hours=1
            )
        ),
    )

    assert (
        authorized.continuation_id
        == issued.continuation_id
    )

    assert (
        authorized.setup_activation_id
        == SETUP_ACTIVATION_ID
    )

    assert (
        authorized.customer_id
        == CUSTOMER_ID
    )

    assert (
        authorized.deployment_id
        == DEPLOYMENT_ID
    )


def test_retry_rotates_secret_but_preserves_identity_and_lifetime(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    first = _issue(
        service
    )

    second = _issue(
        service,
        current_time=(
            NOW
            + timedelta(
                hours=2
            )
        ),
    )

    assert (
        second.issuance_request_id
        == first.issuance_request_id
    )

    assert (
        second.continuation_id
        == first.continuation_id
    )

    assert (
        second.issued_at
        == first.issued_at
    )

    assert (
        second.expires_at
        == first.expires_at
    )

    assert (
        second.continuation_credential
        != first.continuation_credential
    )

    with pytest.raises(
        ValueError,
        match="Invalid",
    ):
        service.authorize(
            continuation_credential=(
                first.continuation_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    hours=2
                )
            ),
        )

    authorized = service.authorize(
        continuation_credential=(
            second.continuation_credential
        ),
        current_time=(
            NOW
            + timedelta(
                hours=2
            )
        ),
    )

    assert (
        authorized.deployment_id
        == DEPLOYMENT_ID
    )


def test_account_fingerprint_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="account fingerprint mismatch",
    ):
        service.authorize(
            continuation_credential=(
                issued.continuation_credential
            ),
            account_fingerprint=(
                "different-account"
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_expired_continuation_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="expired",
    ):
        service.authorize(
            continuation_credential=(
                issued.continuation_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    hours=24
                )
            ),
        )


def test_expired_continuation_cannot_be_reissued(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="Expired",
    ):
        _issue(
            service,
            current_time=(
                NOW
                + timedelta(
                    hours=24
                )
            ),
        )


def test_revoked_continuation_cannot_authorize_or_reissue(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    service.revoke(
        continuation_id=(
            issued.continuation_id
        )
    )

    with pytest.raises(
        ValueError,
        match="revoked",
    ):
        service.authorize(
            continuation_credential=(
                issued.continuation_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )

    with pytest.raises(
        ValueError,
        match="REVOKED",
    ):
        _issue(
            service,
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_missing_build_request_fails_closed(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path,
            build_missing=True,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="build request is missing",
    ):
        _issue(
            service
        )


def test_build_request_must_belong_to_same_setup_activation(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path,
            build_bootstrap_request_id=(
                "different-setup-activation"
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="bootstrap identity mismatch",
    ):
        _issue(
            service
        )


def test_suspended_activation_fails_closed_after_issuance(
    tmp_path: Path,
) -> None:
    _, activation_store, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    activation_store.record = SimpleNamespace(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=CUSTOMER_ID,
        deployment_id=None,
        status=(
            CustomerSetupActivationStatus.SUSPENDED
        ),
    )

    with pytest.raises(
        ValueError,
        match="SUSPENDED",
    ):
        service.authorize(
            continuation_credential=(
                issued.continuation_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_bound_activation_authorizes_same_deployment(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path,
            status=(
                CustomerSetupActivationStatus.BOUND
            ),
            activation_deployment_id=(
                DEPLOYMENT_ID
            ),
        )
    )

    issued = _issue(
        service
    )

    authorized = service.authorize(
        continuation_credential=(
            issued.continuation_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert (
        authorized.deployment_id
        == DEPLOYMENT_ID
    )


def test_bound_activation_deployment_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path,
            status=(
                CustomerSetupActivationStatus.BOUND
            ),
            activation_deployment_id=(
                "different-deployment"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="deployment identity mismatch",
    ):
        _issue(
            service
        )


def test_store_reopens_durable_state(
    tmp_path: Path,
) -> None:
    store, activation_store, build_store, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    reopened = (
        CustomerSetupBuildContinuationStore(
            store.storage_path
        )
    )

    assert reopened.is_ready is True

    recovered_service = (
        CustomerSetupBuildContinuationService(
            continuation_store=reopened,
            setup_activation_store=(
                activation_store
            ),
            build_request_store=(
                build_store
            ),
        )
    )

    authorized = (
        recovered_service.authorize(
            continuation_credential=(
                issued.continuation_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    hours=1
                )
            ),
        )
    )

    assert (
        authorized.customer_id
        == CUSTOMER_ID
    )


def test_issuance_repr_redacts_plaintext(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    issued = _issue(
        service
    )

    rendered = repr(
        issued
    )

    assert (
        issued.continuation_credential
        not in rendered
    )

    assert (
        "continuation_credential=<redacted>"
        in rendered
    )


def test_issuance_request_identity_is_deterministic() -> None:
    first = (
        derive_customer_setup_build_continuation_issuance_request_id(
            setup_activation_id=(
                SETUP_ACTIVATION_ID
            ),
            deployment_id=(
                DEPLOYMENT_ID
            ),
        )
    )

    second = (
        derive_customer_setup_build_continuation_issuance_request_id(
            setup_activation_id=(
                SETUP_ACTIVATION_ID
            ),
            deployment_id=(
                DEPLOYMENT_ID
            ),
        )
    )

    assert first == second

    assert first.startswith(
        "setup-build-continuation-"
    )


def test_naive_current_time_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, _, service = (
        _environment(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        _issue(
            service,
            current_time=(
                datetime(
                    2026,
                    9,
                    1,
                    4,
                    41,
                    53,
                )
            ),
        )


def test_store_rejects_multiple_active_continuations_for_one_activation(
    tmp_path: Path,
) -> None:
    store, _, _, _ = (
        _environment(
            tmp_path
        )
    )

    first = (
        CustomerSetupBuildContinuationRecord(
            issuance_request_id="request-1",
            continuation_id="1" * 32,
            setup_activation_id=(
                SETUP_ACTIVATION_ID
            ),
            deployment_id=DEPLOYMENT_ID,
            account_fingerprint_sha256=(
                "a" * 64
            ),
            verifier_sha256="b" * 64,
            issued_at=(
                "2026-09-01T04:00:00.000000Z"
            ),
            expires_at=(
                "2026-09-02T04:00:00.000000Z"
            ),
            status=(
                CustomerSetupBuildContinuationStatus.ACTIVE
            ),
        )
    )

    second = (
        CustomerSetupBuildContinuationRecord(
            issuance_request_id="request-2",
            continuation_id="2" * 32,
            setup_activation_id=(
                SETUP_ACTIVATION_ID
            ),
            deployment_id=DEPLOYMENT_ID,
            account_fingerprint_sha256=(
                "c" * 64
            ),
            verifier_sha256="d" * 64,
            issued_at=(
                "2026-09-01T04:00:00.000000Z"
            ),
            expires_at=(
                "2026-09-02T04:00:00.000000Z"
            ),
            status=(
                CustomerSetupBuildContinuationStatus.ACTIVE
            ),
        )
    )

    store.add(
        first
    )

    with pytest.raises(
        ValueError,
        match="already has an ACTIVE",
    ):
        store.add(
            second
        )


def test_persisted_schema_contains_only_expected_fields(
    tmp_path: Path,
) -> None:
    store, _, _, service = (
        _environment(
            tmp_path
        )
    )

    _issue(
        service
    )

    payload = json.loads(
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert set(
        payload
    ) == {
        "version",
        "records",
    }

    assert len(
        payload[
            "records"
        ]
    ) == 1

    assert set(
        payload[
            "records"
        ][0]
    ) == {
        "issuance_request_id",
        "continuation_id",
        "setup_activation_id",
        "deployment_id",
        "account_fingerprint_sha256",
        "verifier_sha256",
        "issued_at",
        "expires_at",
        "status",
    }
