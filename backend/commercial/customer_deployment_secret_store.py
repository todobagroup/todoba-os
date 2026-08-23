"""
TODOBA Customer Deployment Secret Store

Owns durable encrypted secret material for customer deployments.

Responsibilities:
- persist deployment secret material encrypted at rest
- protect secret integrity with authenticated encryption
- restore deployment secrets across Cloud restarts
- accept identical registration idempotently
- reject conflicting secret replacement
- persist durable state before advancing in-memory state

Security model:
- AES-256-GCM authenticated encryption
- one random 96-bit nonce per encrypted deployment record
- deployment identity is authenticated as associated data
- master encryption key is supplied by composition
- master encryption key is never persisted by this store

This component does not:
- generate the master encryption key
- read environment variables
- own customer identity
- own Trusted Agent identity
- own MT5 account bindings
- expose secrets through serialization APIs
- rotate or revoke secrets
- execute trading actions
"""

from dataclasses import dataclass
import base64
import binascii
import hmac
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


STORE_VERSION = 1
_NONCE_BYTES = 12
_MASTER_KEY_BYTES = 32
_AAD_PREFIX = (
    "TODOBA-CUSTOMER-DEPLOYMENT-SECRET-STORE"
)


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerDeploymentSecrets:
    """
    Secret material owned by one customer deployment.

    Secrets intentionally do not appear in repr().
    """

    deployment_id: str
    agent_secret: str
    execution_mission_signing_secret: str
    control_mission_signing_secret: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "deployment_id",
            self._normalize_required_string(
                self.deployment_id,
                name="deployment_id",
            ),
        )

        object.__setattr__(
            self,
            "agent_secret",
            self._validate_required_secret(
                self.agent_secret,
                name="agent_secret",
            ),
        )

        object.__setattr__(
            self,
            "execution_mission_signing_secret",
            self._validate_required_secret(
                self.execution_mission_signing_secret,
                name=(
                    "execution_mission_signing_secret"
                ),
            ),
        )

        object.__setattr__(
            self,
            "control_mission_signing_secret",
            self._validate_required_secret(
                self.control_mission_signing_secret,
                name=(
                    "control_mission_signing_secret"
                ),
            ),
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerDeploymentSecrets("
            f"deployment_id={self.deployment_id!r}, "
            "secret_material=<redacted>)"
        )

    def same_secret_material(
        self,
        other: object,
    ) -> bool:
        if not isinstance(
            other,
            CustomerDeploymentSecrets,
        ):
            return False

        if (
            self.deployment_id
            != other.deployment_id
        ):
            return False

        return (
            hmac.compare_digest(
                self.agent_secret.encode("utf-8"),
                other.agent_secret.encode("utf-8"),
            )
            and hmac.compare_digest(
                self.execution_mission_signing_secret.encode(
                    "utf-8"
                ),
                other.execution_mission_signing_secret.encode(
                    "utf-8"
                ),
            )
            and hmac.compare_digest(
                self.control_mission_signing_secret.encode(
                    "utf-8"
                ),
                other.control_mission_signing_secret.encode(
                    "utf-8"
                ),
            )
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

    @staticmethod
    def _validate_required_secret(
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

        if value == "":
            raise ValueError(
                f"{name} is required."
            )

        return value


class CustomerDeploymentSecretStore:
    """
    Durable encrypted store for customer deployment secrets.

    Durable identity:
        deployment_id

    Durable plaintext outside encryption:
        deployment_id
        nonce
        ciphertext

    Secret plaintext exists only in process memory and
    transient encryption/decryption buffers.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        master_key: bytes,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        if not isinstance(
            master_key,
            bytes,
        ):
            raise TypeError(
                "master_key must be bytes."
            )

        if (
            len(master_key)
            != _MASTER_KEY_BYTES
        ):
            raise ValueError(
                "master_key must contain exactly "
                "32 bytes."
            )

        self.storage_path = storage_path
        self._master_key = bytes(
            master_key
        )
        self._cipher = AESGCM(
            self._master_key
        )

        self._secrets: dict[
            str,
            CustomerDeploymentSecrets,
        ] = {}

        self._ready = False

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        """
        Explicitly initialize a new empty secret store.

        Missing durable storage is never silently treated
        as initialized customer secret state.
        """

        if self._ready:
            return

        if self.storage_path.exists():
            self._restore_from_disk()
            return

        self._write_secrets(
            {}
        )

        self._secrets = {}
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        secrets: CustomerDeploymentSecrets,
    ) -> CustomerDeploymentSecrets:
        """
        Register encrypted secret material for one deployment.

        Rules:
        - first registration is accepted
        - identical retry is idempotent
        - conflicting replacement is rejected
        - durable write happens before RAM advances
        """

        self._require_ready()

        if not isinstance(
            secrets,
            CustomerDeploymentSecrets,
        ):
            raise TypeError(
                "CustomerDeploymentSecretStore requires "
                "CustomerDeploymentSecrets."
            )

        existing = self._secrets.get(
            secrets.deployment_id
        )

        if existing is not None:
            if not existing.same_secret_material(
                secrets
            ):
                raise ValueError(
                    "Customer deployment secrets are "
                    "already registered with different "
                    "secret material."
                )

            return existing

        candidate = dict(
            self._secrets
        )

        candidate[
            secrets.deployment_id
        ] = secrets

        self._write_secrets(
            candidate
        )

        self._secrets = candidate

        return secrets

    def get(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentSecrets | None:
        self._require_ready()

        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        return self._secrets.get(
            normalized_deployment_id
        )

    def all(
        self,
    ) -> tuple[
        CustomerDeploymentSecrets,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._secrets[
                deployment_id
            ]
            for deployment_id in sorted(
                self._secrets
            )
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._secrets
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer deployment secret store "
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

    @staticmethod
    def _build_associated_data(
        *,
        deployment_id: str,
    ) -> bytes:
        return (
            f"{_AAD_PREFIX}"
            f"|v{STORE_VERSION}"
            f"|{deployment_id}"
        ).encode(
            "utf-8"
        )

    def _encrypt_secrets(
        self,
        secrets: CustomerDeploymentSecrets,
    ) -> tuple[
        bytes,
        bytes,
    ]:
        plaintext_payload = {
            "deployment_id": (
                secrets.deployment_id
            ),
            "agent_secret": (
                secrets.agent_secret
            ),
            "execution_mission_signing_secret": (
                secrets.execution_mission_signing_secret
            ),
            "control_mission_signing_secret": (
                secrets.control_mission_signing_secret
            ),
        }

        plaintext = json.dumps(
            plaintext_payload,
            separators=(
                ",",
                ":",
            ),
            sort_keys=True,
        ).encode(
            "utf-8"
        )

        nonce = os.urandom(
            _NONCE_BYTES
        )

        associated_data = (
            self._build_associated_data(
                deployment_id=(
                    secrets.deployment_id
                ),
            )
        )

        ciphertext = self._cipher.encrypt(
            nonce,
            plaintext,
            associated_data,
        )

        return (
            nonce,
            ciphertext,
        )

    def _decrypt_secrets(
        self,
        *,
        deployment_id: str,
        nonce: bytes,
        ciphertext: bytes,
    ) -> CustomerDeploymentSecrets:
        associated_data = (
            self._build_associated_data(
                deployment_id=deployment_id,
            )
        )

        try:
            plaintext = self._cipher.decrypt(
                nonce,
                ciphertext,
                associated_data,
            )
        except InvalidTag as error:
            raise ValueError(
                "Customer deployment secret "
                "authentication failed."
            ) from error

        try:
            payload = json.loads(
                plaintext.decode(
                    "utf-8"
                )
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError(
                "Customer deployment secret "
                "plaintext is invalid."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer deployment secret "
                "plaintext must be an object."
            )

        expected_fields = {
            "deployment_id",
            "agent_secret",
            "execution_mission_signing_secret",
            "control_mission_signing_secret",
        }

        if (
            set(payload.keys())
            != expected_fields
        ):
            raise ValueError(
                "Customer deployment secret "
                "plaintext has invalid fields."
            )

        restored = (
            CustomerDeploymentSecrets(
                deployment_id=payload[
                    "deployment_id"
                ],
                agent_secret=payload[
                    "agent_secret"
                ],
                execution_mission_signing_secret=(
                    payload[
                        "execution_mission_signing_secret"
                    ]
                ),
                control_mission_signing_secret=(
                    payload[
                        "control_mission_signing_secret"
                    ]
                ),
            )
        )

        if (
            restored.deployment_id
            != deployment_id
        ):
            raise ValueError(
                "Customer deployment secret identity "
                "does not match encrypted record."
            )

        return restored

    def _restore_from_disk(
        self,
    ) -> None:
        try:
            payload = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8",
                )
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "Customer deployment secret store "
                "contains invalid JSON."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer deployment secret store "
                "payload must be an object."
            )

        if (
            set(payload.keys())
            != {
                "version",
                "deployments",
            }
        ):
            raise ValueError(
                "Customer deployment secret store "
                "payload has invalid fields."
            )

        version = payload[
            "version"
        ]

        if version != STORE_VERSION:
            raise ValueError(
                "Unsupported customer deployment "
                "secret store version."
            )

        items = payload[
            "deployments"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer deployment secret store "
                "deployments must be a list."
            )

        restored: dict[
            str,
            CustomerDeploymentSecrets,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer deployment secret record "
                    "must be an object."
                )

            if (
                set(item.keys())
                != {
                    "deployment_id",
                    "nonce",
                    "ciphertext",
                }
            ):
                raise ValueError(
                    "Customer deployment secret record "
                    "has invalid fields."
                )

            deployment_id = (
                self._normalize_required_string(
                    item[
                        "deployment_id"
                    ],
                    name="deployment_id",
                )
            )

            if deployment_id in restored:
                raise ValueError(
                    "Duplicate customer deployment "
                    "secret record."
                )

            nonce_text = item[
                "nonce"
            ]

            ciphertext_text = item[
                "ciphertext"
            ]

            if not isinstance(
                nonce_text,
                str,
            ):
                raise ValueError(
                    "Customer deployment secret nonce "
                    "must be encoded text."
                )

            if not isinstance(
                ciphertext_text,
                str,
            ):
                raise ValueError(
                    "Customer deployment secret "
                    "ciphertext must be encoded text."
                )

            try:
                nonce = base64.b64decode(
                    nonce_text,
                    validate=True,
                )

                ciphertext = (
                    base64.b64decode(
                        ciphertext_text,
                        validate=True,
                    )
                )
            except (
                binascii.Error,
                ValueError,
            ) as error:
                raise ValueError(
                    "Customer deployment secret record "
                    "contains invalid base64."
                ) from error

            if (
                len(nonce)
                != _NONCE_BYTES
            ):
                raise ValueError(
                    "Customer deployment secret nonce "
                    "has invalid length."
                )

            if (
                len(ciphertext)
                < 16
            ):
                raise ValueError(
                    "Customer deployment secret "
                    "ciphertext is invalid."
                )

            restored_secrets = (
                self._decrypt_secrets(
                    deployment_id=deployment_id,
                    nonce=nonce,
                    ciphertext=ciphertext,
                )
            )

            restored[
                deployment_id
            ] = restored_secrets

        self._secrets = restored
        self._ready = True

    def _write_secrets(
        self,
        secrets_by_deployment: dict[
            str,
            CustomerDeploymentSecrets,
        ],
    ) -> None:
        items = []

        for deployment_id in sorted(
            secrets_by_deployment
        ):
            secrets = (
                secrets_by_deployment[
                    deployment_id
                ]
            )

            if (
                secrets.deployment_id
                != deployment_id
            ):
                raise ValueError(
                    "Customer deployment secret "
                    "dictionary identity mismatch."
                )

            nonce, ciphertext = (
                self._encrypt_secrets(
                    secrets
                )
            )

            items.append(
                {
                    "deployment_id": (
                        deployment_id
                    ),
                    "nonce": (
                        base64.b64encode(
                            nonce
                        ).decode(
                            "ascii"
                        )
                    ),
                    "ciphertext": (
                        base64.b64encode(
                            ciphertext
                        ).decode(
                            "ascii"
                        )
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "deployments": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = Path(
            f"{self.storage_path}.tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file_handle:
            json.dump(
                payload,
                file_handle,
                indent=2,
                sort_keys=True,
            )

            file_handle.write(
                "\n"
            )

            file_handle.flush()

            os.fsync(
                file_handle.fileno()
            )

        os.replace(
            temporary_path,
            self.storage_path,
        )