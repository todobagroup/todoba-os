from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

MAIN_PATH = ROOT / "backend" / "main.py"
MISSION_SERVICE_PATH = (
    ROOT
    / "backend"
    / "trading"
    / "execution"
    / "execution_mission_service.py"
)


def _normalized_source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )


def _function_source(
    *,
    path: Path,
    function_name: str,
) -> str:
    source = _normalized_source(path)
    tree = ast.parse(
        source,
        filename=str(path),
    )

    node = next(
        (
            item
            for item in tree.body
            if isinstance(
                item,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and item.name == function_name
        ),
        None,
    )

    if node is None:
        raise AssertionError(
            f"{function_name} not found in {path}."
        )

    function_source = ast.get_source_segment(
        source,
        node,
    )

    assert function_source is not None
    return function_source


def test_execution_mission_service_has_one_time_commercial_gate_configuration():
    source = _normalized_source(
        MISSION_SERVICE_PATH
    )

    tree = ast.parse(
        source,
        filename=str(MISSION_SERVICE_PATH),
    )

    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ExecutionMissionService"
    )

    method = next(
        (
            node
            for node in cls.body
            if isinstance(node, ast.FunctionDef)
            and node.name
            == "configure_commercial_new_exposure_gate"
        ),
        None,
    )

    assert method is not None

    argument_names = {
        argument.arg
        for argument in (
            list(method.args.args)
            + list(method.args.kwonlyargs)
        )
    }

    assert {
        "commercial_deployment_binding_store",
        "commercial_capacity_decision_provider",
        "commercial_new_exposure_authorizer",
    }.issubset(argument_names)

    method_source = ast.get_source_segment(
        source,
        method,
    )

    assert method_source is not None

    assert (
        "commercial_deployment_binding_store"
        in method_source
    )
    assert (
        "commercial_capacity_decision_provider"
        in method_source
    )
    assert (
        "commercial_new_exposure_authorizer"
        in method_source
    )

    # Configuration must be one-time, not silently replaceable.
    assert (
        "already configured"
        in method_source.lower()
    )


def test_main_declares_exact_capacity_storage_paths():
    source = _normalized_source(
        MAIN_PATH
    )

    for filename in (
        "customer_commercial_deployment_bindings.json",
        "customer_commercial_billing_cycle_baselines.json",
        "customer_commercial_current_billing_cycles.json",
        "customer_commercial_external_funding_observations.json",
    ):
        assert filename in source


def test_capacity_runtime_composition_opens_existing_authority_only():
    source = _function_source(
        path=MAIN_PATH,
        function_name=(
            "_compose_customer_commercial_capacity_runtime"
        ),
    )

    for owner in (
        "CustomerCommercialDeploymentBindingStore",
        "CustomerCommercialBillingCycleBaselineStore",
        "CustomerCommercialCurrentBillingCycleStore",
        "CustomerCommercialExternalFundingObservationStore",
        "CustomerCommercialCurrentBillingCycleService",
        "CustomerCommercialCapacityDecisionService",
        "CustomerCommercialCapacityDecisionProvider",
        "CustomerCommercialNewExposureAuthorizationService",
    ):
        assert owner in source

    # Durable production runtime must never provision authority.
    assert "initialize_empty" not in source

    # Exact restore/open lifecycle.
    assert (
        "commercial_deployment_binding_store"
        in source
    )
    assert ".open_existing()" in source

    assert (
        "commercial_billing_cycle_baseline_store.load()"
        in source
    )
    assert (
        "commercial_current_billing_cycle_store.load()"
        in source
    )
    assert (
        "commercial_external_funding_observation_store.load()"
        in source
    )


def test_capacity_runtime_reuses_authoritative_payment_entitlement_registry():
    source = _function_source(
        path=MAIN_PATH,
        function_name=(
            "_compose_customer_commercial_capacity_runtime"
        ),
    )

    assert (
        "customer_commercial_entitlement_registry"
        in source
    )

    assert (
        "entitlement_registry=("
        in source
    )

    # P9F2A5c2 must not create a second entitlement authority.
    assert (
        "CustomerCommercialEntitlementRegistry("
        not in source
    )


def test_capacity_runtime_configures_existing_execution_mission_service():
    source = _function_source(
        path=MAIN_PATH,
        function_name=(
            "_compose_customer_commercial_capacity_runtime"
        ),
    )

    assert (
        "execution_mission_service"
        ".configure_commercial_new_exposure_gate("
        in source
    )

    for keyword in (
        "commercial_deployment_binding_store=",
        "commercial_capacity_decision_provider=",
        "commercial_new_exposure_authorizer=",
    ):
        assert keyword in source


def test_lifespan_composes_capacity_after_payment_and_before_mission_recovery():
    source = _function_source(
        path=MAIN_PATH,
        function_name="lifespan",
    )

    payment_index = source.index(
        "_compose_customer_payment_runtime("
    )

    vnd_ingress_index = source.index(
        "_compose_authenticated_vnd_reconciliation_ingress("
    )

    capacity_index = source.index(
        "_compose_customer_commercial_capacity_runtime("
    )

    except_index = source.index(
        "except RuntimeError as payment_startup_error:"
    )

    mission_recovery_index = source.index(
        "execution_mission_record_recovery.restore()"
    )

    assert (
        payment_index
        < vnd_ingress_index
        < capacity_index
        < except_index
        < mission_recovery_index
    )



def test_production_execution_mission_service_requires_commercial_gate():
    main_source = _normalized_source(
        MAIN_PATH
    )

    main_tree = ast.parse(
        main_source,
        filename=str(MAIN_PATH),
    )

    assignment = next(
        node
        for node in main_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "execution_mission_service"
            for target in node.targets
        )
    )

    assignment_source = ast.get_source_segment(
        main_source,
        assignment,
    )

    assert assignment_source is not None
    assert (
        "commercial_gate_required=True"
        in assignment_source
    )

    mission_source = _normalized_source(
        MISSION_SERVICE_PATH
    )

    mission_tree = ast.parse(
        mission_source,
        filename=str(MISSION_SERVICE_PATH),
    )

    cls = next(
        node
        for node in mission_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ExecutionMissionService"
    )

    create = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "create_mission"
    )

    create_source = ast.get_source_segment(
        mission_source,
        create,
    )

    assert create_source is not None
    assert "self.commercial_gate_required" in create_source
    assert (
        "is required but not configured"
        in create_source
    )

    existing_index = create_source.index(
        "if existing_record is not None:"
    )
    required_index = create_source.index(
        "self.commercial_gate_required"
    )
    save_index = create_source.rfind(
        "self.repository.save("
    )

    assert (
        existing_index
        < required_index
        < save_index
    )
