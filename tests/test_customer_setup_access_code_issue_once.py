import threading
from types import SimpleNamespace

import pytest

from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeService,
)


class _AccessCodeStore:
    def __init__(self, *, existing=None):
        self.existing = existing
        self.lookup_calls = []
        self.revoke_calls = []

    def get_active_by_setup_activation_id(
        self,
        *,
        setup_activation_id,
    ):
        self.lookup_calls.append(
            setup_activation_id
        )
        return self.existing

    def revoke(
        self,
        *,
        access_code_id,
    ):
        self.revoke_calls.append(
            access_code_id
        )


def _build_service(*, existing=None):
    service = object.__new__(
        CustomerSetupAccessCodeService
    )

    store = _AccessCodeStore(
        existing=existing
    )

    activation = SimpleNamespace(
        setup_activation_id=(
            "setup-activation-paid-001"
        ),
        customer_id="customer-paid-001",
    )

    issue_calls = []

    service._lock = threading.RLock()
    service._access_code_store = store
    service._setup_activation_store = object()

    service._require_active_activation = (
        lambda setup_activation_id: (
            activation
            if setup_activation_id
            == activation.setup_activation_id
            else (_ for _ in ()).throw(
                ValueError(
                    "Unknown ACTIVE Setup Activation."
                )
            )
        )
    )

    def record_issue(
        *,
        setup_activation_id,
    ):
        issue_calls.append(
            setup_activation_id
        )
        return SimpleNamespace(
            setup_activation_id=(
                setup_activation_id
            ),
        )

    service.issue = record_issue

    return (
        service,
        store,
        activation,
        issue_calls,
    )


def test_issue_once_delegates_only_when_no_active_code_exists():
    (
        service,
        store,
        activation,
        issue_calls,
    ) = _build_service()

    result = service.issue_once(
        setup_activation_id=(
            activation.setup_activation_id
        )
    )

    assert store.lookup_calls == [
        activation.setup_activation_id
    ]
    assert store.revoke_calls == []

    assert issue_calls == [
        activation.setup_activation_id
    ]

    assert (
        result.setup_activation_id
        == activation.setup_activation_id
    )


def test_issue_once_replay_fails_without_rotation():
    existing = SimpleNamespace(
        access_code_id="existing-code-001",
        setup_activation_id=(
            "setup-activation-paid-001"
        ),
    )

    (
        service,
        store,
        activation,
        issue_calls,
    ) = _build_service(
        existing=existing
    )

    with pytest.raises(
        RuntimeError,
        match="refusing replay rotation",
    ):
        service.issue_once(
            setup_activation_id=(
                activation.setup_activation_id
            )
        )

    assert store.lookup_calls == [
        activation.setup_activation_id
    ]

    assert store.revoke_calls == []
    assert issue_calls == []
