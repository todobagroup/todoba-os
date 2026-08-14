"""
TODOBA Trusted Agent VPS Runtime Boundary Tests.

Proof:

Local MetaTrader terminal
->
Trusted Agent standby

MetaTrader Virtual Hosting
->
broker-state publication
->
mission polling
"""


from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

AGENT_PATH = (
    ROOT_DIR
    / "MQL5"
    / "Experts"
    / "TODOBA_Trusted_Agent.mq5"
)


def read_agent_source() -> str:
    return AGENT_PATH.read_text(
        encoding="utf-8",
    )


def compact(source: str) -> str:
    return "".join(
        source.split()
    )


def extract_function(
    source: str,
    *,
    start_marker: str,
    end_marker: str,
) -> str:
    start = source.index(
        start_marker
    )

    end = source.index(
        end_marker,
        start,
    )

    return source[
        start:end
    ]


def test_local_terminal_does_not_start_agent_timer():
    source = read_agent_source()

    on_init = extract_function(
        source,
        start_marker="int OnInit()",
        end_marker="void OnDeinit(",
    )

    normalized = compact(
        on_init
    )

    vps_guard = normalized.index(
        "!TerminalInfoInteger(TERMINAL_VPS)"
    )

    standby_return = normalized.index(
        "returnINIT_SUCCEEDED;",
        vps_guard,
    )

    timer_start = normalized.index(
        "EventSetTimer(",
    )

    assert vps_guard < standby_return
    assert standby_return < timer_start


def test_timer_owns_broker_state_and_mission_polling():
    source = read_agent_source()

    on_timer = extract_function(
        source,
        start_marker="void OnTimer()",
        end_marker="void __TODOBA_TEST_END__",
    ) if "void __TODOBA_TEST_END__" in source else (
        source[
            source.index("void OnTimer()"):
        ]
    )

    normalized = compact(
        on_timer
    )

    assert "SendBrokerState();" in normalized
    assert "PollCloud();" in normalized