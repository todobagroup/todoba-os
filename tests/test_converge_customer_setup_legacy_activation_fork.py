import importlib
import inspect

import pytest


def test_operator_legacy_fork_convergence_has_narrow_authority_surface():
    module = importlib.import_module(
        "scripts.converge_customer_setup_legacy_activation_fork"
    )

    owner = getattr(
        module,
        "converge_customer_setup_legacy_activation_fork",
    )

    signature = inspect.signature(
        owner
    )

    assert tuple(
        signature.parameters
    ) == (
        "control_plane_root",
        "activation_code",
        "confirm_runtime_stopped",
    )


def test_operator_requires_runtime_stop_before_state_access(
    tmp_path,
    monkeypatch,
):
    module = importlib.import_module(
        "scripts.converge_customer_setup_legacy_activation_fork"
    )

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
        module.converge_customer_setup_legacy_activation_fork(
            control_plane_root=tmp_path,
            activation_code="tdbsa.test.code",
            confirm_runtime_stopped=False,
        )


def test_operator_proves_unique_bound_legacy_lineage_before_transfer(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    from backend.commercial.customer_setup_activation_service import (
        CustomerSetupActivationStatus,
    )
    from backend.commercial.customer_setup_bootstrap_launch_grant_service import (
        derive_customer_setup_bootstrap_launch_issuance_request_id,
    )

    module = importlib.import_module(
        "scripts.converge_customer_setup_legacy_activation_fork"
    )

    activation_code = "tdbsa.test.activation-code"
    customer_id = "customer-001"
    authoritative_id = "setup-activation-authoritative"
    legacy_bound_id = "setup-activation-legacy-bound"
    legacy_unbound_id = "setup-activation-legacy-unbound"
    deployment_id = "deployment-001"

    def request_id(challenge):
        return (
            module.CustomerSetupAccessCodeExchangeService
            ._derive_authorization_request_id(
                activation_code=activation_code,
                code_challenge_s256=challenge,
            )
        )

    auth_bound = SimpleNamespace(
        authorization_request_id=request_id("challenge-bound"),
        authorization_id="authorization-bound",
        customer_id=customer_id,
        code_challenge_s256="challenge-bound",
        setup_activation_id=None,
    )

    auth_unbound = SimpleNamespace(
        authorization_request_id=request_id("challenge-unbound"),
        authorization_id="authorization-unbound",
        customer_id=customer_id,
        code_challenge_s256="challenge-unbound",
        setup_activation_id=None,
    )

    launch_bound = SimpleNamespace(
        issuance_request_id=(
            derive_customer_setup_bootstrap_launch_issuance_request_id(
                auth_bound.authorization_id
            )
        ),
        launch_id="launch-bound",
        customer_id=customer_id,
    )

    launch_unbound = SimpleNamespace(
        issuance_request_id=(
            derive_customer_setup_bootstrap_launch_issuance_request_id(
                auth_unbound.authorization_id
            )
        ),
        launch_id="launch-unbound",
        customer_id=customer_id,
    )

    authoritative = SimpleNamespace(
        activation_request_id="authoritative-request",
        setup_activation_id=authoritative_id,
        customer_id=customer_id,
        status=CustomerSetupActivationStatus.ACTIVE,
        deployment_id=None,
    )

    legacy_bound = SimpleNamespace(
        activation_request_id=launch_bound.launch_id,
        setup_activation_id=legacy_bound_id,
        customer_id=customer_id,
        status=CustomerSetupActivationStatus.BOUND,
        deployment_id=deployment_id,
    )

    legacy_unbound = SimpleNamespace(
        activation_request_id=launch_unbound.launch_id,
        setup_activation_id=legacy_unbound_id,
        customer_id=customer_id,
        status=CustomerSetupActivationStatus.ACTIVE,
        deployment_id=None,
    )

    deployment = SimpleNamespace(
        deployment_id=deployment_id,
        customer_id=customer_id,
        agent_id="trusted-agent-001",
    )

    deployment_bootstrap = SimpleNamespace(
        enrollment_request_id=legacy_bound_id,
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id="trusted-agent-001",
    )

    class Ready:
        def is_ready(self):
            return True

    class IdentityRegistry(Ready):
        def contains(self, *, customer_id):
            return customer_id == "customer-001"

    class DeploymentRegistry(Ready):
        def get(self, *, deployment_id):
            if deployment_id == "deployment-001":
                return deployment
            return None

    class ActivationStore(Ready):
        def __init__(self):
            self.transfer = None

        def get(self, *, setup_activation_id):
            if setup_activation_id == authoritative_id:
                return authoritative
            if setup_activation_id == legacy_bound_id:
                return legacy_bound
            if setup_activation_id == legacy_unbound_id:
                return legacy_unbound
            return None

        def get_by_activation_request_id(
            self,
            *,
            activation_request_id,
        ):
            if activation_request_id == "launch-bound":
                return legacy_bound
            if activation_request_id == "launch-unbound":
                return legacy_unbound
            return None

        def get_by_deployment_id(self, *, deployment_id):
            if deployment_id == "deployment-001":
                return legacy_bound
            return None

        def converge_legacy_fork(
            self,
            *,
            authoritative_setup_activation_id,
            superseded_setup_activation_id,
            deployment_id,
        ):
            self.transfer = (
                authoritative_setup_activation_id,
                superseded_setup_activation_id,
                deployment_id,
            )

            return SimpleNamespace(
                setup_activation_id=(
                    authoritative_setup_activation_id
                ),
                customer_id=customer_id,
                status=CustomerSetupActivationStatus.BOUND,
                deployment_id=deployment_id,
            )

    class AccessCodeStore(Ready):
        pass

    class BootstrapAuthorizationStore(Ready):
        def all(self):
            return (
                auth_bound,
                auth_unbound,
            )

    class LaunchStore(Ready):
        def get_by_issuance_request_id(
            self,
            *,
            issuance_request_id,
        ):
            if (
                issuance_request_id
                == launch_bound.issuance_request_id
            ):
                return launch_bound

            if (
                issuance_request_id
                == launch_unbound.issuance_request_id
            ):
                return launch_unbound

            return None

    class DeploymentBootstrapStore(Ready):
        def get(self, *, enrollment_request_id):
            if enrollment_request_id == legacy_bound_id:
                return deployment_bootstrap
            return None

    activation_store = ActivationStore()

    monkeypatch.setattr(
        module,
        "CustomerIdentityRegistry",
        lambda *args, **kwargs: IdentityRegistry(),
    )

    monkeypatch.setattr(
        module,
        "CustomerDeploymentRegistry",
        lambda *args, **kwargs: DeploymentRegistry(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupActivationStore",
        lambda *args, **kwargs: activation_store,
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupAccessCodeStore",
        lambda *args, **kwargs: AccessCodeStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupBootstrapAuthorizationStore",
        lambda *args, **kwargs: BootstrapAuthorizationStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupLaunchCredentialStore",
        lambda *args, **kwargs: LaunchStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerDeploymentBootstrapStore",
        lambda *args, **kwargs: DeploymentBootstrapStore(),
    )

    class AccessCodeService:
        def __init__(self, *args, **kwargs):
            pass

        def authorize(self, *, activation_code):
            assert activation_code == "tdbsa.test.activation-code"

            return SimpleNamespace(
                setup_activation_id=authoritative_id,
                customer_id=customer_id,
            )

    monkeypatch.setattr(
        module,
        "CustomerSetupAccessCodeService",
        AccessCodeService,
    )

    result = (
        module
        .converge_customer_setup_legacy_activation_fork(
            control_plane_root=tmp_path,
            activation_code=activation_code,
            confirm_runtime_stopped=True,
        )
    )

    assert activation_store.transfer == (
        authoritative_id,
        legacy_bound_id,
        deployment_id,
    )

    assert (
        result.authoritative_setup_activation_id
        == authoritative_id
    )

    assert (
        result.superseded_setup_activation_id
        == legacy_bound_id
    )

    assert result.deployment_id == deployment_id
    assert result.authorization_id == "authorization-bound"
    assert result.launch_id == "launch-bound"


def _install_fake_operator_state(
    *,
    monkeypatch,
    module,
    activation_code,
    authoritative,
    bootstrap_authorizations,
    launches,
    legacy_activations,
    deployments,
    deployment_bootstraps,
    owners,
    transfer_calls,
):
    from types import SimpleNamespace

    class Ready:
        def is_ready(self):
            return True

    class IdentityRegistry(Ready):
        def contains(self, *, customer_id):
            return (
                customer_id
                == authoritative.customer_id
            )

    class DeploymentRegistry(Ready):
        def get(self, *, deployment_id):
            return deployments.get(
                deployment_id
            )

    class ActivationStore(Ready):
        def get(self, *, setup_activation_id):
            if (
                setup_activation_id
                == authoritative.setup_activation_id
            ):
                return authoritative

            for activation in (
                legacy_activations.values()
            ):
                if (
                    activation.setup_activation_id
                    == setup_activation_id
                ):
                    return activation

            return None

        def get_by_activation_request_id(
            self,
            *,
            activation_request_id,
        ):
            return legacy_activations.get(
                activation_request_id
            )

        def get_by_deployment_id(
            self,
            *,
            deployment_id,
        ):
            return owners.get(
                deployment_id
            )

        def converge_legacy_fork(
            self,
            *,
            authoritative_setup_activation_id,
            superseded_setup_activation_id,
            deployment_id,
        ):
            transfer_calls.append(
                (
                    authoritative_setup_activation_id,
                    superseded_setup_activation_id,
                    deployment_id,
                )
            )

            return SimpleNamespace(
                setup_activation_id=(
                    authoritative_setup_activation_id
                ),
                customer_id=(
                    authoritative.customer_id
                ),
                status=(
                    module.CustomerSetupActivationStatus
                    .BOUND
                ),
                deployment_id=deployment_id,
            )

    class AccessCodeStore(Ready):
        pass

    class BootstrapAuthorizationStore(Ready):
        def all(self):
            return tuple(
                bootstrap_authorizations
            )

    class LaunchStore(Ready):
        def get_by_issuance_request_id(
            self,
            *,
            issuance_request_id,
        ):
            return launches.get(
                issuance_request_id
            )

    class DeploymentBootstrapStore(Ready):
        def get(
            self,
            *,
            enrollment_request_id,
        ):
            return deployment_bootstraps.get(
                enrollment_request_id
            )

    class AccessCodeService:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def authorize(
            self,
            *,
            activation_code,
        ):
            assert (
                activation_code
                == activation_code_value
            )

            return SimpleNamespace(
                setup_activation_id=(
                    authoritative
                    .setup_activation_id
                ),
                customer_id=(
                    authoritative.customer_id
                ),
            )

    activation_code_value = activation_code

    monkeypatch.setattr(
        module,
        "CustomerIdentityRegistry",
        lambda *args, **kwargs: IdentityRegistry(),
    )

    monkeypatch.setattr(
        module,
        "CustomerDeploymentRegistry",
        lambda *args, **kwargs: DeploymentRegistry(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupActivationStore",
        lambda *args, **kwargs: ActivationStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupAccessCodeStore",
        lambda *args, **kwargs: AccessCodeStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupBootstrapAuthorizationStore",
        lambda *args, **kwargs: BootstrapAuthorizationStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupLaunchCredentialStore",
        lambda *args, **kwargs: LaunchStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerDeploymentBootstrapStore",
        lambda *args, **kwargs: DeploymentBootstrapStore(),
    )

    monkeypatch.setattr(
        module,
        "CustomerSetupAccessCodeService",
        AccessCodeService,
    )


def _build_fake_legacy_lineage(
    *,
    module,
    activation_code,
    suffix,
    customer_id,
    deployment_id,
    agent_id,
    activation_status,
):
    from types import SimpleNamespace

    challenge = (
        f"legacy-challenge-{suffix}"
    )

    authorization_id = (
        f"authorization-{suffix}"
    )

    authorization_request_id = (
        module
        .CustomerSetupAccessCodeExchangeService
        ._derive_authorization_request_id(
            activation_code=activation_code,
            code_challenge_s256=challenge,
        )
    )

    authorization = SimpleNamespace(
        authorization_request_id=(
            authorization_request_id
        ),
        authorization_id=authorization_id,
        customer_id=customer_id,
        code_challenge_s256=challenge,
        setup_activation_id=None,
    )

    launch_request_id = (
        module
        .derive_customer_setup_bootstrap_launch_issuance_request_id(
            authorization_id
        )
    )

    launch = SimpleNamespace(
        issuance_request_id=(
            launch_request_id
        ),
        launch_id=f"launch-{suffix}",
        customer_id=customer_id,
    )

    activation = SimpleNamespace(
        activation_request_id=(
            launch.launch_id
        ),
        setup_activation_id=(
            f"setup-activation-{suffix}"
        ),
        customer_id=customer_id,
        status=activation_status,
        deployment_id=deployment_id,
    )

    deployment = SimpleNamespace(
        deployment_id=deployment_id,
        customer_id=customer_id,
        agent_id=agent_id,
    )

    bootstrap = SimpleNamespace(
        enrollment_request_id=(
            activation.setup_activation_id
        ),
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )

    return (
        authorization,
        launch,
        activation,
        deployment,
        bootstrap,
    )


def test_operator_ambiguous_lineage_fails_before_atomic_transfer(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    module = importlib.import_module(
        "scripts.converge_customer_setup_legacy_activation_fork"
    )

    activation_code = "tdbsa.test.ambiguous"

    authoritative = SimpleNamespace(
        activation_request_id="authoritative-request",
        setup_activation_id="setup-activation-authoritative",
        customer_id="customer-001",
        status=(
            module.CustomerSetupActivationStatus.ACTIVE
        ),
        deployment_id=None,
    )

    first = _build_fake_legacy_lineage(
        module=module,
        activation_code=activation_code,
        suffix="first",
        customer_id="customer-001",
        deployment_id="deployment-first",
        agent_id="trusted-agent-first",
        activation_status=(
            module.CustomerSetupActivationStatus.BOUND
        ),
    )

    second = _build_fake_legacy_lineage(
        module=module,
        activation_code=activation_code,
        suffix="second",
        customer_id="customer-001",
        deployment_id="deployment-second",
        agent_id="trusted-agent-second",
        activation_status=(
            module.CustomerSetupActivationStatus.BOUND
        ),
    )

    transfer_calls = []

    _install_fake_operator_state(
        monkeypatch=monkeypatch,
        module=module,
        activation_code=activation_code,
        authoritative=authoritative,
        bootstrap_authorizations=[
            first[0],
            second[0],
        ],
        launches={
            first[1].issuance_request_id: first[1],
            second[1].issuance_request_id: second[1],
        },
        legacy_activations={
            first[1].launch_id: first[2],
            second[1].launch_id: second[2],
        },
        deployments={
            first[3].deployment_id: first[3],
            second[3].deployment_id: second[3],
        },
        deployment_bootstraps={
            first[2].setup_activation_id: first[4],
            second[2].setup_activation_id: second[4],
        },
        owners={
            first[3].deployment_id: first[2],
            second[3].deployment_id: second[2],
        },
        transfer_calls=transfer_calls,
    )

    with pytest.raises(
        RuntimeError,
        match="lineage is ambiguous",
    ):
        module.converge_customer_setup_legacy_activation_fork(
            control_plane_root=tmp_path,
            activation_code=activation_code,
            confirm_runtime_stopped=True,
        )

    assert transfer_calls == []


def test_operator_cross_customer_deployment_fails_before_atomic_transfer(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    module = importlib.import_module(
        "scripts.converge_customer_setup_legacy_activation_fork"
    )

    activation_code = "tdbsa.test.cross-customer"

    authoritative = SimpleNamespace(
        activation_request_id="authoritative-request",
        setup_activation_id="setup-activation-authoritative",
        customer_id="customer-001",
        status=(
            module.CustomerSetupActivationStatus.ACTIVE
        ),
        deployment_id=None,
    )

    (
        authorization,
        launch,
        legacy,
        deployment,
        bootstrap,
    ) = _build_fake_legacy_lineage(
        module=module,
        activation_code=activation_code,
        suffix="cross",
        customer_id="customer-001",
        deployment_id="deployment-cross",
        agent_id="trusted-agent-cross",
        activation_status=(
            module.CustomerSetupActivationStatus.BOUND
        ),
    )

    deployment = SimpleNamespace(
        deployment_id=deployment.deployment_id,
        customer_id="customer-OTHER",
        agent_id=deployment.agent_id,
    )

    transfer_calls = []

    _install_fake_operator_state(
        monkeypatch=monkeypatch,
        module=module,
        activation_code=activation_code,
        authoritative=authoritative,
        bootstrap_authorizations=[
            authorization
        ],
        launches={
            launch.issuance_request_id: launch,
        },
        legacy_activations={
            launch.launch_id: legacy,
        },
        deployments={
            deployment.deployment_id: deployment,
        },
        deployment_bootstraps={
            legacy.setup_activation_id: bootstrap,
        },
        owners={
            deployment.deployment_id: legacy,
        },
        transfer_calls=transfer_calls,
    )

    with pytest.raises(
        RuntimeError,
        match="deployment customer identity did not converge",
    ):
        module.converge_customer_setup_legacy_activation_fork(
            control_plane_root=tmp_path,
            activation_code=activation_code,
            confirm_runtime_stopped=True,
        )

    assert transfer_calls == []


def test_operator_incomplete_lineage_does_not_mutate_activation_state(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    module = importlib.import_module(
        "scripts.converge_customer_setup_legacy_activation_fork"
    )

    activation_code = "tdbsa.test.incomplete"

    authoritative = SimpleNamespace(
        activation_request_id="authoritative-request",
        setup_activation_id="setup-activation-authoritative",
        customer_id="customer-001",
        status=(
            module.CustomerSetupActivationStatus.ACTIVE
        ),
        deployment_id=None,
    )

    challenge = "legacy-incomplete-challenge"

    authorization = SimpleNamespace(
        authorization_request_id=(
            module
            .CustomerSetupAccessCodeExchangeService
            ._derive_authorization_request_id(
                activation_code=activation_code,
                code_challenge_s256=challenge,
            )
        ),
        authorization_id="authorization-incomplete",
        customer_id="customer-001",
        code_challenge_s256=challenge,
        setup_activation_id=None,
    )

    transfer_calls = []

    _install_fake_operator_state(
        monkeypatch=monkeypatch,
        module=module,
        activation_code=activation_code,
        authoritative=authoritative,
        bootstrap_authorizations=[
            authorization
        ],
        launches={},
        legacy_activations={},
        deployments={},
        deployment_bootstraps={},
        owners={},
        transfer_calls=transfer_calls,
    )

    with pytest.raises(
        RuntimeError,
        match="No provable legacy Setup activation fork",
    ):
        module.converge_customer_setup_legacy_activation_fork(
            control_plane_root=tmp_path,
            activation_code=activation_code,
            confirm_runtime_stopped=True,
        )

    assert transfer_calls == []
