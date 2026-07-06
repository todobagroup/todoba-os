"""
TODOBA Symbol Resolver

Normalize trading symbols for Trading Operations.
"""


def resolve_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("/", "")

    mapping = {
        "XAUUSD": "XAUUSD",
        "GOLD": "XAUUSD",
        "GOLDUSD": "XAUUSD",
    }

    if normalized not in mapping:
        raise ValueError(f"Unsupported symbol: {symbol}")

    return mapping[normalized]