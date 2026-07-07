"""
TODOBA Broker Symbol Resolver

Converts TODOBA canonical symbols into real broker symbols.
"""


def resolve_broker_symbol(
    canonical_symbol: str,
    symbol_map: dict[str, str],
) -> str:

    symbol = canonical_symbol.strip().upper()

    if symbol not in symbol_map:
        raise ValueError(f"No broker symbol mapping for: {canonical_symbol}")

    return symbol_map[symbol]