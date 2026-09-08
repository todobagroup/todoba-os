import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")


def _source() -> str:
    return MAIN_PATH.read_text(
        encoding="utf-8"
    )


def _commercial_imports() -> set[tuple[str, str]]:
    tree = ast.parse(_source())

    imports: set[tuple[str, str]] = set()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith(
                "backend.commercial."
            )
        ):
            for alias in node.names:
                imports.add(
                    (
                        node.module,
                        alias.name,
                    )
                )

    return imports


def test_backend_main_imports_vps_connect_production_owners(
) -> None:
    imports = _commercial_imports()

    expected = {
        (
            "backend.commercial."
            "customer_vps_connect_deployment_resolver",
            "CustomerVPSConnectDeploymentResolver",
        ),
        (
            "backend.commercial."
            "customer_vps_connect_grant_service",
            "CustomerVPSConnectGrantStore",
        ),
        (
            "backend.commercial."
            "customer_vps_connect_grant_service",
            "CustomerVPSConnectGrantService",
        ),
        (
            "backend.commercial."
            "customer_vps_connect_grant_composition_service",
            "CustomerVPSConnectGrantCompositionService",
        ),
        (
            "backend.commercial."
            "customer_vps_connect_grant_api",
            "create_customer_vps_connect_grant_router",
        ),
    }

    assert expected <= imports


def test_backend_main_owns_vps_connect_grant_storage_path(
) -> None:
    source = _source()

    assert (
        "CUSTOMER_VPS_CONNECT_GRANT_STORAGE_PATH"
        in source
    )

    assert (
        "customer_vps_connect_grants.json"
        in source
    )


def test_runtime_opens_preprovisioned_grant_store_only(
) -> None:
    source = _source()

    assert (
        "CustomerVPSConnectGrantStore("
        in source
    )

    assert (
        "vps_connect_grant_store.open_existing()"
        in source
    )

    assert (
        "vps_connect_grant_store.initialize_empty()"
        not in source
    )


def test_runtime_composes_only_existing_server_authorities(
) -> None:
    source = _source()

    required = (
        "CustomerVPSConnectDeploymentResolver(",
        "deployment_registry=(",
        "customer_deployment_registry",
        "account_binding_store=(",
        "trusted_agent_account_binding_store",
        "CustomerVPSConnectGrantService(",
        "grant_store=(",
        "vps_connect_grant_store",
        "CustomerVPSConnectGrantCompositionService(",
        "authorize_bound_access_code=(",
        "access_code_service.authorize_bound",
        "resolve_deployment=(",
        "vps_connect_deployment_resolver.resolve",
        "issue_grant=(",
        "vps_connect_grant_service.issue",
    )

    for fragment in required:
        assert fragment in source


def test_runtime_includes_vps_connect_grant_router_once(
) -> None:
    source = _source()

    assert (
        source.count(
            "create_customer_vps_connect_grant_router("
        )
        == 1
    )

    assert (
        "issue_vps_connect_grant=("
        in source
    )

    assert (
        "vps_connect_grant_composition_service.issue"
        in source
    )

    assert (
        source.count(
            "app.include_router(\n"
            "        vps_connect_grant_router\n"
            "    )"
        )
        == 1
    )

import ast as _c5d_ast


def _c5d_find_assignment_call(
    *,
    target_name: str,
    callee_name: str,
):
    tree = _c5d_ast.parse(
        _source()
    )

    matches = []

    for node in _c5d_ast.walk(tree):
        if not isinstance(
            node,
            _c5d_ast.Assign,
        ):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not isinstance(
            target,
            _c5d_ast.Name,
        ):
            continue

        if target.id != target_name:
            continue

        if not isinstance(
            node.value,
            _c5d_ast.Call,
        ):
            continue

        func = node.value.func

        if (
            isinstance(
                func,
                _c5d_ast.Name,
            )
            and func.id == callee_name
        ):
            matches.append(
                node.value
            )

    assert len(matches) == 1

    return matches[0]


def test_live_proof_production_imports_required_owners():
    source = _source()

    assert (
        "customer_vps_connect_live_proof_service import"
        in source
    )
    assert (
        "CustomerVPSConnectLiveProofService"
        in source
    )

    assert (
        "customer_vps_connect_live_proof_api import"
        in source
    )
    assert (
        "create_customer_vps_connect_live_proof_router"
        in source
    )


def test_live_proof_production_uses_shared_grant_and_broker_state():
    source = _source()

    service_call = _c5d_find_assignment_call(
        target_name="vps_connect_live_proof_service",
        callee_name="CustomerVPSConnectLiveProofService",
    )

    kwargs = {
        keyword.arg: keyword.value
        for keyword in service_call.keywords
    }

    assert set(kwargs) == {
        "grant_service",
        "broker_state_store",
    }

    assert isinstance(
        kwargs["grant_service"],
        _c5d_ast.Name,
    )
    assert (
        kwargs["grant_service"].id
        == "vps_connect_grant_service"
    )

    assert isinstance(
        kwargs["broker_state_store"],
        _c5d_ast.Name,
    )
    assert (
        kwargs["broker_state_store"].id
        == "broker_state_store"
    )

    # These owners live in different lexical scopes:
    # the grant service is composed inside
    # _compose_customer_setup_runtime, while
    # broker_state_store is the shared module-level owner.
    # Cross-scope textual source order is not an invariant.
    assert source.count(
        "CustomerVPSConnectGrantService("
    ) == 1

    assert source.count(
        "BrokerStateStore()"
    ) == 1


def test_live_proof_production_router_uses_service_verify_only():
    router_call = _c5d_find_assignment_call(
        target_name="vps_connect_live_proof_router",
        callee_name="create_customer_vps_connect_live_proof_router",
    )

    kwargs = {
        keyword.arg: keyword.value
        for keyword in router_call.keywords
    }

    assert set(kwargs) == {
        "verify_vps_connect_live_proof",
    }

    verify = kwargs[
        "verify_vps_connect_live_proof"
    ]

    assert isinstance(
        verify,
        _c5d_ast.Attribute,
    )

    assert verify.attr == "verify"

    assert isinstance(
        verify.value,
        _c5d_ast.Name,
    )

    assert (
        verify.value.id
        == "vps_connect_live_proof_service"
    )


def test_live_proof_production_includes_router_once_without_parallel_state():
    source = _source()
    tree = _c5d_ast.parse(
        source
    )

    live_proof_include_count = 0

    for node in _c5d_ast.walk(tree):
        if not isinstance(
            node,
            _c5d_ast.Call,
        ):
            continue

        func = node.func

        if not (
            isinstance(
                func,
                _c5d_ast.Attribute,
            )
            and func.attr == "include_router"
        ):
            continue

        if len(node.args) != 1:
            continue

        argument = node.args[0]

        if (
            isinstance(
                argument,
                _c5d_ast.Name,
            )
            and argument.id
            == "vps_connect_live_proof_router"
        ):
            live_proof_include_count += 1

    assert live_proof_include_count == 1

    assert source.count(
        "BrokerStateStore()"
    ) == 1

    assert source.count(
        "CustomerVPSConnectGrantService("
    ) == 1

    assert source.count(
        "CustomerVPSConnectLiveProofService("
    ) == 1

    assert source.count(
        "create_customer_vps_connect_live_proof_router("
    ) == 1

    assert (
        "CustomerVPSConnectGrantStore("
        in source
    )

    assert (
        "vps_connect_grant_store.initialize_empty()"
        not in source
    )
