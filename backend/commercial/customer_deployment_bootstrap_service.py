"""
TODOBA Customer Deployment Bootstrap Service

Creates a stable commercial enrollment candidate without
requiring a customer or operator to choose internal TODOBA
deployment identities or secret material.

Bootstrap responsibilities:
- accept customer identity and MT5 account fingerprint
- accept an enrollment request id used for retry safety
- generate deployment and Trusted Agent identities
- generate independent cryptographic secret domains
- durably remember generated non-secret bootstrap identity
- recover the same candidate after process restart
- reuse existing encrypted secret material after partial work
- prepare deployment material through Customer Deployment
  Enrollment Service
- activate deployment only through an explicit activation
  step
- prevent duplicate enrollment of the same MT5 account

Bootstrap persistence never stores plaintext deployment
secret material.

The raw MT5 account fingerprint remains authoritative only
in TrustedAgentAccountBindingStore. Bootstrap persistence
stores only a SHA-256 digest so a conflicting retry can be
rejected without creating a second account-binding owner.

This component does not:
- authenticate a customer
- expose an HTTP API
- build or distribute an EX5 artifact
- purchase or migrate MetaTrader Virtual Hosting
- own subscription or entitlement
- rotate or revoke deployed credentials
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets as secure_random
import threading
import uuid

from backend.commercial.customer_deployment_enrollment_service import (
    CustomerDeploymentEnrollmentResult,
    CustomerDeploymentEnrollmentService,
    CustomerDeploymentPreparationResult,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
    CustomerDeploymentSecretStore,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


STORE_VERSION = 1

_ID_GENERATION_ATTEMPTS = 64
_SECRET_RANDOM_BYTES = 48


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerDeploymentBootstrapRecord:
    """
    Durable non-secret identity for one bootstrap request.

    account_fingerprint_digest is validation evidence only.
    The authoritative raw account fingerprint remains in
    TrustedAgentAccountBindingStore.
    """

    enrollment_request_id: str
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint_digest: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "enrollment_request_id",
            "customer_id",
            "deployment_id",
            "agent_id",
        ):
            object.__setattr__(
                self,
                name,
                self._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        digest = (
            self._normalize_required_string(
                self.account_fingerprint_digest,
                name=(
                    "account_fingerprint_digest"
                ),
            )
        ).lower()

        if (
            len(digest) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in digest
            )
        ):
            raise ValueError(
                "account_fingerprint_digest must be "
                "a SHA-256 hexadecimal digest."
            )

        object.__setattr__(
            self,
            "account_fingerprint_digest",
            digest,
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerDeploymentBootstrapRecord("
            f"enrollment_request_id="
            f"{self.enrollment_request_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"deployment_id={self.deployment_id!r}, "
            f"agent_id={self.agent_id!r}, "
            "account_fingerprint_digest=<redacted>)"
        )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerDeploymentBootstrapPreparationResult:
    """
    Internal prepared bootstrap candidate.

    This result contains the material required by the secure
    deployment packaging layer but does not mean the
    deployment is active.

    Secret material and raw account fingerprint are never
    emitted by repr().
    """

    enrollment_request_id: str
    deployment: CustomerDeployment
    secrets: CustomerDeploymentSecrets
    account_fingerprint: str

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerDeploymentBootstrapPreparationResult("
            f"enrollment_request_id="
            f"{self.enrollment_request_id!r}, "
            f"deployment={self.deployment!r}, "
            "account_fingerprint=<redacted>, "
            "secret_material=<redacted>)"
        )

@dataclass(
    frozen=True,
    repr=False,
)
class CustomerDeploymentBootstrapResult:
    """
    Internal bootstrap result.

    Secret material is available to the later secure
    deployment packaging layer but is never emitted by
    repr().
    """

    enrollment_request_id: str
    deployment: CustomerDeployment
    secrets: CustomerDeploymentSecrets
    account_fingerprint: str
    projected_deployment_count: int

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerDeploymentBootstrapResult("
            f"enrollment_request_id="
            f"{self.enrollment_request_id!r}, "
            f"deployment={self.deployment!r}, "
            "account_fingerprint=<redacted>, "
            "secret_material=<redacted>, "
            f"projected_deployment_count="
            f"{self.projected_deployment_count!r})"
        )


class CustomerDeploymentBootstrapStore:
    """
    Durable non-secret bootstrap idempotency owner.

    Identity:
        enrollment_request_id

    Additional uniqueness:
        deployment_id
        agent_id
        account_fingerprint_digest
    """

    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path

        self._records: dict[
            str,
            CustomerDeploymentBootstrapRecord,
        ] = {}

        self._ready = False

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        if self._ready:
            return

        if self.storage_path.exists():
            self._restore_from_disk()
            return

        self._write_records(
            {}
        )

        self._records = {}
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerDeploymentBootstrapRecord,
    ) -> CustomerDeploymentBootstrapRecord:
        self._require_ready()

        if not isinstance(
            record,
            CustomerDeploymentBootstrapRecord,
        ):
            raise TypeError(
                "CustomerDeploymentBootstrapStore "
                "requires "
                "CustomerDeploymentBootstrapRecord."
            )

        existing = self._records.get(
            record.enrollment_request_id
        )

        if existing is not None:
            if existing != record:
                raise ValueError(
                    "Enrollment request is already "
                    "registered with different bootstrap "
                    "identity."
                )

            return existing

        for stored in self._records.values():
            if (
                stored.deployment_id
                == record.deployment_id
            ):
                raise ValueError(
                    "Bootstrap deployment identity is "
                    "already assigned."
                )

            if (
                stored.agent_id
                == record.agent_id
            ):
                raise ValueError(
                    "Bootstrap Trusted Agent identity is "
                    "already assigned."
                )

            if (
                stored.account_fingerprint_digest
                == record.account_fingerprint_digest
            ):
                raise ValueError(
                    "MT5 account already has a bootstrap "
                    "identity."
                )

        candidate = dict(
            self._records
        )

        candidate[
            record.enrollment_request_id
        ] = record

        self._write_records(
            candidate
        )

        self._records = candidate

        return record

    def get(
        self,
        *,
        enrollment_request_id: str,
    ) -> CustomerDeploymentBootstrapRecord | None:
        self._require_ready()

        normalized = (
            self._normalize_required_string(
                enrollment_request_id,
                name="enrollment_request_id",
            )
        )

        return self._records.get(
            normalized
        )

    def find_by_account_digest(
        self,
        *,
        account_fingerprint_digest: str,
    ) -> CustomerDeploymentBootstrapRecord | None:
        self._require_ready()

        normalized = (
            self._normalize_required_string(
                account_fingerprint_digest,
                name=(
                    "account_fingerprint_digest"
                ),
            )
        ).lower()

        for record in self._records.values():
            if (
                record.account_fingerprint_digest
                == normalized
            ):
                return record

        return None

    def all(
        self,
    ) -> tuple[
        CustomerDeploymentBootstrapRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                request_id
            ]
            for request_id in sorted(
                self._records
            )
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._records
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer deployment bootstrap store "
                "is not initialized."
            )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized

    def _restore_from_disk(
        self,
    ) -> None:
        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer deployment bootstrap payload "
                "must be an object."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported customer deployment "
                "bootstrap store version."
            )

        items = payload.get(
            "records"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer deployment bootstrap records "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerDeploymentBootstrapRecord,
        ] = {}

        seen_deployment_ids: set[str] = set()
        seen_agent_ids: set[str] = set()
        seen_account_digests: set[str] = set()

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer deployment bootstrap item "
                    "must be an object."
                )

            required_keys = {
                "enrollment_request_id",
                "customer_id",
                "deployment_id",
                "agent_id",
                "account_fingerprint_digest",
            }

            if set(
                item
            ) != required_keys:
                raise ValueError(
                    "Customer deployment bootstrap item "
                    "has invalid fields."
                )

            record = (
                CustomerDeploymentBootstrapRecord(
                    enrollment_request_id=item[
                        "enrollment_request_id"
                    ],
                    customer_id=item[
                        "customer_id"
                    ],
                    deployment_id=item[
                        "deployment_id"
                    ],
                    agent_id=item[
                        "agent_id"
                    ],
                    account_fingerprint_digest=item[
                        "account_fingerprint_digest"
                    ],
                )
            )

            if (
                record.enrollment_request_id
                in restored
            ):
                raise ValueError(
                    "Duplicate enrollment request."
                )

            if (
                record.deployment_id
                in seen_deployment_ids
            ):
                raise ValueError(
                    "Duplicate bootstrap deployment "
                    "identity."
                )

            if (
                record.agent_id
                in seen_agent_ids
            ):
                raise ValueError(
                    "Duplicate bootstrap Trusted Agent "
                    "identity."
                )

            if (
                record.account_fingerprint_digest
                in seen_account_digests
            ):
                raise ValueError(
                    "Duplicate bootstrap MT5 account."
                )

            restored[
                record.enrollment_request_id
            ] = record

            seen_deployment_ids.add(
                record.deployment_id
            )

            seen_agent_ids.add(
                record.agent_id
            )

            seen_account_digests.add(
                record.account_fingerprint_digest
            )

        self._records = restored
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerDeploymentBootstrapRecord,
        ],
    ) -> None:
        items = []

        for request_id in sorted(
            records
        ):
            record = records[
                request_id
            ]

            items.append(
                {
                    "enrollment_request_id": (
                        record.enrollment_request_id
                    ),
                    "customer_id": (
                        record.customer_id
                    ),
                    "deployment_id": (
                        record.deployment_id
                    ),
                    "agent_id": (
                        record.agent_id
                    ),
                    "account_fingerprint_digest": (
                        record
                        .account_fingerprint_digest
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "records": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                f"{self.storage_path.name}.tmp"
            )
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()

            raise


class CustomerDeploymentBootstrapService:
    """
    Generate or recover one stable enrollment candidate.

    The bootstrap record is persisted before any secret or
    commercial deployment mutation so retry can recover the
    same deployment_id and agent_id after interruption.
    """

    def __init__(
        self,
        *,
        bootstrap_store: CustomerDeploymentBootstrapStore,
        deployment_registry: CustomerDeploymentRegistry,
        secret_store: CustomerDeploymentSecretStore,
        account_binding_store: (
            TrustedAgentAccountBindingStore
        ),
        enrollment_service: (
            CustomerDeploymentEnrollmentService
        ),
    ) -> None:
        if not isinstance(
            bootstrap_store,
            CustomerDeploymentBootstrapStore,
        ):
            raise TypeError(
                "bootstrap_store must be "
                "CustomerDeploymentBootstrapStore."
            )

        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not isinstance(
            secret_store,
            CustomerDeploymentSecretStore,
        ):
            raise TypeError(
                "secret_store must be "
                "CustomerDeploymentSecretStore."
            )

        if not isinstance(
            account_binding_store,
            TrustedAgentAccountBindingStore,
        ):
            raise TypeError(
                "account_binding_store must be "
                "TrustedAgentAccountBindingStore."
            )

        if not isinstance(
            enrollment_service,
            CustomerDeploymentEnrollmentService,
        ):
            raise TypeError(
                "enrollment_service must be "
                "CustomerDeploymentEnrollmentService."
            )

        self._bootstrap_store = (
            bootstrap_store
        )

        self._deployment_registry = (
            deployment_registry
        )

        self._secret_store = (
            secret_store
        )

        self._account_binding_store = (
            account_binding_store
        )

        self._enrollment_service = (
            enrollment_service
        )

        self._lock = threading.RLock()

    def bootstrap(
        self,
        *,
        enrollment_request_id: str,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerDeploymentBootstrapResult:
        """
        Create or recover and activate one complete customer
        deployment bootstrap.

        Backward-compatible contract:

            bootstrap()
                = prepare_bootstrap()
                + activate_bootstrap()

        Existing offline onboarding callers therefore keep
        their original complete-bootstrap behavior.
        """

        return self.activate_bootstrap(
            enrollment_request_id=(
                enrollment_request_id
            ),
            customer_id=customer_id,
            account_fingerprint=(
                account_fingerprint
            ),
        )

    def prepare_bootstrap(
        self,
        *,
        enrollment_request_id: str,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerDeploymentBootstrapPreparationResult:
        """
        Create or recover one durable bootstrap candidate
        without activating its commercial deployment.

        A retry with the same enrollment request returns the
        same identities and secret material.

        A second request for the same customer/account also
        converges on the existing bootstrap.

        Cross-customer reuse of an already enrolled or
        reserved MT5 account fails closed.

        Preparation stages deployment secrets and Trusted
        Agent account binding through the Enrollment Service
        but does not cross CustomerDeploymentRegistry, the
        durable activation barrier.
        """

        normalized_request_id = (
            self._normalize_required_string(
                enrollment_request_id,
                name="enrollment_request_id",
            )
        )

        normalized_customer_id = (
            self._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        normalized_account_fingerprint = (
            self._normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        account_digest = (
            self._account_fingerprint_digest(
                normalized_account_fingerprint
            )
        )

        with self._lock:
            self._require_sources_ready()

            record = (
                self._resolve_existing_record(
                    enrollment_request_id=(
                        normalized_request_id
                    ),
                    customer_id=(
                        normalized_customer_id
                    ),
                    account_fingerprint=(
                        normalized_account_fingerprint
                    ),
                    account_fingerprint_digest=(
                        account_digest
                    ),
                )
            )

            if record is None:
                record = (
                    self._create_bootstrap_record(
                        enrollment_request_id=(
                            normalized_request_id
                        ),
                        customer_id=(
                            normalized_customer_id
                        ),
                        account_fingerprint=(
                            normalized_account_fingerprint
                        ),
                        account_fingerprint_digest=(
                            account_digest
                        ),
                    )
                )

            deployment = CustomerDeployment(
                customer_id=record.customer_id,
                deployment_id=(
                    record.deployment_id
                ),
                agent_id=record.agent_id,
            )

            stored_secrets = (
                self._secret_store.get(
                    deployment_id=(
                        record.deployment_id
                    )
                )
            )

            if stored_secrets is None:
                deployment_secrets = (
                    self._generate_secrets(
                        deployment_id=(
                            record.deployment_id
                        )
                    )
                )
            else:
                deployment_secrets = (
                    stored_secrets
                )

            preparation_result = (
                self._enrollment_service.prepare(
                    deployment=deployment,
                    secrets=deployment_secrets,
                    account_fingerprint=(
                        normalized_account_fingerprint
                    ),
                )
            )

            return self._build_preparation_result(
                record=record,
                secrets=deployment_secrets,
                account_fingerprint=(
                    normalized_account_fingerprint
                ),
                preparation_result=(
                    preparation_result
                ),
            )

    def activate_bootstrap(
        self,
        *,
        enrollment_request_id: str,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerDeploymentBootstrapResult:
        """
        Activate one bootstrap candidate using its stable
        authoritative request/customer/account inputs.

        Preparation is rerun idempotently first so activation
        remains recoverable after process restart or a crash
        between preparation and activation.
        """

        with self._lock:
            preparation = self.prepare_bootstrap(
                enrollment_request_id=(
                    enrollment_request_id
                ),
                customer_id=customer_id,
                account_fingerprint=(
                    account_fingerprint
                ),
            )

            record = (
                self._bootstrap_store.get(
                    enrollment_request_id=(
                        preparation.enrollment_request_id
                    )
                )
            )

            if record is None:
                raise RuntimeError(
                    "Prepared customer deployment bootstrap "
                    "identity is missing."
                )

            if (
                record.deployment_id
                != preparation.deployment.deployment_id
                or record.agent_id
                != preparation.deployment.agent_id
                or record.customer_id
                != preparation.deployment.customer_id
            ):
                raise RuntimeError(
                    "Prepared customer deployment bootstrap "
                    "identity does not match durable record."
                )

            enrollment_result = (
                self._enrollment_service.activate(
                    deployment=(
                        preparation.deployment
                    ),
                    secrets=preparation.secrets,
                    account_fingerprint=(
                        preparation.account_fingerprint
                    ),
                )
            )

            return self._build_result(
                record=record,
                secrets=preparation.secrets,
                account_fingerprint=(
                    preparation.account_fingerprint
                ),
                enrollment_result=(
                    enrollment_result
                ),
            )
    def _resolve_existing_record(
        self,
        *,
        enrollment_request_id: str,
        customer_id: str,
        account_fingerprint: str,
        account_fingerprint_digest: str,
    ) -> CustomerDeploymentBootstrapRecord | None:
        request_record = (
            self._bootstrap_store.get(
                enrollment_request_id=(
                    enrollment_request_id
                )
            )
        )

        if request_record is not None:
            self._validate_record_request(
                record=request_record,
                customer_id=customer_id,
                account_fingerprint_digest=(
                    account_fingerprint_digest
                ),
            )

            return request_record

        account_record = (
            self._bootstrap_store
            .find_by_account_digest(
                account_fingerprint_digest=(
                    account_fingerprint_digest
                )
            )
        )

        if account_record is not None:
            if (
                account_record.customer_id
                != customer_id
            ):
                raise ValueError(
                    "MT5 account is already reserved "
                    "for another customer."
                )

            return account_record

        existing_deployment = (
            self._find_existing_deployment_for_account(
                customer_id=customer_id,
                account_fingerprint=(
                    account_fingerprint
                ),
            )
        )

        if existing_deployment is None:
            return None

        adoption_record = (
            CustomerDeploymentBootstrapRecord(
                enrollment_request_id=(
                    enrollment_request_id
                ),
                customer_id=customer_id,
                deployment_id=(
                    existing_deployment.deployment_id
                ),
                agent_id=(
                    existing_deployment.agent_id
                ),
                account_fingerprint_digest=(
                    account_fingerprint_digest
                ),
            )
        )

        return self._bootstrap_store.register(
            adoption_record
        )

    def _validate_record_request(
        self,
        *,
        record: CustomerDeploymentBootstrapRecord,
        customer_id: str,
        account_fingerprint_digest: str,
    ) -> None:
        if record.customer_id != customer_id:
            raise ValueError(
                "Enrollment request belongs to a "
                "different customer."
            )

        if (
            record.account_fingerprint_digest
            != account_fingerprint_digest
        ):
            raise ValueError(
                "Enrollment request belongs to a "
                "different MT5 account."
            )

    def _find_existing_deployment_for_account(
        self,
        *,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerDeployment | None:
        matched: CustomerDeployment | None = None

        for deployment in (
            self._deployment_registry.all()
        ):
            bound_account = (
                self._account_binding_store
                .get_account_fingerprint(
                    agent_id=deployment.agent_id
                )
            )

            if bound_account is None:
                raise RuntimeError(
                    "Commercial deployment is missing "
                    "its Trusted Agent account binding."
                )

            if (
                self._secret_store.get(
                    deployment_id=(
                        deployment.deployment_id
                    )
                )
                is None
            ):
                raise RuntimeError(
                    "Commercial deployment is missing "
                    "its deployment secret material."
                )

            if (
                bound_account
                != account_fingerprint
            ):
                continue

            if deployment.customer_id != customer_id:
                raise ValueError(
                    "MT5 account is already enrolled "
                    "for another customer."
                )

            if matched is not None:
                raise RuntimeError(
                    "MT5 account is assigned to multiple "
                    "commercial deployments."
                )

            matched = deployment

        return matched

    def _create_bootstrap_record(
        self,
        *,
        enrollment_request_id: str,
        customer_id: str,
        account_fingerprint: str,
        account_fingerprint_digest: str,
    ) -> CustomerDeploymentBootstrapRecord:
        self._reject_existing_account_binding(
            account_fingerprint=(
                account_fingerprint
            ),
        )

        deployment_id, agent_id = (
            self._generate_unique_identity()
        )

        record = (
            CustomerDeploymentBootstrapRecord(
                enrollment_request_id=(
                    enrollment_request_id
                ),
                customer_id=customer_id,
                deployment_id=deployment_id,
                agent_id=agent_id,
                account_fingerprint_digest=(
                    account_fingerprint_digest
                ),
            )
        )

        return self._bootstrap_store.register(
            record
        )

    def _reject_existing_account_binding(
        self,
        *,
        account_fingerprint: str,
    ) -> None:
        # Commercial and bootstrap identities were already
        # resolved before this method is reached.
        #
        # Any remaining authoritative account owner is an
        # orphan/unresolved Trusted Agent binding and must
        # fail closed before a second Agent is generated.
        existing_agent_id = (
            self._account_binding_store
            .get_agent_id_for_account(
                account_fingerprint=(
                    account_fingerprint
                )
            )
        )

        if existing_agent_id is not None:
            raise RuntimeError(
                "MT5 account binding exists without "
                "a resolvable bootstrap identity."
            )

    def _generate_unique_identity(
        self,
    ) -> tuple[
        str,
        str,
    ]:
        bootstrap_records = (
            self._bootstrap_store.all()
        )

        bootstrap_deployment_ids = {
            record.deployment_id
            for record in bootstrap_records
        }

        bootstrap_agent_ids = {
            record.agent_id
            for record in bootstrap_records
        }

        for _ in range(
            _ID_GENERATION_ATTEMPTS
        ):
            deployment_id = (
                f"deployment-{uuid.uuid4().hex}"
            )

            agent_id = (
                f"trusted-agent-{uuid.uuid4().hex}"
            )

            if (
                deployment_id
                in bootstrap_deployment_ids
            ):
                continue

            if (
                agent_id
                in bootstrap_agent_ids
            ):
                continue

            if (
                self._deployment_registry.get(
                    deployment_id=(
                        deployment_id
                    )
                )
                is not None
            ):
                continue

            if (
                self._deployment_registry
                .get_by_agent_id(
                    agent_id=agent_id
                )
                is not None
            ):
                continue

            if (
                self._secret_store.get(
                    deployment_id=(
                        deployment_id
                    )
                )
                is not None
            ):
                continue

            if (
                self._account_binding_store
                .get_account_fingerprint(
                    agent_id=agent_id
                )
                is not None
            ):
                continue

            return (
                deployment_id,
                agent_id,
            )

        raise RuntimeError(
            "Unable to generate unique customer "
            "deployment bootstrap identity."
        )

    @staticmethod
    def _generate_secrets(
        *,
        deployment_id: str,
    ) -> CustomerDeploymentSecrets:
        return CustomerDeploymentSecrets(
            deployment_id=deployment_id,
            agent_secret=(
                secure_random.token_urlsafe(
                    _SECRET_RANDOM_BYTES
                )
            ),
            execution_mission_signing_secret=(
                secure_random.token_urlsafe(
                    _SECRET_RANDOM_BYTES
                )
            ),
            control_mission_signing_secret=(
                secure_random.token_urlsafe(
                    _SECRET_RANDOM_BYTES
                )
            ),
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._bootstrap_store.is_ready():
            raise RuntimeError(
                "Customer deployment bootstrap store "
                "is not initialized."
            )

        if not self._deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is not "
                "initialized for bootstrap."
            )

        if not self._secret_store.is_ready():
            raise RuntimeError(
                "Customer deployment secret store is not "
                "initialized for bootstrap."
            )

        if not self._account_binding_store.is_ready():
            raise RuntimeError(
                "Trusted Agent account binding store is "
                "not initialized for bootstrap."
            )

    @staticmethod
    def _build_preparation_result(
        *,
        record: CustomerDeploymentBootstrapRecord,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
        preparation_result: (
            CustomerDeploymentPreparationResult
        ),
    ) -> CustomerDeploymentBootstrapPreparationResult:
        if (
            preparation_result.deployment.deployment_id
            != record.deployment_id
            or preparation_result.deployment.agent_id
            != record.agent_id
            or preparation_result.deployment.customer_id
            != record.customer_id
        ):
            raise RuntimeError(
                "Prepared enrollment identity does not "
                "match bootstrap identity."
            )

        if (
            preparation_result.account_fingerprint
            != account_fingerprint
        ):
            raise RuntimeError(
                "Prepared enrollment account does not "
                "match bootstrap account."
            )

        return CustomerDeploymentBootstrapPreparationResult(
            enrollment_request_id=(
                record.enrollment_request_id
            ),
            deployment=(
                preparation_result.deployment
            ),
            secrets=secrets,
            account_fingerprint=(
                account_fingerprint
            ),
        )
    @staticmethod
    def _build_result(
        *,
        record: CustomerDeploymentBootstrapRecord,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
        enrollment_result: (
            CustomerDeploymentEnrollmentResult
        ),
    ) -> CustomerDeploymentBootstrapResult:
        return CustomerDeploymentBootstrapResult(
            enrollment_request_id=(
                record.enrollment_request_id
            ),
            deployment=(
                enrollment_result.deployment
            ),
            secrets=secrets,
            account_fingerprint=(
                account_fingerprint
            ),
            projected_deployment_count=(
                enrollment_result
                .projected_deployment_count
            ),
        )

    @staticmethod
    def _account_fingerprint_digest(
        account_fingerprint: str,
    ) -> str:
        return hashlib.sha256(
            account_fingerprint.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized
