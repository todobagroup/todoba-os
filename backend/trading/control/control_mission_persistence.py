"""
TODOBA Control Mission Persistence

Persists control missions to disk.

This component saves and restores
ControlMissionRepository. Delivery, lifecycle tracking,
HTTP transport, and broker control belong elsewhere.
"""

import json
from pathlib import Path

from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)


class ControlMissionPersistence:
    """
    Persist ControlMissionRepository to JSON.
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

    def save(
        self,
        repository: ControlMissionRepository,
    ) -> None:
        if not isinstance(
            repository,
            ControlMissionRepository,
        ):
            raise TypeError(
                "save requires "
                "ControlMissionRepository."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = [
            ControlMissionSerializer.serialize(
                mission
            )
            for mission in repository.all()
        ]

        temporary_path = self.storage_path.with_suffix(
            self.storage_path.suffix + ".tmp"
        )

        temporary_path.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(
            self.storage_path
        )

    def restore(
        self,
        repository: ControlMissionRepository,
    ) -> int:
        if not isinstance(
            repository,
            ControlMissionRepository,
        ):
            raise TypeError(
                "restore requires "
                "ControlMissionRepository."
            )

        if not self.storage_path.exists():
            return 0

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        count = 0

        for item in payload:
            repository.save(
                ControlMissionSerializer.deserialize(
                    item
                )
            )

            count += 1

        return count