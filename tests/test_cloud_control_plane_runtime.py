"""
TODOBA Proof084

Cloud Control Plane Runtime Test

Proves:

- TODOBARuntime remains generic
- CLOUD mode does not load RuntimeBootstrap
- LOCAL_TRADING mode preserves RuntimeBootstrap composition
- runtime mode defaults to LOCAL_TRADING
- runtime mode can be configured for CLOUD
- backend.main composes CLOUD without local Trading bootstrap
"""

import builtins
import importlib
import sys

import pytest

from backend.runtime.todoba_runtime import (
    TODOBARuntime,
)
from backend.runtime.runtime_mode import (
    RuntimeMode,
    create_runtime,
)


def test_todoba_runtime_remains_generic() -> None:
    runtime = TODOBARuntime()

    assert runtime._start_services == []
    assert runtime._stop_services == []


def test_cloud_mode_does_not_load_local_trading_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == (
            "backend.runtime.runtime_bootstrap"
        ):
            raise AssertionError(
                "CLOUD mode must not load "
                "RuntimeBootstrap."
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        guarded_import,
    )

    runtime = create_runtime(
        RuntimeMode.CLOUD
    )

    assert isinstance(
        runtime,
        TODOBARuntime,
    )

    assert runtime._start_services == []
    assert runtime._stop_services == []


def test_local_trading_mode_preserves_runtime_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRuntimeBootstrap:
        def create_runtime(
            self,
        ) -> TODOBARuntime:
            runtime = TODOBARuntime()

            async def start_trading() -> None:
                return None

            async def stop_trading() -> None:
                return None

            runtime.register(
                start=start_trading,
                stop=stop_trading,
            )

            return runtime

    import backend.runtime.runtime_bootstrap as runtime_bootstrap_module

    monkeypatch.setattr(
        runtime_bootstrap_module,
        "RuntimeBootstrap",
        FakeRuntimeBootstrap,
    )

    runtime = create_runtime(
        RuntimeMode.LOCAL_TRADING
    )

    assert isinstance(
        runtime,
        TODOBARuntime,
    )

    assert len(runtime._start_services) == 1
    assert len(runtime._stop_services) == 1


def test_runtime_mode_defaults_to_local_trading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dotenv

    monkeypatch.delenv(
        "TODOBA_RUNTIME_MODE",
        raising=False,
    )

    monkeypatch.setattr(
        dotenv,
        "load_dotenv",
        lambda *args, **kwargs: False,
    )

    import backend.config as config

    loaded = importlib.reload(
        config
    )

    assert loaded.TODOBA_RUNTIME_MODE == (
        "LOCAL_TRADING"
    )


def test_runtime_mode_can_be_configured_for_cloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TODOBA_RUNTIME_MODE",
        "CLOUD",
    )

    import backend.config as config

    loaded = importlib.reload(
        config
    )

    assert loaded.TODOBA_RUNTIME_MODE == (
        "CLOUD"
    )


def test_main_cloud_mode_does_not_load_runtime_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TODOBA_RUNTIME_MODE",
        "CLOUD",
    )

    import backend.config as config

    importlib.reload(
        config
    )

    sys.modules.pop(
        "backend.main",
        None,
    )

    original_import = builtins.__import__

    def guarded_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == (
            "backend.runtime.runtime_bootstrap"
        ):
            raise AssertionError(
                "backend.main CLOUD mode "
                "must not load RuntimeBootstrap."
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        guarded_import,
    )

    main = importlib.import_module(
        "backend.main"
    )

    assert isinstance(
        main.todoba_runtime,
        TODOBARuntime,
    )