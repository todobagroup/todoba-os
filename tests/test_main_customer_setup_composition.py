"""
TODOBA Production Customer Setup Composition Tests

Production rule:
- importing backend.main must not require offline Setup state
- FastAPI lifespan startup owns Setup reopen/readiness
- missing durable Setup state fails startup closed
- no production initialize_empty()
- both Setup routers share one R3 handoff authorizer
"""

import ast
from pathlib import Path


MAIN_PATH = Path(
    "backend/main.py"
)

SOURCE = MAIN_PATH.read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE
)


def _function(
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in TREE.body
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        )
    ]

    assert len(matches) == 1

    return matches[0]


def _calls_named(
    tree: ast.AST,
    name: str,
) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id == name
        )
    ]


def _keyword(
    call: ast.Call,
    name: str,
) -> ast.expr:
    matches = [
        keyword.value
        for keyword in call.keywords
        if keyword.arg == name
    ]

    assert len(matches) == 1

    return matches[0]


def _is_name(
    node: ast.AST,
    name: str,
) -> bool:
    return (
        isinstance(
            node,
            ast.Name,
        )
        and node.id == name
    )


def _is_method(
    node: ast.AST,
    *,
    owner: str,
    method: str,
) -> bool:
    return (
        isinstance(
            node,
            ast.Attribute,
        )
        and node.attr == method
        and isinstance(
            node.value,
            ast.Name,
        )
        and node.value.id == owner
    )


def test_main_owns_authoritative_setup_storage_paths(
) -> None:
    expected = (
        (
            "CUSTOMER_SETUP_ACTIVATION_STORAGE_PATH",
            "customer_setup_activations.json",
        ),
        (
            "CUSTOMER_SETUP_HANDOFF_STORAGE_PATH",
            "customer_setup_handoffs.json",
        ),
        (
            "CUSTOMER_DEPLOYMENT_BOOTSTRAP_STORAGE_PATH",
            "customer_deployment_bootstraps.json",
        ),
        (
            "CUSTOMER_DEPLOYMENT_PACKAGE_BUILD_REQUEST_STORAGE_ROOT",
            "customer_deployment_package_build_requests",
        ),
    )

    for constant, leaf in expected:
        assert constant in SOURCE
        assert leaf in SOURCE


def test_setup_composition_is_owned_by_lifespan_startup(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    lifespan = _function(
        "lifespan"
    )

    compose_calls = _calls_named(
        lifespan,
        "_compose_customer_setup_runtime",
    )

    assert len(
        compose_calls
    ) == 1

    assert len(
        _calls_named(
            compose,
            "CustomerSetupActivationStore",
        )
    ) == 1

    assert len(
        _calls_named(
            compose,
            "CustomerSetupHandoffStore",
        )
    ) == 1

    assert len(
        _calls_named(
            compose,
            "CustomerDeploymentBootstrapStore",
        )
    ) == 1

    assert len(
        _calls_named(
            compose,
            "CustomerDeploymentPackageBuildRequestStore",
        )
    ) == 1


def test_setup_services_are_not_composed_at_module_import(
) -> None:
    forbidden_top_level_calls = {
        "CustomerSetupActivationService",
        "CustomerSetupHandoffService",
        "CustomerSetupHandoffAuthorizer",
        "CustomerDeploymentEnrollmentService",
        "CustomerDeploymentBootstrapService",
        "create_customer_setup_provisioning_router",
        "create_customer_setup_package_router",
    }

    for node in TREE.body:
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not isinstance(
            node.value,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.value.func,
            ast.Name,
        ):
            continue

        assert (
            node.value.func.id
            not in forbidden_top_level_calls
        )


def test_setup_startup_requires_all_durable_owners_ready(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    for owner_name in (
        "Customer setup activation store",
        "Customer setup handoff store",
        "Customer deployment bootstrap store",
        "Customer deployment package build request store",
    ):
        assert owner_name in compose_source

    assert ".is_ready()" in compose_source


def test_main_never_initializes_setup_durable_state(
) -> None:
    initialize_calls = [
        node
        for node in ast.walk(
            TREE
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "initialize_empty"
        )
    ]

    assert initialize_calls == []


def test_main_owns_no_package_build_execution(
) -> None:
    assert "MetaEditor" not in SOURCE
    assert "build_package(" not in SOURCE
    assert "subprocess.run(" not in SOURCE


def test_setup_services_compose_exactly_once_in_startup_owner(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    expected = (
        "CustomerSetupActivationService",
        "CustomerSetupHandoffService",
        "CustomerSetupHandoffAuthorizer",
        "CustomerDeploymentEnrollmentService",
        "CustomerDeploymentBootstrapService",
    )

    for name in expected:
        assert len(
            _calls_named(
                compose,
                name,
            )
        ) == 1


def test_setup_routes_compose_exactly_once_in_startup_owner(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    assert len(
        _calls_named(
            compose,
            "create_customer_setup_provisioning_router",
        )
    ) == 1

    assert len(
        _calls_named(
            compose,
            "create_customer_setup_package_router",
        )
    ) == 1


def test_setup_routes_share_one_r3_handoff_authorizer(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    provisioning = _calls_named(
        compose,
        "create_customer_setup_provisioning_router",
    )[0]

    package = _calls_named(
        compose,
        "create_customer_setup_package_router",
    )[0]

    assert _is_method(
        _keyword(
            provisioning,
            "authorize_setup_handoff",
        ),
        owner="handoff_authorizer",
        method="authorize",
    )

    assert _is_method(
        _keyword(
            package,
            "authorize_setup_handoff",
        ),
        owner="handoff_authorizer",
        method="authorize",
    )


def test_provisioning_router_reuses_authoritative_owners(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    call = _calls_named(
        compose,
        "create_customer_setup_provisioning_router",
    )[0]

    expected = {
        "bootstrap_service": (
            "bootstrap_service"
        ),
        "build_request_store": (
            "build_request_store"
        ),
        "package_publication": (
            "customer_deployment_package_publication"
        ),
        "entitlement_registry": (
            "customer_deployment_entitlement_registry"
        ),
        "setup_activation_service": (
            "activation_service"
        ),
    }

    for keyword_name, owner_name in (
        expected.items()
    ):
        assert _is_name(
            _keyword(
                call,
                keyword_name,
            ),
            owner_name,
        )


def test_setup_package_router_reuses_existing_authorizers(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    call = _calls_named(
        compose,
        "create_customer_setup_package_router",
    )[0]

    assert _is_method(
        _keyword(
            call,
            "authorize_deployment",
        ),
        owner="customer_deployment_authorizer",
        method="authorize",
    )

    assert _is_method(
        _keyword(
            call,
            "authorize_entitlement",
        ),
        owner=(
            "customer_deployment_entitlement_authorizer"
        ),
        method="authorize",
    )

    assert _is_name(
        _keyword(
            call,
            "package_publication",
        ),
        "customer_deployment_package_publication",
    )


def test_setup_composition_is_idempotent_across_lifespan_reentry(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    assert (
        "if _customer_setup_runtime_composed:"
        in compose_source
    )

    assert (
        "_customer_setup_runtime_composed = True"
        in compose_source
    )


def test_setup_dependency_order_is_safe(
) -> None:
    compose = _function(
        "_compose_customer_setup_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    assert compose_source.index(
        "activation_service = ("
    ) < compose_source.index(
        "handoff_service = ("
    )

    assert compose_source.index(
        "handoff_service = ("
    ) < compose_source.index(
        "handoff_authorizer = ("
    )

    assert compose_source.index(
        "enrollment_service = ("
    ) < compose_source.index(
        "bootstrap_service = ("
    )
