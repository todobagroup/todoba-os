from pathlib import Path
import re


EA_PATH = Path(
    "MQL5/Experts/TODOBA_Trusted_Agent.mq5"
)


def _source() -> str:
    return EA_PATH.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )


def _function(
    source: str,
    name: str,
) -> str:
    pattern = re.compile(
        rf"(?m)^[ \t]*"
        rf"(?:void|bool|int|long|double|string|datetime)"
        rf"[ \t]+{re.escape(name)}[ \t]*\([^)]*\)"
    )

    match = pattern.search(source)

    assert match is not None, (
        f"{name} signature missing"
    )

    opening = source.find(
        "{",
        match.end(),
    )

    assert opening >= 0

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        opening,
        len(source),
    ):
        char = source[index]

        if in_string:
            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
            continue

        if char == "}":
            depth -= 1

            if depth == 0:
                return source[
                    match.start():
                    index + 1
                ]

    raise AssertionError(
        f"{name} body is unterminated"
    )


def test_trusted_agent_has_raw_cashflow_publisher():
    source = _source()

    assert (
        "SendExternalFundingEvidence"
        in source
    )


def test_cashflow_publisher_reads_mt5_deal_history():
    source = _source()

    for required in (
        "HistorySelect(",
        "HistoryDealsTotal(",
        "HistoryDealGetTicket(",
        "HistoryDealGetInteger(",
        "HistoryDealGetDouble(",
        "HistoryDealGetString(",
    ):
        assert required in source


def test_cashflow_publisher_filters_account_level_cashflow_types():
    source = _source()

    for required in (
        "DEAL_TYPE_BALANCE",
        "DEAL_TYPE_CREDIT",
        "DEAL_TYPE_CHARGE",
        "DEAL_TYPE_CORRECTION",
        "DEAL_TYPE_BONUS",
        "DEAL_TYPE_COMMISSION",
        "DEAL_TYPE_COMMISSION_DAILY",
        "DEAL_TYPE_COMMISSION_MONTHLY",
        "DEAL_TYPE_COMMISSION_AGENT_DAILY",
        "DEAL_TYPE_COMMISSION_AGENT_MONTHLY",
        "DEAL_TYPE_INTEREST",
    ):
        assert required in source


def test_cashflow_publisher_uses_existing_authenticated_post_boundary():
    source = _source()

    publisher = _function(
        source,
        "SendExternalFundingEvidence",
    )

    assert (
        '"/commercial/external-funding/evidence"'
        in publisher
    )

    assert "PostJson(" in publisher

    for forbidden in (
        "Authorization: Bearer",
        "TODOBA_AGENT_SECRET",
        "WebRequest(",
    ):
        assert forbidden not in publisher


def test_cashflow_payload_is_raw_broker_evidence_only():
    source = _source()

    publisher = _function(
        source,
        "SendExternalFundingEvidence",
    )

\
    for field_name in (
        "account_fingerprint",
        "deal_ticket",
        "deal_time_msc",
        "observed_at",
        "cashflow_kind",
        "raw_deal_type",
        "amount",
        "order_ticket",
        "deal_entry",
        "magic",
        "position_id",
        "deal_reason",
        "volume",
        "price",
        "symbol",
        "external_id",
        "comment",
    ):
        escaped_json_key = (
            '\\"'
            + field_name
            + '\\"'
        )

        assert escaped_json_key in publisher

    for field_name in (
        "cycle_id",
        "customer_id",
        "deployment_id",
        "commercial_entitlement_id",
        "funding_kind",
        "upgrade_required",
    ):
        escaped_json_key = (
            '\\"'
            + field_name
            + '\\"'
        )

        assert escaped_json_key not in publisher


def test_account_fingerprint_is_derived_from_live_mt5_identity():
    source = _source()

    publisher = _function(
        source,
        "SendExternalFundingEvidence",
    )

    assert "ACCOUNT_LOGIN" in publisher
    assert "ACCOUNT_SERVER" in publisher


def test_timer_publishes_funding_evidence_before_vps_polling():
    source = _source()

    timer = _function(
        source,
        "OnTimer",
    )

    funding_index = timer.index(
        "SendExternalFundingEvidence();"
    )

    vps_guard_index = timer.index(
        "TERMINAL_VPS"
    )

    poll_index = timer.index(
        "PollCloud();"
    )

    assert (
        funding_index
        < vps_guard_index
        < poll_index
    )


def test_cashflow_publisher_does_not_gain_trade_execution_authority():
    source = _source()

    publisher = _function(
        source,
        "SendExternalFundingEvidence",
    )

    for forbidden in (
        "OrderSend(",
        "CTrade",
        "PositionClose(",
        "TRADE_ACTION_DEAL",
        "TRADE_ACTION_REMOVE",
    ):
        assert forbidden not in publisher
