"""
TODOBA Broker Discovery

Discovers available symbols from a broker.
"""

import MetaTrader5 as mt5


class BrokerDiscovery:

    def discover_symbols(self):

        symbols = mt5.symbols_get()

        if symbols is None:
            return []

        return symbols