from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FRESHNESS_GUARD = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "MissionFreshnessGuard.mqh"
)

EXECUTION_VALIDATOR = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionMissionValidator.mqh"
)

CONTROL_VALIDATOR = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAControl"
    / "ControlMissionValidator.mqh"
)


def read_source(path: Path) -> str:
    assert path.exists(), f"Required source file does not exist: {path}"
    return path.read_text(encoding="utf-8-sig")


def test_shared_mission_freshness_guard_contract():
    source = read_source(FRESHNESS_GUARD)

    assert "TODOBAMissionFreshnessGuard" in source
    assert "TimeGMT()" in source
    assert "created_at" in source
    assert "expires_at" in source

    assert "ParseUtcIso8601" in source
    assert "expires_at <= created_at" in source
    assert "expires_at <= now" in source


def test_execution_mission_validator_requires_freshness_guard():
    source = read_source(EXECUTION_VALIDATOR)

    assert (
        "#include <TODOBAExecution/MissionFreshnessGuard.mqh>"
        in source
    )

    assert (
        "TODOBAMissionFreshnessGuard::Validate("
        in source
    )

    assert "mission.created_at" in source
    assert "mission.expires_at" in source


def test_control_mission_validator_requires_freshness_guard():
    source = read_source(CONTROL_VALIDATOR)

    assert (
        "#include <TODOBAExecution/MissionFreshnessGuard.mqh>"
        in source
    )

    assert (
        "TODOBAMissionFreshnessGuard::Validate("
        in source
    )

    assert "mission.created_at" in source
    assert "mission.expires_at" in source