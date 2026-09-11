from pathlib import Path


def _source():
    return Path(
        "MQL5/Experts/TODOBA_Trusted_Agent.mq5"
    ).read_text(
        encoding="utf-8-sig"
    )


def test_agent_emits_supported_runtime_origin():
    source = _source()

    assert "TERMINAL_VPS" in source
    assert "runtime_environment" in source
    assert '"metaquotes_vps"' in source
    assert '"local"' in source


def test_broker_state_uses_attached_symbol_not_hard_coded_gold():
    source = _source()

    start = source.index(
        "void SendBrokerState()"
    )
    end = source.index(
        "void PollCloud()",
        start,
    )
    block = source[start:end]

    assert "TODOBABrokerStateReader::Read(" in block
    assert "_Symbol" in block
    assert '"XAUUSD"' not in block


def test_local_runtime_publishes_state_but_cannot_poll_execution():
    source = _source()

    start = source.index(
        "void OnTimer()"
    )
    block = source[start:]

    state_pos = block.index(
        "SendBrokerState();"
    )
    guard_pos = block.index(
        "TERMINAL_VPS"
    )
    return_pos = block.index(
        "return;",
        guard_pos,
    )
    mission_pos = block.index(
        "PollCloud();"
    )
    control_pos = block.index(
        "PollControlCloud();"
    )

    assert (
        state_pos
        < guard_pos
        < return_pos
        < mission_pos
        < control_pos
    )
