from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXECUTION_MISSION = (
    ROOT
    / "backend"
    / "trading"
    / "execution"
    / "execution_mission.py"
)

CONTROL_MISSION = (
    ROOT
    / "backend"
    / "trading"
    / "control"
    / "control_mission.py"
)

EXECUTION_SERIALIZER_V2 = (
    ROOT
    / "backend"
    / "trading"
    / "execution"
    / "execution_mission_serializer_v2.py"
)

CONTROL_SERIALIZER_V2 = (
    ROOT
    / "backend"
    / "trading"
    / "control"
    / "control_mission_serializer_v2.py"
)

EXECUTION_SIGNING_V2 = (
    ROOT
    / "backend"
    / "trading"
    / "execution"
    / "execution_mission_signing_payload_v2.py"
)

CONTROL_SIGNING_V2 = (
    ROOT
    / "backend"
    / "trading"
    / "control"
    / "control_mission_signing_payload_v2.py"
)

EXECUTION_SIGNER_V2 = (
    ROOT
    / "backend"
    / "trading"
    / "execution"
    / "execution_mission_signer_v2.py"
)

CONTROL_SIGNER_V2 = (
    ROOT
    / "backend"
    / "trading"
    / "control"
    / "control_mission_signer_v2.py"
)

MQL_EXECUTION_PARSER = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionMissionParser.mqh"
)

MQL_CONTROL_PARSER = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAControl"
    / "ControlMissionParser.mqh"
)

MQL_EXECUTION_PARSER_V2 = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionMissionParserV2.mqh"
)

MQL_CONTROL_PARSER_V2 = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAControl"
    / "ControlMissionParserV2.mqh"
)

MQL_EXECUTION_SIGNING_V2 = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionMissionSigningPayloadV2.mqh"
)

MQL_CONTROL_SIGNING_V2 = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAControl"
    / "ControlMissionSigningPayloadV2.mqh"
)

MQL_EXECUTION_VERIFIER_V2 = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionMissionSignatureVerifierV2.mqh"
)

MQL_CONTROL_VERIFIER_V2 = (
    ROOT
    / "MQL5"
    / "Include"
    / "TODOBAControl"
    / "ControlMissionSignatureVerifierV2.mqh"
)


def read_source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    )


def test_shared_mission_contracts_gain_backward_compatible_security_sequence():
    execution = read_source(
        EXECUTION_MISSION
    )

    control = read_source(
        CONTROL_MISSION
    )

    assert "security_sequence: int = 0" in execution
    assert "security_sequence: int = 0" in control


def test_python_execution_v2_contract_is_additive():
    assert EXECUTION_SERIALIZER_V2.exists()
    assert EXECUTION_SIGNING_V2.exists()
    assert EXECUTION_SIGNER_V2.exists()

    serializer = read_source(
        EXECUTION_SERIALIZER_V2
    )

    signing = read_source(
        EXECUTION_SIGNING_V2
    )

    signer = read_source(
        EXECUTION_SIGNER_V2
    )

    assert '"security_sequence"' in serializer
    assert "security_sequence=" in serializer

    assert (
        'DOMAIN = "TODOBA_EXECUTION_MISSION_V2"'
        in signing
    )

    assert "mission.security_sequence" in signing

    assert (
        signing.index("mission.sequence")
        <
        signing.rindex("mission.security_sequence")
    )

    assert (
        "ExecutionMissionSigningPayloadV2"
        in signer
    )


def test_python_control_v2_contract_is_additive():
    assert CONTROL_SERIALIZER_V2.exists()
    assert CONTROL_SIGNING_V2.exists()
    assert CONTROL_SIGNER_V2.exists()

    serializer = read_source(
        CONTROL_SERIALIZER_V2
    )

    signing = read_source(
        CONTROL_SIGNING_V2
    )

    signer = read_source(
        CONTROL_SIGNER_V2
    )

    assert '"security_sequence"' in serializer
    assert "security_sequence=" in serializer

    assert (
        'DOMAIN = "TODOBA_CONTROL_MISSION_V2"'
        in signing
    )

    assert "mission.security_sequence" in signing

    assert (
        signing.index("mission.sequence")
        <
        signing.rindex("mission.security_sequence")
    )

    assert (
        "ControlMissionSigningPayloadV2"
        in signer
    )


def test_mql_execution_v2_contract_is_additive():
    parser = read_source(
        MQL_EXECUTION_PARSER
    )

    assert "long security_sequence;" in parser

    assert MQL_EXECUTION_PARSER_V2.exists()
    assert MQL_EXECUTION_SIGNING_V2.exists()
    assert MQL_EXECUTION_VERIFIER_V2.exists()

    parser_v2 = read_source(
        MQL_EXECUTION_PARSER_V2
    )

    signing_v2 = read_source(
        MQL_EXECUTION_SIGNING_V2
    )

    verifier_v2 = read_source(
        MQL_EXECUTION_VERIFIER_V2
    )

    assert '"security_sequence",' in parser_v2
    assert "mission.security_sequence" in parser_v2

    assert (
        '"TODOBA_EXECUTION_MISSION_V2"'
        in signing_v2
    )

    assert "mission.security_sequence" in signing_v2

    assert (
        signing_v2.index("mission.sequence")
        <
        signing_v2.rindex(
            "mission.security_sequence"
        )
    )

    assert (
        "TODOBAExecutionMissionSigningPayloadV2"
        in verifier_v2
    )


def test_mql_control_v2_contract_is_additive():
    parser = read_source(
        MQL_CONTROL_PARSER
    )

    assert "long security_sequence;" in parser

    assert MQL_CONTROL_PARSER_V2.exists()
    assert MQL_CONTROL_SIGNING_V2.exists()
    assert MQL_CONTROL_VERIFIER_V2.exists()

    parser_v2 = read_source(
        MQL_CONTROL_PARSER_V2
    )

    signing_v2 = read_source(
        MQL_CONTROL_SIGNING_V2
    )

    verifier_v2 = read_source(
        MQL_CONTROL_VERIFIER_V2
    )

    assert '"security_sequence",' in parser_v2
    assert "mission.security_sequence" in parser_v2

    assert (
        '"TODOBA_CONTROL_MISSION_V2"'
        in signing_v2
    )

    assert "mission.security_sequence" in signing_v2

    assert (
        signing_v2.index("mission.sequence")
        <
        signing_v2.rindex(
            "mission.security_sequence"
        )
    )

    assert (
        "TODOBAControlMissionSigningPayloadV2"
        in verifier_v2
    )