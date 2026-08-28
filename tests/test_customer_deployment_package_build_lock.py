"""
TODOBA Customer Deployment Package Build Lock Tests

Proof:
- lock manager requires a Path
- one deployment lock can be acquired and released
- release allows reacquisition
- different deployment locks coexist
- context manager releases normally
- deterministic lock file exposes no raw deployment identity
- persistent lock file remains zero-byte
- malformed lock material fails closed
- second process is blocked for the same deployment
- process crash releases the Windows OS lock
- different deployment remains independently lockable
- owner uses msvcrt with no external/time-based lease system
- owner performs no lock-file initialization writes

All filesystem state is isolated beneath pytest tmp_path.
"""

import ast
from pathlib import Path
import subprocess
import sys
import time

import pytest

from backend.commercial.customer_deployment_package_build_lock import (
    CustomerDeploymentPackageBuildLockManager,
)


DEPLOYMENT_A = "deployment-build-lock-a"
DEPLOYMENT_B = "deployment-build-lock-b"


def start_holder(
    *,
    tmp_path: Path,
    lock_root: Path,
    deployment_id: str,
) -> tuple[
    subprocess.Popen,
    Path,
]:
    script = (
        tmp_path
        / (
            "hold_"
            + deployment_id
            + ".py"
        )
    )

    ready = (
        tmp_path
        / (
            "ready_"
            + deployment_id
            + ".txt"
        )
    )

    script.write_text(
        """
from pathlib import Path
import sys
import time

sys.path.insert(
    0,
    str(
        Path.cwd()
    ),
)

from backend.commercial.customer_deployment_package_build_lock import (
    CustomerDeploymentPackageBuildLockManager,
)

lock_root = Path(
    sys.argv[1]
)

deployment_id = (
    sys.argv[2]
)

ready_path = Path(
    sys.argv[3]
)

manager = (
    CustomerDeploymentPackageBuildLockManager(
        lock_root
    )
)

lock = manager.acquire(
    deployment_id=deployment_id
)

if lock is None:
    raise SystemExit(3)

ready_path.write_text(
    "ACQUIRED",
    encoding="utf-8",
)

time.sleep(
    60
)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [
            sys.executable,
            str(
                script
            ),
            str(
                lock_root
            ),
            deployment_id,
            str(
                ready
            ),
        ],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = (
        time.monotonic()
        + 5.0
    )

    while (
        time.monotonic()
        < deadline
    ):
        if ready.is_file():
            return (
                process,
                ready,
            )

        if process.poll() is not None:
            stdout, stderr = (
                process.communicate()
            )

            pytest.fail(
                "Holder process exited before acquiring "
                f"lock.\nstdout={stdout}\nstderr={stderr}"
            )

        time.sleep(
            0.05
        )

    process.kill()
    process.wait(
        timeout=5
    )

    stdout, stderr = (
        process.communicate()
    )

    pytest.fail(
        "Timed out waiting for holder process.\n"
        f"stdout={stdout}\nstderr={stderr}"
    )


def stop_holder(
    process: subprocess.Popen,
) -> None:
    if process.poll() is None:
        process.kill()

    process.wait(
        timeout=5
    )


def test_manager_requires_path() -> None:
    with pytest.raises(
        TypeError,
        match="lock_root must be Path",
    ):
        CustomerDeploymentPackageBuildLockManager(
            "not-a-path"
        )


def test_acquire_and_release_allows_reacquisition(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "locks"
    )

    manager = (
        CustomerDeploymentPackageBuildLockManager(
            root
        )
    )

    first = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert first is not None
    assert not first.released

    first.release()

    assert first.released

    # release() must be idempotent.
    first.release()

    second = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert second is not None

    second.release()


def test_different_deployments_can_hold_locks_together(
    tmp_path: Path,
) -> None:
    manager = (
        CustomerDeploymentPackageBuildLockManager(
            tmp_path
            / "locks"
        )
    )

    first = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    second = manager.acquire(
        deployment_id=DEPLOYMENT_B
    )

    assert first is not None
    assert second is not None

    try:
        assert (
            first.lock_path
            != second.lock_path
        )
    finally:
        first.release()
        second.release()


def test_context_manager_releases_lock(
    tmp_path: Path,
) -> None:
    manager = (
        CustomerDeploymentPackageBuildLockManager(
            tmp_path
            / "locks"
        )
    )

    lock = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert lock is not None

    with lock as acquired:
        assert acquired is lock
        assert not lock.released

    assert lock.released

    retry = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert retry is not None
    retry.release()


def test_lock_file_is_deterministic_non_secret_and_empty(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "locks"
    )

    manager = (
        CustomerDeploymentPackageBuildLockManager(
            root
        )
    )

    expected_path = manager.lock_path(
        deployment_id=DEPLOYMENT_A
    )

    assert (
        DEPLOYMENT_A
        not in expected_path.name
    )

    assert expected_path.name.startswith(
        "build-lock-"
    )

    assert expected_path.name.endswith(
        ".lock"
    )

    lock = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert lock is not None

    try:
        assert (
            lock.lock_path
            == expected_path
        )

        assert expected_path.is_file()

        # stat() remains safe while the Windows byte range
        # is locked by this process.
        assert (
            expected_path.stat().st_size
            == 0
        )
    finally:
        lock.release()

    assert (
        expected_path.read_bytes()
        == b""
    )


def test_malformed_lock_file_fails_closed(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "locks"
    )

    manager = (
        CustomerDeploymentPackageBuildLockManager(
            root
        )
    )

    root.mkdir()

    lock_path = manager.lock_path(
        deployment_id=DEPLOYMENT_A
    )

    lock_path.write_bytes(
        b"XX"
    )

    with pytest.raises(
        RuntimeError,
        match="must remain empty",
    ):
        manager.acquire(
            deployment_id=DEPLOYMENT_A
        )


def test_second_process_is_blocked_and_crash_releases_lock(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "locks"
    )

    holder, _ = start_holder(
        tmp_path=tmp_path,
        lock_root=root,
        deployment_id=DEPLOYMENT_A,
    )

    manager = (
        CustomerDeploymentPackageBuildLockManager(
            root
        )
    )

    try:
        blocked = manager.acquire(
            deployment_id=DEPLOYMENT_A
        )

        assert blocked is None

    finally:
        # Forceful termination simulates a package build
        # worker crash without normal release().
        stop_holder(
            holder
        )

    recovered = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert recovered is not None

    recovered.release()


def test_other_deployment_can_lock_while_process_holds_first(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "locks"
    )

    holder, _ = start_holder(
        tmp_path=tmp_path,
        lock_root=root,
        deployment_id=DEPLOYMENT_A,
    )

    manager = (
        CustomerDeploymentPackageBuildLockManager(
            root
        )
    )

    second = None

    try:
        second = manager.acquire(
            deployment_id=DEPLOYMENT_B
        )

        assert second is not None

    finally:
        if second is not None:
            second.release()

        stop_holder(
            holder
        )


def test_released_lock_cannot_be_reentered(
    tmp_path: Path,
) -> None:
    manager = (
        CustomerDeploymentPackageBuildLockManager(
            tmp_path
            / "locks"
        )
    )

    lock = manager.acquire(
        deployment_id=DEPLOYMENT_A
    )

    assert lock is not None

    lock.release()

    with pytest.raises(
        RuntimeError,
        match="already been released",
    ):
        lock.__enter__()


def test_owner_uses_zero_byte_windows_os_lock_only() -> None:
    owner_path = Path(
        "backend/commercial/"
        "customer_deployment_package_build_lock.py"
    )

    source = owner_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imported_modules = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_modules.add(
                    node.module
                )

    assert "msvcrt" in imported_modules
    assert "filelock" not in imported_modules
    assert "portalocker" not in imported_modules
    assert "os" not in imported_modules

    names = {
        node.id
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Name,
        )
    }

    assert "datetime" not in names
    assert "timedelta" not in names

    attributes = {
        node.attr
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Attribute,
        )
    }

    assert "LK_NBLCK" in attributes
    assert "LK_UNLCK" in attributes

    # The zero-byte owner must never initialize, rewrite,
    # replace or delete its persistent lock file.
    forbidden_calls = {
        "write",
        "write_bytes",
        "write_text",
        "fsync",
        "replace",
        "unlink",
        "remove",
    }

    actual_calls = {
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
    }

    assert (
        forbidden_calls
        .isdisjoint(
            actual_calls
        )
    )

    assert "_ensure_lock_file" not in source

    # No commercial state or secret owner may leak into
    # this synchronization primitive.
    for forbidden in (
        "CustomerDeploymentSecrets",
        "account_fingerprint",
        "customer_id",
        "artifact_sha256",
        "artifact_size_bytes",
        "expires_at",
        "worker_id",
    ):
        assert forbidden not in source
