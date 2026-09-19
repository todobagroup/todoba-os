from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    ROOT
    / "backend"
    / "commercial"
    / "customer_commercial_external_funding_convergence_service.py"
)

API_PATH = (
    ROOT
    / "backend"
    / "commercial"
    / "customer_commercial_external_funding_api.py"
)

MAIN_PATH = ROOT / "backend" / "main.py"


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )


def test_p9f2b0a_convergence_owner_exists():
    assert SERVICE_PATH.is_file()


def test_p9f2b0a_api_owner_exists():
    assert API_PATH.is_file()


def test_convergence_uses_authoritative_commercial_identity_and_cycle():
    source = _source(SERVICE_PATH)

    required = (
        "CustomerCommercialDeploymentBindingStore",
        "CustomerCommercialCapacityDecisionProvider",
        "CustomerCommercialExternalFundingObservationService",
        "MT5ExternalFundingClassifier",
        "MT5AccountCashflowEvidence",
        "get_by_agent_account",
        ".provide(",
        ".classify(",
        ".observe(",
    )

    for fragment in required:
        assert fragment in source

    binding_index = source.index(
        "get_by_agent_account"
    )
    capacity_index = source.index(
        ".provide("
    )
    classify_index = source.index(
        ".classify("
    )
    observe_index = source.index(
        ".observe("
    )

    assert (
        binding_index
        < capacity_index
        < classify_index
        < observe_index
    )


def test_convergence_does_not_accept_caller_commercial_authority():
    source = _source(SERVICE_PATH)
    tree = ast.parse(
        source,
        filename=str(SERVICE_PATH),
    )

    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name
        == "CustomerCommercialExternalFundingConvergenceService"
    )

    method = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "converge"
    )

    parameters = {
        arg.arg
        for arg in (
            list(method.args.args)
            + list(method.args.kwonlyargs)
        )
    }

    assert "authenticated_agent_id" in parameters
    assert "evidence" in parameters

    forbidden = {
        "cycle_id",
        "customer_id",
        "deployment_id",
        "commercial_entitlement_id",
        "funding_kind",
        "classification",
    }

    assert parameters.isdisjoint(
        forbidden
    )


def test_api_uses_trusted_agent_authentication_and_account_guard():
    source = _source(API_PATH)

    for required in (
        "create_trusted_agent_authentication_dependency",
        "TrustedAgentAccountBindingGuard",
        "account_binding_guard.require_binding(",
        "CustomerCommercialExternalFundingConvergenceService",
        ".converge(",
    ):
        assert required in source

    assert "/commercial/external-funding/evidence" in source


def test_api_accepts_raw_broker_facts_not_commercial_truth():
    source = _source(API_PATH)

    request_class_start = source.index(
        "class CustomerCommercialExternalFundingEvidenceRequest"
    )

    router_start = source.index(
        "def create_customer_commercial_external_funding_router"
    )

    request_source = source[
        request_class_start:
        router_start
    ]

    for required in (
        "account_fingerprint",
        "deal_ticket",
        "deal_time_msc",
        "observed_at",
        "cashflow_kind",
        "raw_deal_type",
        "amount",
        "order_ticket",
        "deal_entry",
        "magic",
        "position_id",
        "deal_reason",
        "volume",
        "price",
        "symbol",
        "external_id",
        "comment",
    ):
        assert required in request_source

    for forbidden in (
        "cycle_id",
        "customer_id",
        "deployment_id",
        "commercial_entitlement_id",
        "funding_kind",
    ):
        assert forbidden not in request_source


def test_server_not_client_owns_external_funding_classification():
    api_source = _source(API_PATH)
    service_source = _source(SERVICE_PATH)

    request_start = api_source.index(
        "class CustomerCommercialExternalFundingEvidenceRequest"
    )
    router_start = api_source.index(
        "def create_customer_commercial_external_funding_router"
    )

    request_source = api_source[
        request_start:
        router_start
    ]

    assert (
        "MT5ExternalFundingClassification"
        not in request_source
    )
    assert "funding_kind" not in request_source

    assert "MT5ExternalFundingClassifier" in service_source
    assert ".classify(" in service_source


def test_main_composes_external_funding_ingress_inside_capacity_runtime():
    source = _source(MAIN_PATH)

    for required in (
        "CustomerCommercialExternalFundingObservationService",
        "CustomerCommercialExternalFundingConvergenceService",
        "create_customer_commercial_external_funding_router",
        "commercial_external_funding_observation_store",
        "commercial_billing_cycle_baseline_store",
        "commercial_deployment_binding_store",
        "commercial_capacity_decision_provider",
        "trusted_agent_authenticator",
        "trusted_agent_account_binding_guard",
    ):
        assert required in source


def test_external_funding_ingress_does_not_gain_direct_mt5_authority():
    combined = (
        _source(SERVICE_PATH)
        + "\n"
        + _source(API_PATH)
    )

    for forbidden in (
        "MetaTrader5",
        "history_deals_get",
        "HistorySelect",
        "order_send",
        "TRADE_ACTION_REMOVE",
    ):
        assert forbidden not in combined
