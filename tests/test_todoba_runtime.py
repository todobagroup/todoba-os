from backend.runtime.todoba_runtime import (
    TODOBARuntime,
)


def test_runtime_can_be_created():
    runtime = TODOBARuntime()

    assert runtime is not None


def test_runtime_has_start():
    runtime = TODOBARuntime()

    assert hasattr(runtime, "start")


def test_runtime_has_stop():
    runtime = TODOBARuntime()

    assert hasattr(runtime, "stop")