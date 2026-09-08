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
