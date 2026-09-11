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


def test_local_terminal_starts_readiness_timer_but_execution_remains_vps_only():
    source = read_agent_source()

    on_init = extract_function(
        source,
        start_marker="int OnInit()",
        end_marker="void OnDeinit(",
    )

    normalized_init = compact(
        on_init
    )

    assert (
        "!TerminalInfoInteger(TERMINAL_VPS)"
        in normalized_init
    )

    assert (
        "EventSetTimer("
        in normalized_init
    )

    on_timer_start = source.index(
        "void OnTimer()"
    )

    on_timer = source[
        on_timer_start:
    ]

    normalized_timer = compact(
        on_timer
    )

    state_publish = normalized_timer.index(
        "SendBrokerState();"
    )

    vps_guard = normalized_timer.index(
        "!TerminalInfoInteger(TERMINAL_VPS)"
    )

    local_return = normalized_timer.index(
        "return;",
        vps_guard,
    )

    mission_poll = normalized_timer.index(
        "PollCloud();"
    )

    control_poll = normalized_timer.index(
        "PollControlCloud();"
    )

    assert (
        state_publish
        < vps_guard
        < local_return
        < mission_poll
        < control_poll
    )
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
