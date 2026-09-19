"""
TODOBA Execution Mission Service

Coordinates execution mission creation flow.

This component owns:
- repository storage
- mission persistence
- lifecycle registration
- mission record persistence
- initial delivery to Trusted Agent queue
- producer retry safety
- optional Cloud-owned security sequence assignment

It does not:
- receive HTTP requests
- execute broker orders
- own lease-based redelivery policy
"""

from dataclasses import replace
from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.security_sequence_assignment_service import (
    SecuritySequenceAssignmentService,
)

from backend.commercial.customer_commercial_capacity_decision_provider import (
    CustomerCommercialCapacityDecisionProvider,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_new_exposure_authorization_service import (
    CustomerCommercialNewExposureAuthorizationService,
)


class ExecutionMissionService:
    """
    Application service for execution mission creation.
    """

    _TERMINAL_STATUSES = {
        ExecutionMissionStatus.COMPLETED,
        ExecutionMissionStatus.FAILED,
    }

    def __init__(
        self,
        repository: ExecutionMissionRepository,
        persistence: ExecutionMissionPersistence,
        delivery_bridge: ExecutionMissionDeliveryBridge,
        registry: ExecutionMissionRegistry,
        record_persistence: Optional[
            ExecutionMissionRecordPersistence
        ] = None,
        *,
        security_sequence_assignment_service: Optional[
            SecuritySequenceAssignmentService
        ] = None,
        commercial_deployment_binding_store: Optional[
            CustomerCommercialDeploymentBindingStore
        ] = None,
        commercial_capacity_decision_provider: Optional[
            CustomerCommercialCapacityDecisionProvider
        ] = None,
        commercial_new_exposure_authorizer: Optional[
            CustomerCommercialNewExposureAuthorizationService
        ] = None,
        commercial_gate_required: bool = False,
    ) -> None:
        if not isinstance(
            repository,
            ExecutionMissionRepository,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionRepository."
            )

        if not isinstance(
            persistence,
            ExecutionMissionPersistence,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionPersistence."
            )

        if not isinstance(
            delivery_bridge,
            ExecutionMissionDeliveryBridge,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionDeliveryBridge."
            )

        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionRegistry."
            )

        if (
            record_persistence is not None
            and not isinstance(
                record_persistence,
                ExecutionMissionRecordPersistence,
            )
        ):
            raise TypeError(
                "record_persistence must be "
                "ExecutionMissionRecordPersistence."
            )

        if (
            security_sequence_assignment_service
            is not None
            and not isinstance(
                security_sequence_assignment_service,
                SecuritySequenceAssignmentService,
            )
        ):
            raise TypeError(
                "security_sequence_assignment_service "
                "must be SecuritySequenceAssignmentService."
            )

        if not isinstance(
            commercial_gate_required,
            bool,
        ):
            raise TypeError(
                "commercial_gate_required must be bool."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry
        self.record_persistence = record_persistence
        self.security_sequence_assignment_service = (
            security_sequence_assignment_service
        )

        commercial_gate_dependencies = (
            commercial_deployment_binding_store,
            commercial_capacity_decision_provider,
            commercial_new_exposure_authorizer,
        )

        provided_commercial_gate_dependencies = sum(
            dependency is not None
            for dependency in commercial_gate_dependencies
        )

        if provided_commercial_gate_dependencies not in (
            0,
            len(commercial_gate_dependencies),
        ):
            raise ValueError(
                "commercial new-exposure gate dependencies "
                "must be provided together."
            )

        if (
            commercial_deployment_binding_store is not None
            and not isinstance(
                commercial_deployment_binding_store,
                CustomerCommercialDeploymentBindingStore,
            )
        ):
            raise TypeError(
                "commercial_deployment_binding_store must be "
                "CustomerCommercialDeploymentBindingStore."
            )

        if (
            commercial_capacity_decision_provider is not None
            and not isinstance(
                commercial_capacity_decision_provider,
                CustomerCommercialCapacityDecisionProvider,
            )
        ):
            raise TypeError(
                "commercial_capacity_decision_provider must be "
                "CustomerCommercialCapacityDecisionProvider."
            )

        if (
            commercial_new_exposure_authorizer is not None
            and not isinstance(
                commercial_new_exposure_authorizer,
                CustomerCommercialNewExposureAuthorizationService,
            )
        ):
            raise TypeError(
                "commercial_new_exposure_authorizer must be "
                "CustomerCommercialNewExposureAuthorizationService."
            )

        self.commercial_deployment_binding_store = (
            commercial_deployment_binding_store
        )
        self.commercial_capacity_decision_provider = (
            commercial_capacity_decision_provider
        )
        self.commercial_new_exposure_authorizer = (
            commercial_new_exposure_authorizer
        )
        self.commercial_gate_required = (
            commercial_gate_required
        )

    def _assign_security_sequence(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        assignment_service = (
            self.security_sequence_assignment_service
        )

        if assignment_service is None:
            return mission

        if mission.security_sequence != 0:
            raise ValueError(
                "source mission security_sequence "
                "must be zero."
            )

        source_payload = (
            ExecutionMissionSerializer.serialize(
                mission
            )
        )

        security_sequence = (
            assignment_service.assign(
                mission_id=mission.mission_id,
                source_payload=source_payload,
            )
        )

        return replace(
            mission,
            security_sequence=security_sequence,
        )

    def configure_commercial_new_exposure_gate(
        self,
        *,
        commercial_deployment_binding_store: (
            CustomerCommercialDeploymentBindingStore
        ),
        commercial_capacity_decision_provider: (
            CustomerCommercialCapacityDecisionProvider
        ),
        commercial_new_exposure_authorizer: (
            CustomerCommercialNewExposureAuthorizationService
        ),
    ) -> None:
        if (
            self.commercial_deployment_binding_store
            is not None
            or self.commercial_capacity_decision_provider
            is not None
            or self.commercial_new_exposure_authorizer
            is not None
        ):
            raise RuntimeError(
                "Commercial new-exposure gate "
                "is already configured."
            )

        if not isinstance(
            commercial_deployment_binding_store,
            CustomerCommercialDeploymentBindingStore,
        ):
            raise TypeError(
                "commercial_deployment_binding_store must be "
                "CustomerCommercialDeploymentBindingStore."
            )

        if not isinstance(
            commercial_capacity_decision_provider,
            CustomerCommercialCapacityDecisionProvider,
        ):
            raise TypeError(
                "commercial_capacity_decision_provider must be "
                "CustomerCommercialCapacityDecisionProvider."
            )

        if not isinstance(
            commercial_new_exposure_authorizer,
            CustomerCommercialNewExposureAuthorizationService,
        ):
            raise TypeError(
                "commercial_new_exposure_authorizer must be "
                "CustomerCommercialNewExposureAuthorizationService."
            )

        self.commercial_deployment_binding_store = (
            commercial_deployment_binding_store
        )
        self.commercial_capacity_decision_provider = (
            commercial_capacity_decision_provider
        )
        self.commercial_new_exposure_authorizer = (
            commercial_new_exposure_authorizer
        )

    def create_mission(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "create_mission requires ExecutionMission."
            )

        final_mission = self._assign_security_sequence(
            mission
        )

        existing_record = self.registry.get(
            final_mission.mission_id
        )

        if (
            existing_record is not None
            and existing_record.mission != final_mission
        ):
            raise ValueError(
                "Execution mission ID conflict."
            )

        if existing_record is not None:
            if (
                existing_record.status
                in self._TERMINAL_STATUSES
            ):
                return existing_record.mission

            if (
                existing_record.status
                != ExecutionMissionStatus.CREATED
            ):
                return existing_record.mission

            stored_mission = self.repository.save(
                final_mission
            )

            self.persistence.save(
                self.repository
            )

            self.delivery_bridge.redeliver(
                stored_mission
            )

            return stored_mission

        if (
            self.commercial_gate_required
            and self.commercial_deployment_binding_store
            is None
        ):
            raise RuntimeError(
                "Commercial new-exposure gate "
                "is required but not configured."
            )

        if (
            self.commercial_deployment_binding_store
            is not None
        ):
            binding = (
                self.commercial_deployment_binding_store
                .get_by_agent_account(
                    agent_id=final_mission.agent_id,
                    account_fingerprint=(
                        final_mission.account_fingerprint
                    ),
                )
            )

            if binding is None:
                raise RuntimeError(
                    "Execution mission commercial deployment "
                    "binding could not be resolved."
                )

            capacity_decision = (
                self.commercial_capacity_decision_provider
                .provide(
                    deployment_id=binding.deployment_id,
                )
            )

            self.commercial_new_exposure_authorizer.authorize(
                capacity_decision=capacity_decision,
            )

        stored_mission = self.repository.save(
            final_mission
        )

        self.persistence.save(
            self.repository
        )

        record = self.registry.register(
            ExecutionMissionRecord(
                mission=stored_mission
            )
        )

        if self.record_persistence is not None:
            self.record_persistence.save(
                self.registry
            )

        self.delivery_bridge.deliver(
            stored_mission
        )

        return record.mission