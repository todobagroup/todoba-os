from backend.main import (
    broker_execution_evidence_processor,
    execution_mission_acknowledgement_processor,
    execution_mission_completed_processor,
    execution_mission_delivery_lease_persistence,
    execution_mission_delivery_expiration_policy,
    execution_mission_delivery_lease_recovery,
    execution_mission_delivery_lease_registry,
    execution_mission_delivery_lease_service,
    execution_mission_delivery_redelivery_processor,
    execution_mission_execution_started_processor,
    execution_mission_failed_processor,
    execution_mission_lifecycle_scheduler,
    execution_mission_lifecycle_service,
    execution_mission_record_cleanup,
    execution_mission_record_persistence,
    execution_mission_record_retention_policy,
    execution_mission_record_retention_scheduler,
    execution_mission_registry,
    todoba_runtime,
)
from backend.trading.execution.broker_execution_evidence_processor import (
    BrokerExecutionEvidenceProcessor,
)
from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)
from backend.trading.execution.execution_mission_completed_processor import (
    ExecutionMissionCompletedProcessor,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_recovery import (
    ExecutionMissionDeliveryLeaseRecovery,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)
from backend.trading.execution.execution_mission_delivery_redelivery_processor import (
    ExecutionMissionDeliveryRedeliveryProcessor,
)
from backend.trading.execution.execution_mission_execution_started_processor import (
    ExecutionMissionExecutionStartedProcessor,
)
from backend.trading.execution.execution_mission_failed_processor import (
    ExecutionMissionFailedProcessor,
)
from backend.trading.execution.execution_mission_lifecycle_scheduler import (
    ExecutionMissionLifecycleScheduler,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_record_cleanup import (
    ExecutionMissionRecordCleanup,
)
from backend.trading.execution.execution_mission_record_retention_policy import (
    ExecutionMissionRecordRetentionPolicy,
)
from backend.trading.execution.execution_mission_record_retention_scheduler import (
    ExecutionMissionRecordRetentionScheduler,
)
from backend.trading.execution.execution_mission_delivery_expiration_policy import (
    ExecutionMissionDeliveryExpirationPolicy,
)


def test_main_composes_execution_mission_lifecycle_runtime() -> None:
    assert isinstance(
        execution_mission_lifecycle_service,
        ExecutionMissionLifecycleService,
    )

    assert isinstance(
        execution_mission_delivery_lease_registry,
        ExecutionMissionDeliveryLeaseRegistry,
    )

    assert isinstance(
        execution_mission_delivery_lease_persistence,
        ExecutionMissionDeliveryLeasePersistence,
    )

    assert isinstance(
        execution_mission_delivery_lease_recovery,
        ExecutionMissionDeliveryLeaseRecovery,
    )

    assert isinstance(
        execution_mission_delivery_lease_service,
        ExecutionMissionDeliveryLeaseService,
    )

    assert (
        execution_mission_delivery_lease_service.registry
        is execution_mission_delivery_lease_registry
    )

    assert (
        execution_mission_delivery_lease_service.persistence
        is execution_mission_delivery_lease_persistence
    )

    assert (
        execution_mission_delivery_lease_recovery.registry
        is execution_mission_delivery_lease_registry
    )

    assert (
        execution_mission_delivery_lease_recovery.persistence
        is execution_mission_delivery_lease_persistence
    )

    assert isinstance(
        execution_mission_acknowledgement_processor,
        ExecutionMissionAcknowledgementProcessor,
    )

    assert (
        execution_mission_acknowledgement_processor.lease_registry
        is execution_mission_delivery_lease_registry
    )

    assert (
        execution_mission_acknowledgement_processor.lease_persistence
        is execution_mission_delivery_lease_persistence
    )

    assert isinstance(
        execution_mission_execution_started_processor,
        ExecutionMissionExecutionStartedProcessor,
    )

    assert isinstance(
        execution_mission_completed_processor,
        ExecutionMissionCompletedProcessor,
    )

    assert isinstance(
        execution_mission_failed_processor,
        ExecutionMissionFailedProcessor,
    )

    assert isinstance(
        broker_execution_evidence_processor,
        BrokerExecutionEvidenceProcessor,
    )

    assert isinstance(
        execution_mission_delivery_redelivery_processor,
        ExecutionMissionDeliveryRedeliveryProcessor,
    )

    assert (
        execution_mission_delivery_redelivery_processor.lease_registry
        is execution_mission_delivery_lease_registry
    )

    assert (
        execution_mission_delivery_redelivery_processor.lease_persistence
        is execution_mission_delivery_lease_persistence
    )

    assert (
        execution_mission_delivery_redelivery_processor.lifecycle_service
        is execution_mission_lifecycle_service
    )

    assert (
        execution_mission_delivery_redelivery_processor.max_delivery_attempts
        == 3
    )

    assert isinstance(
        execution_mission_record_retention_policy,
        ExecutionMissionRecordRetentionPolicy,
    )

    assert (
        execution_mission_record_retention_policy.retention_days
        == 30
    )

    assert isinstance(
        execution_mission_record_cleanup,
        ExecutionMissionRecordCleanup,
    )

    assert (
        execution_mission_record_cleanup.registry
        is execution_mission_registry
    )

    assert (
        execution_mission_record_cleanup.persistence
        is execution_mission_record_persistence
    )

    assert isinstance(
        execution_mission_record_retention_scheduler,
        ExecutionMissionRecordRetentionScheduler,
    )

    assert (
        execution_mission_record_retention_scheduler.policy
        is execution_mission_record_retention_policy
    )

    assert (
        execution_mission_record_retention_scheduler.cleanup
        is execution_mission_record_cleanup
    )

    assert (
        execution_mission_record_retention_scheduler.interval_seconds
        == 3600.0
    )

    assert (
        execution_mission_record_retention_scheduler.start
        in todoba_runtime._start_services
    )

    assert (
        execution_mission_record_retention_scheduler.stop
        in todoba_runtime._stop_services
    )

    assert isinstance(
        execution_mission_lifecycle_scheduler,
        ExecutionMissionLifecycleScheduler,
    )
    assert isinstance(
    execution_mission_delivery_expiration_policy,
    ExecutionMissionDeliveryExpirationPolicy,
)

    assert execution_mission_lifecycle_scheduler.processors == [
        execution_mission_acknowledgement_processor,
        execution_mission_execution_started_processor,
        execution_mission_completed_processor,
        execution_mission_failed_processor,
        broker_execution_evidence_processor,
        execution_mission_delivery_redelivery_processor,
    ]