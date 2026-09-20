import ast
from pathlib import Path


PROVISIONER_PATH = Path(
    "scripts/provision_customer_setup_control_plane.py"
)

EXPECTED_FILENAMES = (
    "customer_commercial_deployment_bindings.json",
    "customer_commercial_billing_cycle_baselines.json",
    "customer_commercial_current_billing_cycles.json",
    "customer_commercial_external_funding_observations.json",
    "customer_commercial_pending_exposure_containment_issuances.json",
)

EXPECTED_STORE_CLASSES = (
    "CustomerCommercialDeploymentBindingStore",
    "CustomerCommercialBillingCycleBaselineStore",
    "CustomerCommercialCurrentBillingCycleStore",
    "CustomerCommercialExternalFundingObservationStore",
    "CustomerCommercialPendingExposureContainmentIssuanceStore",
)


def _provisioner_source():
    text = PROVISIONER_PATH.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    tree = ast.parse(
        text,
        filename=str(PROVISIONER_PATH),
    )

    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        == "provision_customer_setup_control_plane"
    )

    source = ast.get_source_segment(
        text,
        function,
    )

    assert source is not None

    return text, source


def test_capacity_store_filenames_are_declared():
    text, _ = _provisioner_source()

    for filename in EXPECTED_FILENAMES:
        assert filename in text


def test_provisioner_constructs_all_capacity_stores():
    _, source = _provisioner_source()

    for class_name in EXPECTED_STORE_CLASSES:
        assert class_name in source


def test_provisioner_initializes_or_opens_all_capacity_stores():
    _, source = _provisioner_source()

    for class_name in EXPECTED_STORE_CLASSES:
        assert class_name in source

    assert source.count(
        "initialize_empty()"
    ) >= 5

    required_store_variables = (
        "commercial_deployment_binding_store",
        "commercial_billing_cycle_baseline_store",
        "commercial_current_billing_cycle_store",
        "commercial_external_funding_observation_store",
        "commercial_pending_exposure_containment_issuance_store",
    )

    for required in required_store_variables:
        assert required in source

    assert (
        "commercial_deployment_binding_store.open_existing()"
        in source
        or (
            "if not commercial_deployment_binding_store.is_ready():"
            in source
            and
            "commercial_deployment_binding_store.initialize_empty()"
            in source
        )
    )

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
    assert (
        "commercial_pending_exposure_containment_issuance_store.load()"
        in source
    )


def test_provisioner_verifies_capacity_store_readiness():
    _, source = _provisioner_source()

    required_ready_checks = (
        "commercial_deployment_binding_store.is_ready()",
        "commercial_billing_cycle_baseline_store.is_ready()",
        "commercial_current_billing_cycle_store.is_ready()",
        "commercial_external_funding_observation_store.is_ready()",
        "commercial_pending_exposure_containment_issuance_store.is_ready()",
    )

    for required in required_ready_checks:
        assert required in source


def test_provisioner_keeps_existing_public_return_contract():
    text, _ = _provisioner_source()

    tree = ast.parse(
        text,
        filename=str(PROVISIONER_PATH),
    )

    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        == "provision_customer_setup_control_plane"
    )

    annotation = ast.unparse(
        function.returns
    )

    assert annotation == (
        "tuple[Path, Path, Path, Path, Path]"
    )
