from __future__ import annotations

import ast
from pathlib import Path


MAIN_PATH = (
    Path(__file__)
    .resolve()
    .parents[1]
    / "backend"
    / "main.py"
)

SOURCE = MAIN_PATH.read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE
)


def _function(
    name: str,
) -> ast.FunctionDef:
    for node in TREE.body:
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"Missing function: {name}"
    )


def _async_function(
    name: str,
) -> ast.AsyncFunctionDef:
    for node in TREE.body:
        if (
            isinstance(
                node,
                ast.AsyncFunctionDef,
            )
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"Missing async function: {name}"
    )


def _calls_named(
    owner: ast.AST,
    name: str,
) -> list[ast.Call]:
    calls: list[ast.Call] = []

    for node in ast.walk(
        owner
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id == name
        ):
            calls.append(
                node
            )

    return calls


def test_payment_runtime_has_dedicated_lifespan_owner(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )
    lifespan = _async_function(
        "lifespan"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )
    lifespan_source = ast.get_source_segment(
        SOURCE,
        lifespan,
    )

    assert compose_source is not None
    assert lifespan_source is not None

    assert lifespan_source.count(
        "_compose_customer_payment_runtime("
    ) == 1

    assert lifespan_source.index(
        "_compose_customer_setup_runtime("
    ) < lifespan_source.index(
        "_compose_customer_payment_runtime("
    )


def test_payment_runtime_owns_exact_six_durable_stores(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    expected = {
        "CustomerCommercialOrderStore",
        "CustomerPaymentIntentStore",
        "CustomerPaymentEvidenceStore",
        "CustomerPaymentSettlementStore",
        "CustomerPayPalOrderBindingStore",
        "CustomerVndBankReconciliationStore",
    }

    actual = {
        name
        for name in expected
        if len(
            _calls_named(
                compose,
                name,
            )
        ) == 1
    }

    assert actual == expected


def test_payment_runtime_uses_p7b0_storage_files(
) -> None:
    required = (
        "customer_commercial_orders.json",
        "customer_payment_intents.json",
        "customer_payment_evidence.json",
        "customer_payment_settlements.json",
        "customer_paypal_order_bindings.json",
        "customer_vnd_bank_reconciliations.json",
    )

    for filename in required:
        assert filename in SOURCE


def test_payment_runtime_fails_closed_before_restore(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    required_paths = {
        "CUSTOMER_COMMERCIAL_ORDER_STORAGE_PATH",
        "CUSTOMER_PAYMENT_INTENT_STORAGE_PATH",
        "CUSTOMER_PAYMENT_EVIDENCE_STORAGE_PATH",
        "CUSTOMER_PAYMENT_SETTLEMENT_STORAGE_PATH",
        "CUSTOMER_PAYPAL_ORDER_BINDING_STORAGE_PATH",
        "CUSTOMER_VND_BANK_RECONCILIATION_STORAGE_PATH",
    }

    for path_name in required_paths:
        assert path_name in compose_source

    calls = [
        node
        for node in ast.walk(
            compose
        )
        if isinstance(
            node,
            ast.Call,
        )
    ]

    is_file_calls = [
        node
        for node in calls
        if (
            isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr == "is_file"
        )
    ]

    assert len(is_file_calls) == 1

    store_names = {
        "CustomerCommercialOrderStore",
        "CustomerPaymentIntentStore",
        "CustomerPaymentEvidenceStore",
        "CustomerPaymentSettlementStore",
        "CustomerPayPalOrderBindingStore",
        "CustomerVndBankReconciliationStore",
    }

    store_constructors = [
        node
        for node in calls
        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id in store_names
        )
    ]

    assert len(store_constructors) == 6

    first_constructor_line = min(
        node.lineno
        for node in store_constructors
    )

    assert all(
        node.lineno < first_constructor_line
        for node in is_file_calls
    )

    assert "initialize_empty(" not in compose_source

    assert (
        compose_source.count(
            ".open_existing()"
        )
        == 6
    )


def test_payment_runtime_never_provisions_vnd_store(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    assert (
        "vnd_bank_reconciliation_store.initialize_empty()"
        not in compose_source
    )


def test_payment_runtime_requires_all_six_stores_ready(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    required_labels = (
        "Customer commercial order store",
        "Customer payment intent store",
        "Customer payment evidence store",
        "Customer payment settlement store",
        "Customer PayPal order binding store",
        "Customer VND bank reconciliation store",
    )

    for label in required_labels:
        assert (
            f'"{label}"'
            in compose_source
        )


def test_payment_runtime_exports_authoritative_store_owners(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    expected = (
        "customer_commercial_order_store",
        "customer_payment_intent_store",
        "customer_payment_evidence_store",
        "customer_payment_settlement_store",
        "customer_paypal_order_binding_store",
        "customer_vnd_bank_reconciliation_store",
    )

    for name in expected:
        assert (
            f"global {name}"
            in compose_source
        )

        assert (
            f"{name} = ("
            in compose_source
            or
            f"{name} = "
            in compose_source
        )


def test_payment_runtime_has_no_provider_or_business_action_authority(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    forbidden = (
        "create_customer_payment",
        "include_router(",
        ".settle(",
        ".activate(",
        ".confirm(",
        ".capture(",
        "paypal_client",
        "webhook",
        "operator_id",
    )

    for token in forbidden:
        assert token not in compose_source


def _payment_compose_function_for_exec(
):
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    module = ast.Module(
        body=[
            compose,
        ],
        type_ignores=[],
    )

    ast.fix_missing_locations(
        module
    )

    class _CompositionOwner:
        def __init__(
            self,
            **kwargs,
        ) -> None:
            self.kwargs = kwargs

    namespace = {
        "FastAPI": object,
        "CustomerPaymentSettlementService": (
            _CompositionOwner
        ),
        "CustomerPaymentSettlementActivationBridge": (
            _CompositionOwner
        ),
        "CustomerPaymentSettlementOrchestrationService": (
            _CompositionOwner
        ),
        "customer_setup_activation_service": object(),
    }

    exec(
        compile(
            module,
            filename="<payment-compose-test>",
            mode="exec",
        ),
        namespace,
    )

    return (
        namespace[
            "_compose_customer_payment_runtime"
        ],
        namespace,
    )


def test_payment_runtime_missing_any_durable_file_fails_before_store_construction(
    tmp_path: Path,
) -> None:
    class _ExplodingStore:
        def __init__(
            self,
            *args,
            **kwargs,
        ) -> None:
            raise AssertionError(
                "Store construction must not occur "
                "before every payment durable file exists."
            )

    path_names = (
        "CUSTOMER_COMMERCIAL_ORDER_STORAGE_PATH",
        "CUSTOMER_PAYMENT_INTENT_STORAGE_PATH",
        "CUSTOMER_PAYMENT_EVIDENCE_STORAGE_PATH",
        "CUSTOMER_PAYMENT_SETTLEMENT_STORAGE_PATH",
        "CUSTOMER_PAYPAL_ORDER_BINDING_STORAGE_PATH",
        "CUSTOMER_VND_BANK_RECONCILIATION_STORAGE_PATH",
    )

    store_names = (
        "CustomerCommercialOrderStore",
        "CustomerPaymentIntentStore",
        "CustomerPaymentEvidenceStore",
        "CustomerPaymentSettlementStore",
        "CustomerPayPalOrderBindingStore",
        "CustomerVndBankReconciliationStore",
    )

    for missing_index, missing_name in enumerate(
        path_names
    ):
        compose, namespace = (
            _payment_compose_function_for_exec()
        )

        for index, path_name in enumerate(
            path_names
        ):
            storage_path = (
                tmp_path
                / f"{missing_index}-{index}.json"
            )

            if path_name != missing_name:
                storage_path.write_text(
                    "{}",
                    encoding="utf-8",
                )

            namespace[path_name] = (
                storage_path
            )

        for store_name in store_names:
            namespace[store_name] = (
                _ExplodingStore
            )

        namespace[
            "_customer_payment_runtime_composed"
        ] = False

        try:
            compose(
                object()
            )
        except RuntimeError as exc:
            assert (
                "is not provisioned."
                in str(exc)
            )
        else:
            raise AssertionError(
                f"Missing {missing_name} "
                "did not fail closed."
            )

        assert (
            namespace[
                "_customer_payment_runtime_composed"
            ]
            is False
        )


def test_payment_runtime_restores_existing_state_without_mutation(
    tmp_path: Path,
) -> None:
    from backend.commercial.customer_commercial_order_service import (
        CustomerCommercialOrderRecord,
        CustomerCommercialOrderStatus,
        CustomerCommercialOrderStore,
    )
    from backend.commercial.customer_payment_evidence_service import (
        CustomerPaymentEvidenceStore,
    )
    from backend.commercial.customer_payment_intent_service import (
        CustomerPaymentIntentStore,
    )
    from backend.commercial.customer_payment_settlement_service import (
        CustomerPaymentSettlementStore,
    )
    from backend.commercial.customer_paypal_order_binding_service import (
        CustomerPayPalOrderBindingStore,
    )
    from backend.commercial.customer_vnd_bank_reconciliation_service import (
        CustomerVndBankReconciliationStore,
    )

    commercial_order_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )
    payment_intent_path = (
        tmp_path
        / "customer_payment_intents.json"
    )
    payment_evidence_path = (
        tmp_path
        / "customer_payment_evidence.json"
    )
    payment_settlement_path = (
        tmp_path
        / "customer_payment_settlements.json"
    )
    paypal_binding_path = (
        tmp_path
        / "customer_paypal_order_bindings.json"
    )
    vnd_reconciliation_path = (
        tmp_path
        / "customer_vnd_bank_reconciliations.json"
    )

    order_store = (
        CustomerCommercialOrderStore(
            commercial_order_path
        )
    )
    order_store.initialize_empty()

    order = CustomerCommercialOrderRecord(
        order_request_id=(
            "p7b1-order-request-001"
        ),
        order_id="p7b1-order-001",
        customer_id="customer-001",
        amount_minor=2500,
        currency="USD",
        status=(
            CustomerCommercialOrderStatus.PENDING
        ),
    )

    order_store.register(
        order
    )

    payment_intent_store = (
        CustomerPaymentIntentStore(
            payment_intent_path
        )
    )
    payment_intent_store.initialize_empty()

    payment_evidence_store = (
        CustomerPaymentEvidenceStore(
            payment_evidence_path
        )
    )
    payment_evidence_store.initialize_empty()

    payment_settlement_store = (
        CustomerPaymentSettlementStore(
            payment_settlement_path
        )
    )
    payment_settlement_store.initialize_empty()

    paypal_binding_store = (
        CustomerPayPalOrderBindingStore(
            paypal_binding_path
        )
    )
    paypal_binding_store.initialize_empty()

    vnd_reconciliation_store = (
        CustomerVndBankReconciliationStore(
            vnd_reconciliation_path
        )
    )
    vnd_reconciliation_store.initialize_empty()

    paths = {
        "CUSTOMER_COMMERCIAL_ORDER_STORAGE_PATH": (
            commercial_order_path
        ),
        "CUSTOMER_PAYMENT_INTENT_STORAGE_PATH": (
            payment_intent_path
        ),
        "CUSTOMER_PAYMENT_EVIDENCE_STORAGE_PATH": (
            payment_evidence_path
        ),
        "CUSTOMER_PAYMENT_SETTLEMENT_STORAGE_PATH": (
            payment_settlement_path
        ),
        "CUSTOMER_PAYPAL_ORDER_BINDING_STORAGE_PATH": (
            paypal_binding_path
        ),
        "CUSTOMER_VND_BANK_RECONCILIATION_STORAGE_PATH": (
            vnd_reconciliation_path
        ),
    }

    before = {
        name: storage_path.read_bytes()
        for name, storage_path in paths.items()
    }

    compose, namespace = (
        _payment_compose_function_for_exec()
    )

    namespace.update(
        paths
    )

    namespace.update(
        {
            "CustomerCommercialOrderStore": (
                CustomerCommercialOrderStore
            ),
            "CustomerPaymentIntentStore": (
                CustomerPaymentIntentStore
            ),
            "CustomerPaymentEvidenceStore": (
                CustomerPaymentEvidenceStore
            ),
            "CustomerPaymentSettlementStore": (
                CustomerPaymentSettlementStore
            ),
            "CustomerPayPalOrderBindingStore": (
                CustomerPayPalOrderBindingStore
            ),
            "CustomerVndBankReconciliationStore": (
                CustomerVndBankReconciliationStore
            ),
            "_customer_payment_runtime_composed": False,
        }
    )

    compose(
        object()
    )

    after = {
        name: storage_path.read_bytes()
        for name, storage_path in paths.items()
    }

    assert after == before

    assert (
        namespace[
            "_customer_payment_runtime_composed"
        ]
        is True
    )

    restored_order_store = namespace[
        "customer_commercial_order_store"
    ]

    assert (
        restored_order_store.get(
            order_id=order.order_id
        )
        == order
    )

    assert namespace[
        "customer_payment_intent_store"
    ].is_ready()

    assert namespace[
        "customer_payment_evidence_store"
    ].is_ready()

    assert namespace[
        "customer_payment_settlement_store"
    ].is_ready()

    assert namespace[
        "customer_paypal_order_binding_store"
    ].is_ready()

    assert namespace[
        "customer_vnd_bank_reconciliation_store"
    ].is_ready()


def test_payment_runtime_composes_settlement_orchestration_chain(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    expected = {
        "CustomerPaymentSettlementService": 1,
        "CustomerPaymentSettlementActivationBridge": 1,
        "CustomerPaymentSettlementOrchestrationService": 1,
    }

    for owner_name, expected_count in expected.items():
        assert len(
            _calls_named(
                compose,
                owner_name,
            )
        ) == expected_count


def test_payment_runtime_exports_orchestration_owners(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    expected = (
        "customer_payment_settlement_service",
        "customer_payment_settlement_activation_bridge",
        "customer_payment_settlement_orchestration_service",
    )

    for name in expected:
        assert f"global {name}" in compose_source

        assert (
            f"{name} = ("
            in compose_source
            or f"{name} = "
            in compose_source
        )


def test_payment_runtime_settlement_service_uses_restored_stores(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    required = (
        "settlement_store=payment_settlement_store",
        "payment_evidence_store=payment_evidence_store",
        "payment_intent_store=payment_intent_store",
        "order_store=commercial_order_store",
    )

    normalized = " ".join(
        compose_source.split()
    )

    for token in required:
        assert token in normalized


def test_payment_runtime_activation_bridge_uses_setup_authority(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    calls = _calls_named(
        compose,
        "CustomerPaymentSettlementActivationBridge",
    )

    assert len(calls) == 1

    keywords = {
        keyword.arg: keyword.value
        for keyword in calls[0].keywords
    }

    expected = {
        "settlement_store": "payment_settlement_store",
        "order_store": "commercial_order_store",
        "setup_activation_service": (
            "customer_setup_activation_service"
        ),
    }

    assert set(keywords) == set(expected)

    for keyword_name, value_name in expected.items():
        value = keywords[keyword_name]

        assert isinstance(
            value,
            ast.Name,
        )

        assert value.id == value_name


def test_payment_runtime_orchestrator_uses_only_narrow_downstream_owners(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    calls = _calls_named(
        compose,
        "CustomerPaymentSettlementOrchestrationService",
    )

    assert len(calls) == 1

    keywords = {
        keyword.arg: keyword.value
        for keyword in calls[0].keywords
    }

    expected = {
        "settlement_service": "payment_settlement_service",
        "activation_bridge": (
            "payment_settlement_activation_bridge"
        ),
    }

    assert set(keywords) == set(expected)

    for keyword_name, value_name in expected.items():
        value = keywords[keyword_name]

        assert isinstance(
            value,
            ast.Name,
        )

        assert value.id == value_name


def test_payment_runtime_still_has_no_payment_execution_authority(
) -> None:
    compose = _function(
        "_compose_customer_payment_runtime"
    )

    compose_source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert compose_source is not None

    forbidden = (
        ".settle(",
        ".activate(",
        ".activate_from_settlement(",
        ".complete_verified_payment(",
        ".receive(",
        ".publish(",
        ".build_assertion(",
        ".confirm(",
        ".capture(",
        "include_router(",
        "operator_id",
        "webhook_verification",
    )

    for token in forbidden:
        assert token not in compose_source