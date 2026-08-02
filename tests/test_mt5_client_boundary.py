from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.broker.mt5_client import (
    MT5Client,
)


class FakeTerminalInfo:
    pass


class FakeAccountInfo:

    login = 123456
    server = "DemoServer"
    balance = 10000.0
    equity = 10000.0
    margin = 0.0
    margin_free = 10000.0
    leverage = 100


class FakeSymbolInfo:

    digits = 2
    point = 0.01


class FakeTick:

    bid = 4099.0
    ask = 4100.0


class FakeMT5:

    def __init__(self):

        self.initialized = False
        self.shutdown_called = False


    def initialize(self):

        self.initialized = True

        return True


    def shutdown(self):

        self.shutdown_called = True


    def terminal_info(self):

        if self.initialized:
            return FakeTerminalInfo()

        return None


    def account_info(self):

        return FakeAccountInfo()


    def symbol_info(
        self,
        symbol,
    ):

        return FakeSymbolInfo()


    def symbol_info_tick(
        self,
        symbol,
    ):

        return FakeTick()



def test_mt5_client_boundary():

    fake_mt5 = FakeMT5()


    client = MT5Client(
        mt5_module=fake_mt5
    )


    connected = client.connect()


    assert connected is True


    assert client.is_connected() is True


    account = client.get_account_info()


    assert account is not None


    assert account.login == 123456


    market = client.get_market_info(
        "XAUUSD"
    )


    assert market is not None


    assert market.symbol == "XAUUSD"


    client.disconnect()


    assert fake_mt5.shutdown_called is True