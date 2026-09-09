import importlib
import inspect

import pytest


MODULE = (
    "scripts."
    "converge_customer_setup_legacy_activation_fork_by_setup_activation_id"
)


def test_durable_identity_recovery_has_narrow_authority_surface():
    module = importlib.import_module(MODULE)

    owner = getattr(
        module,
        "converge_customer_setup_legacy_activation_fork_by_setup_activation_id",
    )

    assert tuple(inspect.signature(owner).parameters) == (
        "control_plane_root",
        "setup_activation_id",
        "confirm_runtime_stopped",
    )


def test_durable_identity_recovery_requires_runtime_stop_before_state_access(
    tmp_path,
    monkeypatch,
):
    module = importlib.import_module(MODULE)

    def forbidden_state_open(*args, **kwargs):
        raise AssertionError(
            "state must not be opened before runtime-stop gate"
        )

    monkeypatch.setattr(
        module,
        "CustomerIdentityRegistry",
        forbidden_state_open,
    )

    with pytest.raises(
        RuntimeError,
        match="runtime must be confirmed stopped",
    ):
        module.converge_customer_setup_legacy_activation_fork_by_setup_activation_id(
            control_plane_root=tmp_path,
            setup_activation_id="setup-activation-authoritative",
            confirm_runtime_stopped=False,
        )


def test_durable_identity_recovery_rejects_non_normalized_identity(
    tmp_path,
):
    module = importlib.import_module(MODULE)

    with pytest.raises(
        ValueError,
        match="must be normalized",
    ):
        module.converge_customer_setup_legacy_activation_fork_by_setup_activation_id(
            control_plane_root=tmp_path,
            setup_activation_id=" setup-activation-authoritative ",
            confirm_runtime_stopped=True,
        )
