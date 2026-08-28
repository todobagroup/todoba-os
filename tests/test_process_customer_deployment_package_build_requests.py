"""
Tests for the one-shot customer package build queue runner.

The suite proves:
- empty queue succeeds
- deterministic snapshot order is preserved
- BUILT / ALREADY_READY / BUSY all continue
- one worker fault fails closed immediately
- malformed queue/result state fails closed
- result deployment identity must converge
- summary arithmetic is closed
- CLI accepts only machine-local build paths
- production runner never initializes durable state
- missing production durable state fails closed without
  creating replacement commercial state
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
)
from backend.commercial.customer_deployment_package_build_worker import (
    CustomerDeploymentPackageBuildWorkerResult,
    CustomerDeploymentPackageBuildWorkerStatus,
)
from scripts.process_customer_deployment_package_build_requests import (
    CustomerDeploymentPackageBuildQueueSummary,
    _build_parser,
    _compose_customer_deployment_package_build_runner,
    process_customer_deployment_package_build_requests,
)


def make_request(
    deployment_id: str,
) -> CustomerDeploymentPackageBuildRequest:
    return CustomerDeploymentPackageBuildRequest(
        deployment_id=deployment_id,
        bootstrap_request_id=(
            "bootstrap-"
            + deployment_id
        ),
    )


def make_result(
    deployment_id: str,
    status: CustomerDeploymentPackageBuildWorkerStatus,
) -> CustomerDeploymentPackageBuildWorkerResult:
    return CustomerDeploymentPackageBuildWorkerResult(
        deployment_id=deployment_id,
        status=status,
    )


class FakeBuildRequestStore:
    def __init__(
        self,
        requests,
    ) -> None:
        self.requests = requests
        self.all_calls = 0

    def all(
        self,
    ):
        self.all_calls += 1
        return self.requests


class FakeWorker:
    def __init__(
        self,
        results,
        *,
        fail_on: str | None = None,
    ) -> None:
        self.results = dict(
            results
        )
        self.fail_on = fail_on
        self.calls: list[str] = []

    def process(
        self,
        *,
        deployment_id: str,
    ):
        self.calls.append(
            deployment_id
        )

        if deployment_id == self.fail_on:
            raise RuntimeError(
                "simulated-worker-failure"
            )

        return self.results[
            deployment_id
        ]


def test_empty_queue_succeeds() -> None:
    store = FakeBuildRequestStore(
        ()
    )

    worker = FakeWorker(
        {}
    )

    summary = (
        process_customer_deployment_package_build_requests(
            build_request_store=store,
            worker=worker,
        )
    )

    assert summary == (
        CustomerDeploymentPackageBuildQueueSummary(
            total=0,
            built=0,
            already_ready=0,
            busy=0,
        )
    )

    assert store.all_calls == 1
    assert worker.calls == []


def test_runner_preserves_snapshot_order_and_counts_all_safe_statuses(
) -> None:
    requests = (
        make_request(
            "deployment-c"
        ),
        make_request(
            "deployment-a"
        ),
        make_request(
            "deployment-b"
        ),
    )

    worker = FakeWorker(
        {
            "deployment-c": make_result(
                "deployment-c",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUILT,
            ),
            "deployment-a": make_result(
                "deployment-a",
                CustomerDeploymentPackageBuildWorkerStatus
                .ALREADY_READY,
            ),
            "deployment-b": make_result(
                "deployment-b",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUSY,
            ),
        }
    )

    summary = (
        process_customer_deployment_package_build_requests(
            build_request_store=(
                FakeBuildRequestStore(
                    requests
                )
            ),
            worker=worker,
        )
    )

    assert worker.calls == [
        "deployment-c",
        "deployment-a",
        "deployment-b",
    ]

    assert summary == (
        CustomerDeploymentPackageBuildQueueSummary(
            total=3,
            built=1,
            already_ready=1,
            busy=1,
        )
    )


def test_busy_does_not_stop_later_requests() -> None:
    requests = (
        make_request(
            "deployment-a"
        ),
        make_request(
            "deployment-b"
        ),
    )

    worker = FakeWorker(
        {
            "deployment-a": make_result(
                "deployment-a",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUSY,
            ),
            "deployment-b": make_result(
                "deployment-b",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUILT,
            ),
        }
    )

    summary = (
        process_customer_deployment_package_build_requests(
            build_request_store=(
                FakeBuildRequestStore(
                    requests
                )
            ),
            worker=worker,
        )
    )

    assert worker.calls == [
        "deployment-a",
        "deployment-b",
    ]

    assert summary.busy == 1
    assert summary.built == 1


def test_worker_fault_stops_queue_immediately() -> None:
    requests = (
        make_request(
            "deployment-a"
        ),
        make_request(
            "deployment-b"
        ),
        make_request(
            "deployment-c"
        ),
    )

    worker = FakeWorker(
        {
            "deployment-a": make_result(
                "deployment-a",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUILT,
            ),
            "deployment-b": make_result(
                "deployment-b",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUILT,
            ),
            "deployment-c": make_result(
                "deployment-c",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUILT,
            ),
        },
        fail_on="deployment-b",
    )

    with pytest.raises(
        RuntimeError,
        match="simulated-worker-failure",
    ):
        process_customer_deployment_package_build_requests(
            build_request_store=(
                FakeBuildRequestStore(
                    requests
                )
            ),
            worker=worker,
        )

    assert worker.calls == [
        "deployment-a",
        "deployment-b",
    ]


def test_store_must_return_tuple_snapshot() -> None:
    store = FakeBuildRequestStore(
        [
            make_request(
                "deployment-a"
            )
        ]
    )

    worker = FakeWorker(
        {}
    )

    with pytest.raises(
        RuntimeError,
        match="must return a tuple snapshot",
    ):
        process_customer_deployment_package_build_requests(
            build_request_store=store,
            worker=worker,
        )

    assert worker.calls == []


def test_invalid_request_state_fails_closed() -> None:
    store = FakeBuildRequestStore(
        (
            object(),
        )
    )

    worker = FakeWorker(
        {}
    )

    with pytest.raises(
        RuntimeError,
        match="invalid request state",
    ):
        process_customer_deployment_package_build_requests(
            build_request_store=store,
            worker=worker,
        )

    assert worker.calls == []


def test_invalid_worker_result_fails_closed() -> None:
    request = make_request(
        "deployment-a"
    )

    worker = FakeWorker(
        {
            "deployment-a": object(),
        }
    )

    with pytest.raises(
        RuntimeError,
        match="returned invalid result",
    ):
        process_customer_deployment_package_build_requests(
            build_request_store=(
                FakeBuildRequestStore(
                    (
                        request,
                    )
                )
            ),
            worker=worker,
        )


def test_worker_result_deployment_identity_must_match_request(
) -> None:
    request = make_request(
        "deployment-a"
    )

    worker = FakeWorker(
        {
            "deployment-a": make_result(
                "deployment-other",
                CustomerDeploymentPackageBuildWorkerStatus
                .BUILT,
            ),
        }
    )

    with pytest.raises(
        RuntimeError,
        match="deployment identity mismatch",
    ):
        process_customer_deployment_package_build_requests(
            build_request_store=(
                FakeBuildRequestStore(
                    (
                        request,
                    )
                )
            ),
            worker=worker,
        )


def test_summary_counts_must_converge_to_total() -> None:
    with pytest.raises(
        ValueError,
        match="must converge to total",
    ):
        CustomerDeploymentPackageBuildQueueSummary(
            total=3,
            built=1,
            already_ready=1,
            busy=0,
        )


def test_cli_accepts_only_machine_local_build_paths() -> None:
    parser = _build_parser()

    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith(
            "--"
        )
        and option != "--help"
    }

    assert option_strings == {
        "--platform-mql5-root",
        "--metaeditor-path",
        "--workspace-root",
    }

    forbidden = {
        "--customer-id",
        "--deployment-id",
        "--agent-id",
        "--account-fingerprint",
        "--control-plane-root",
        "--package-root",
        "--master-key",
        "--confirm-runtime-stopped",
    }

    assert (
        option_strings.intersection(
            forbidden
        )
        == set()
    )


def test_runner_source_has_recovery_only_commercial_surface(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "process_customer_deployment_package_build_requests.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    called_attributes = [
        node.func.attr
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
                ast.Attribute,
            )
        )
    ]

    assert (
        "initialize_empty"
        not in called_attributes
    )

    forbidden_actions = {
        "register",
        "activate_bootstrap",
        "bind",
        "grant",
        "issue",
        "onboard",
        "enroll",
        "suspend",
        "reactivate",
        "revoke",
    }

    assert (
        forbidden_actions.intersection(
            called_attributes
        )
        == set()
    )

    imports_backend_main = False

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                if (
                    alias.name == "backend.main"
                    or alias.name.startswith(
                        "backend.main."
                    )
                ):
                    imports_backend_main = True

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if (
                node.module == "backend.main"
                or (
                    node.module is not None
                    and node.module.startswith(
                        "backend.main."
                    )
                )
                or (
                    node.module == "backend"
                    and any(
                        alias.name == "main"
                        for alias in node.names
                    )
                )
            ):
                imports_backend_main = True

    assert not imports_backend_main

    assert (
        "CustomerAccessProvisioningService"
        not in source
    )

    assert (
        "CustomerDeploymentEntitlementRegistry"
        not in source
    )

    assert (
        "CustomerSetupActivationService"
        not in source
    )

    assert (
        "customer_deployment_package_build_requests"
        in source
    )

    assert (
        "customer_deployment_package_build_locks"
        in source
    )


def test_missing_production_state_fails_closed_without_initializing(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    platform_mql5_root = (
        tmp_path
        / "platform-mql5"
    )

    workspace_root = (
        tmp_path
        / "workspace"
    )

    package_root = (
        tmp_path
        / "packages"
    )

    metaeditor_path = (
        tmp_path
        / "metaeditor64.exe"
    )

    with pytest.raises(
        RuntimeError,
        match="is not initialized",
    ):
        _compose_customer_deployment_package_build_runner(
            control_plane_root=(
                control_plane_root
            ),
            encoded_master_key=(
                "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s="
            ),
            mql5_source_root=(
                tmp_path
                / "MQL5"
            ),
            platform_mql5_root=(
                platform_mql5_root
            ),
            workspace_root=(
                workspace_root
            ),
            package_root=(
                package_root
            ),
            metaeditor_path=(
                metaeditor_path
            ),
        )

    assert not (
        control_plane_root
        / "commercial"
        / "customer_deployments.json"
    ).exists()

    assert not (
        control_plane_root
        / "commercial"
        / "customer_deployment_secrets.json"
    ).exists()

    assert not (
        control_plane_root
        / "commercial"
        / "customer_deployment_bootstraps.json"
    ).exists()

    assert not (
        control_plane_root
        / "commercial"
        / "customer_deployment_package_build_requests"
    ).exists()

    assert not (
        control_plane_root
        / "commercial"
        / "customer_deployment_package_build_locks"
    ).exists()

    assert not (
        control_plane_root
        / "trading"
        / "trusted_agent_account_bindings.json"
    ).exists()
