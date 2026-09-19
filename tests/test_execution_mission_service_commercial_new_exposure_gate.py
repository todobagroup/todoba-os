import ast
import inspect
from pathlib import Path

from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)


def _service_source():
    path = Path(
        "backend/trading/execution/"
        "execution_mission_service.py"
    )

    text = path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    tree = ast.parse(
        text,
        filename=str(path),
    )

    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ExecutionMissionService"
    )

    return text, owner


def test_constructor_exposes_exact_optional_commercial_gate_dependencies():
    parameters = inspect.signature(
        ExecutionMissionService.__init__
    ).parameters

    assert (
        "commercial_deployment_binding_store"
        in parameters
    )
    assert (
        "commercial_capacity_decision_provider"
        in parameters
    )
    assert (
        "commercial_new_exposure_authorizer"
        in parameters
    )


def test_create_mission_resolves_commercial_authority_from_mission_identity():
    text, owner = _service_source()

    method = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "create_mission"
    )

    source = ast.get_source_segment(
        text,
        method,
    )

    assert source is not None

    assert "final_mission.agent_id" in source
    assert "final_mission.account_fingerprint" in source
    assert "get_by_agent_account" in source
    assert "commercial_capacity_decision_provider" in source
    assert ".provide(" in source
    assert "binding.deployment_id" in source
    assert "commercial_new_exposure_authorizer" in source
    assert ".authorize(" in source


def test_first_issuance_authorization_precedes_first_repository_mutation():
    text, owner = _service_source()

    method = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "create_mission"
    )

    source = ast.get_source_segment(
        text,
        method,
    )

    assert source is not None

    authorize_index = source.rfind(
        "commercial_new_exposure_authorizer"
    )

    first_issuance_save_index = source.rfind(
        "self.repository.save("
    )

    assert authorize_index != -1
    assert first_issuance_save_index != -1
    assert authorize_index < first_issuance_save_index


def test_existing_record_branch_remains_before_commercial_authorization():
    text, owner = _service_source()

    method = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "create_mission"
    )

    source = ast.get_source_segment(
        text,
        method,
    )

    assert source is not None

    existing_branch_index = source.find(
        "if existing_record is not None:"
    )

    authorization_index = source.rfind(
        "commercial_new_exposure_authorizer"
    )

    assert existing_branch_index != -1
    assert authorization_index != -1

    assert existing_branch_index < authorization_index


def test_service_does_not_accept_caller_supplied_deployment_identity():
    parameters = inspect.signature(
        ExecutionMissionService.create_mission
    ).parameters

    assert list(parameters) == [
        "self",
        "mission",
    ]

    assert "deployment_id" not in parameters
    assert "customer_id" not in parameters
