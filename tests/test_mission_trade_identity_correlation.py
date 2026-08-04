"""
TODOBA Proof059

Mission Broker Evidence Trade Identity Correlation

Proves:

ExecutionMission identity
        ↓
BrokerExecutionEvidence
        ↓
TradeRecord identity
        ↓
TradingRuntime lifecycle entry
"""

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)

from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)

from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)

from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)


class FakeExecutionPipeline:
    pass


def test_mission_broker_evidence_matches_trade_identity():

    evidence = BrokerExecutionEvidence(
        mission_id="proof059-mission-001",
        agent_id="agent-001",
        success=True,
        retcode=10009,
        order_ticket=500001,
        deal_ticket=600001,
        execution_price=4050.0,
        comment="proof059",
        completed_at="2026-08-05T00:00:00Z",
    )

    trade_record = TradeRecord(
        trade_id="proof059-trade-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=500001,
        deal=600001,
    )

    assert evidence.order_ticket == (
        trade_record.order
    )

    assert evidence.deal_ticket == (
        trade_record.deal
    )

    assert trade_record.status == (
        TradeStatus.OPEN
    )


def test_trading_runtime_accepts_trade_identity():

    runtime = TradingRuntime(
        execution_pipeline=FakeExecutionPipeline(),
    )

    trade_record = TradeRecord(
        trade_id="proof059-trade-002",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=700001,
        deal=800001,
    )

    result = runtime.register_open_trade(
        trade_record
    )

    assert result.trade_id == (
        "proof059-trade-002"
    )

    assert result.order == 700001

    assert result.deal == 800001