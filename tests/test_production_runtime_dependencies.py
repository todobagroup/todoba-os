from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

PRODUCTION_REQUIREMENTS = (
    REPOSITORY_ROOT
    / "requirements-production.txt"
)

DEVELOPMENT_REQUIREMENTS = (
    REPOSITORY_ROOT
    / "requirements.txt"
)

EXPECTED_PRODUCTION_REQUIREMENTS = (
    "fastapi==0.141.1",
    "uvicorn==0.53.0",
    "pydantic==2.13.5",
    "python-dotenv==1.2.3",
    "telethon==1.45.0",
    "MetaTrader5==5.0.6180",
    "httpx==0.28.1",
    "cryptography==50.0.1",
)


def _meaningful_lines(
    path: Path,
) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in path.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
    )


def _normalized_package_name(
    requirement: str,
) -> str:
    return (
        requirement.split("==", 1)[0]
        .strip()
        .lower()
        .replace("_", "-")
    )


def test_production_dependency_manifest_exists() -> None:
    assert PRODUCTION_REQUIREMENTS.is_file()


def test_production_dependency_manifest_is_exact_and_pinned() -> None:
    assert (
        _meaningful_lines(
            PRODUCTION_REQUIREMENTS
        )
        == EXPECTED_PRODUCTION_REQUIREMENTS
    )


def test_production_dependency_manifest_excludes_test_tooling() -> None:
    names = {
        _normalized_package_name(line)
        for line in _meaningful_lines(
            PRODUCTION_REQUIREMENTS
        )
    }

    assert "pytest" not in names
    assert "pyinstaller" not in names


def test_development_manifest_keeps_pytest_compatibility() -> None:
    names = {
        _normalized_package_name(line)
        for line in _meaningful_lines(
            DEVELOPMENT_REQUIREMENTS
        )
    }

    assert "pytest" in names


def test_production_dependencies_are_declared_in_development_manifest() -> None:
    development_names = {
        _normalized_package_name(line)
        for line in _meaningful_lines(
            DEVELOPMENT_REQUIREMENTS
        )
    }

    production_names = {
        _normalized_package_name(line)
        for line in EXPECTED_PRODUCTION_REQUIREMENTS
    }

    assert production_names <= development_names
