import hashlib
import inspect
import threading
from types import SimpleNamespace

from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeService,
    CustomerSetupAccessCodeStatus,
)


class _FakeAccessCodeStore:
    def __init__(self):
        self.active = SimpleNamespace(
            access_code_id="old-code-id",
            setup_activation_id="setup-activation-001",
            status=CustomerSetupAccessCodeStatus.ACTIVE,
        )
        self.revoked = []
        self.registered = []

    def get_active_by_setup_activation_id(
        self,
        *,
        setup_activation_id,
    ):
        if (
            self.active is not None
            and self.active.setup_activation_id
            == setup_activation_id
        ):
            return self.active
        return None

    def revoke(
        self,
        *,
        access_code_id,
    ):
        self.revoked.append(access_code_id)
        self.active = None

    def get(
        self,
        *,
        access_code_id,
    ):
        return None

    def register(
        self,
        record,
    ):
        self.registered.append(record)
        self.active = record
        return record


def _build_service():
    service = object.__new__(
        CustomerSetupAccessCodeService
    )
    store = _FakeAccessCodeStore()

    service._access_code_store = store
    service._setup_activation_store = object()
    service._lock = threading.RLock()

    activation = SimpleNamespace(
        setup_activation_id="setup-activation-001",
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    service._require_bound_activation = (
        lambda setup_activation_id: activation
        if setup_activation_id
        == activation.setup_activation_id
        else (_ for _ in ()).throw(
            ValueError("Unknown bound activation.")
        )
    )

    return service, store, activation


def test_reissue_bound_has_narrow_authority_surface():
    parameters = inspect.signature(
        CustomerSetupAccessCodeService.reissue_bound
    ).parameters

    assert tuple(parameters) == (
        "self",
        "setup_activation_id",
    )


def test_reissue_bound_rotates_code_without_identity_change():
    service, store, activation = _build_service()

    issued = service.reissue_bound(
        setup_activation_id=(
            activation.setup_activation_id
        )
    )

    assert store.revoked == ["old-code-id"]
    assert len(store.registered) == 1

    persisted = store.registered[0]

    assert (
        issued.setup_activation_id
        == activation.setup_activation_id
    )
    assert issued.customer_id == activation.customer_id

    assert (
        persisted.setup_activation_id
        == activation.setup_activation_id
    )
    assert (
        persisted.status
        is CustomerSetupAccessCodeStatus.ACTIVE
    )

    assert (
        persisted.code_sha256
        == hashlib.sha256(
            issued.activation_code.encode("utf-8")
        ).hexdigest()
    )

    assert issued.access_code_id != "old-code-id"
    assert "old-code-id" not in issued.activation_code


def test_reissue_bound_propagates_bound_authority_rejection():
    service, store, _ = _build_service()

    try:
        service.reissue_bound(
            setup_activation_id="wrong-activation"
        )
    except ValueError as exc:
        assert "bound activation" in str(exc)
    else:
        raise AssertionError(
            "BOUND authority rejection was bypassed."
        )

    assert store.revoked == []
    assert store.registered == []
