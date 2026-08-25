from pathlib import Path

import pytest

from backend.config import (
    BASE_DIR,
    TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
    get_customer_package_root,
)


def test_customer_package_root_requires_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TODOBA_CUSTOMER_PACKAGE_ROOT "
            "is required"
        ),
    ):
        get_customer_package_root()


@pytest.mark.parametrize(
    "configured_value",
    [
        "",
        "   ",
    ],
)
def test_customer_package_root_rejects_empty_environment(
    monkeypatch: pytest.MonkeyPatch,
    configured_value: str,
) -> None:
    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        configured_value,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TODOBA_CUSTOMER_PACKAGE_ROOT "
            "is required"
        ),
    ):
        get_customer_package_root()


def test_customer_package_root_rejects_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        "customer-packages",
    )

    with pytest.raises(
        ValueError,
        match=(
            "TODOBA_CUSTOMER_PACKAGE_ROOT must "
            "be an absolute path"
        ),
    ):
        get_customer_package_root()


@pytest.mark.parametrize(
    "configured_path",
    [
        BASE_DIR,
        BASE_DIR / "customer-packages",
        BASE_DIR / "data" / "customer-packages",
    ],
)
def test_customer_package_root_rejects_repository_paths(
    monkeypatch: pytest.MonkeyPatch,
    configured_path: Path,
) -> None:
    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        str(
            configured_path
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "TODOBA_CUSTOMER_PACKAGE_ROOT must "
            "be outside the repository"
        ),
    ):
        get_customer_package_root()


def test_customer_package_root_accepts_existing_external_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = (
        tmp_path
        / "customer-packages"
    )

    package_root.mkdir()

    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        str(
            package_root
        ),
    )

    result = get_customer_package_root()

    assert result == package_root.resolve()
    assert result.is_dir()


def test_customer_package_root_allows_missing_external_directory_without_creating_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = (
        tmp_path
        / "customer-packages"
    )

    assert not package_root.exists()

    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        str(
            package_root
        ),
    )

    result = get_customer_package_root()

    assert result == package_root.resolve()
    assert not package_root.exists()


def test_customer_package_root_strips_environment_whitespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = (
        tmp_path
        / "customer-packages"
    )

    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        f"  {package_root}  ",
    )

    result = get_customer_package_root()

    assert result == package_root.resolve()


def test_customer_package_root_configuration_does_not_create_filesystem_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = (
        tmp_path
        / "customer-packages"
        / "published"
    )

    assert not package_root.exists()
    assert not package_root.parent.exists()

    monkeypatch.setenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        str(
            package_root
        ),
    )

    get_customer_package_root()

    assert not package_root.exists()
    assert not package_root.parent.exists()
