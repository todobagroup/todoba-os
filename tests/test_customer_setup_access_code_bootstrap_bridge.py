"""
Owner tests for hidden customer Activation Code bootstrap bridge.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import backend.commercial.customer_setup_access_code_bootstrap_bridge as bridge_module
from backend.commercial.customer_setup_access_code_bootstrap_bridge import (
    CustomerSetupAccessCodeBootstrapBridge,
)
from backend.commercial.customer_setup_access_code_http_client import (
    CustomerSetupAccessCodeHttpClient,
    CustomerSetupAccessCodeTransportResult,
)
from backend.commercial.customer_setup_bootstrap_acquisition import (
    CustomerSetupBootstrapAcquisition,
)


ACTIVATION_CODE = (
    "tdbsa."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

CODE_CHALLENGE = (
    "B" * 43
)

AUTHORIZATION_CODE = (
    "tdbba."
    + ("2" * 32)
    + "."
    + ("C" * 43)
)


class FakeAccessCodeClient(
    CustomerSetupAccessCodeHttpClient
):
    __slots__ = (
        "calls",
    )

    def __init__(
        self,
    ) -> None:
        self.calls = []

    def exchange(
        self,
        *,
        activation_code: str,
        code_challenge_s256: str,
    ):
        self.calls.append(
            {
                "activation_code": (
                    activation_code
                ),
                "code_challenge_s256": (
                    code_challenge_s256
                ),
            }
        )

        return (
            CustomerSetupAccessCodeTransportResult(
                authorization_code=(
                    AUTHORIZATION_CODE
                ),
                expires_at=(
                    "2026-09-05T01:00:00+00:00"
                ),
            )
        )


class FakeAcquisition(
    CustomerSetupBootstrapAcquisition
):
    __slots__ = (
        "launch_calls",
    )

    def __init__(
        self,
    ) -> None:
        self.launch_calls = []

    @property
    def code_challenge_s256(
        self,
    ) -> str:
        return CODE_CHALLENGE

    def launch(
        self,
        *,
        authorization_code: str,
    ) -> None:
        self.launch_calls.append(
            authorization_code
        )


def _build():
    client = (
        FakeAccessCodeClient()
    )

    acquisition = (
        FakeAcquisition()
    )

    bridge = (
        CustomerSetupAccessCodeBootstrapBridge(
            access_code_client=client,
            acquisition=acquisition,
        )
    )

    return (
        bridge,
        client,
        acquisition,
    )


def test_launch_exchanges_activation_code_with_public_pkce_challenge(
) -> None:
    (
        bridge,
        client,
        acquisition,
    ) = _build()

    bridge.launch(
        activation_code=(
            ACTIVATION_CODE
        )
    )

    assert client.calls == [
        {
            "activation_code": (
                ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                CODE_CHALLENGE
            ),
        }
    ]

    assert acquisition.launch_calls == [
        AUTHORIZATION_CODE,
    ]


def test_internal_authorization_code_is_not_returned(
) -> None:
    (
        bridge,
        client,
        acquisition,
    ) = _build()

    del client
    del acquisition

    result = bridge.launch(
        activation_code=ACTIVATION_CODE
    )

    assert result is None


def test_exchange_failure_prevents_bootstrap_launch(
) -> None:
    class FailingClient(
        FakeAccessCodeClient
    ):
        def exchange(
            self,
            *,
            activation_code,
            code_challenge_s256,
        ):
            del activation_code
            del code_challenge_s256

            raise RuntimeError(
                "exchange failed"
            )

    client = (
        FailingClient()
    )

    acquisition = (
        FakeAcquisition()
    )

    bridge = (
        CustomerSetupAccessCodeBootstrapBridge(
            access_code_client=client,
            acquisition=acquisition,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="exchange failed",
    ):
        bridge.launch(
            activation_code=ACTIVATION_CODE
        )

    assert (
        acquisition.launch_calls
        == []
    )


def test_bootstrap_failure_propagates_after_single_exchange(
) -> None:
    class FailingAcquisition(
        FakeAcquisition
    ):
        def launch(
            self,
            *,
            authorization_code,
        ):
            self.launch_calls.append(
                authorization_code
            )

            raise RuntimeError(
                "bootstrap failed"
            )

    client = (
        FakeAccessCodeClient()
    )

    acquisition = (
        FailingAcquisition()
    )

    bridge = (
        CustomerSetupAccessCodeBootstrapBridge(
            access_code_client=client,
            acquisition=acquisition,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="bootstrap failed",
    ):
        bridge.launch(
            activation_code=ACTIVATION_CODE
        )

    assert len(
        client.calls
    ) == 1

    assert acquisition.launch_calls == [
        AUTHORIZATION_CODE,
    ]


@pytest.mark.parametrize(
    "activation_code",
    [
        "",
        "   ",
        " activation-code",
        "activation-code ",
    ],
)
def test_invalid_activation_code_is_rejected_before_exchange(
    activation_code,
) -> None:
    (
        bridge,
        client,
        acquisition,
    ) = _build()

    with pytest.raises(
        ValueError,
    ):
        bridge.launch(
            activation_code=(
                activation_code
            )
        )

    assert client.calls == []
    assert acquisition.launch_calls == []


def test_non_string_activation_code_is_rejected_before_exchange(
) -> None:
    (
        bridge,
        client,
        acquisition,
    ) = _build()

    with pytest.raises(
        TypeError,
        match="activation_code must be str",
    ):
        bridge.launch(
            activation_code=123
        )

    assert client.calls == []
    assert acquisition.launch_calls == []


def test_constructor_requires_access_code_http_client(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "access_code_client must be "
            "CustomerSetupAccessCodeHttpClient"
        ),
    ):
        CustomerSetupAccessCodeBootstrapBridge(
            access_code_client=object(),
            acquisition=FakeAcquisition(),
        )


def test_constructor_requires_bootstrap_acquisition(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "acquisition must be "
            "CustomerSetupBootstrapAcquisition"
        ),
    ):
        CustomerSetupAccessCodeBootstrapBridge(
            access_code_client=(
                FakeAccessCodeClient()
            ),
            acquisition=object(),
        )


def test_public_surface_is_launch_only(
) -> None:
    public_members = {
        name
        for name in dir(
            CustomerSetupAccessCodeBootstrapBridge
        )
        if not name.startswith(
            "_"
        )
    }

    assert public_members == {
        "launch",
    }

    parameters = inspect.signature(
        CustomerSetupAccessCodeBootstrapBridge.launch
    ).parameters

    assert set(
        parameters
    ) == {
        "self",
        "activation_code",
    }


def test_bridge_has_no_dynamic_secret_attachment_surface(
) -> None:
    (
        bridge,
        client,
        acquisition,
    ) = _build()

    del client
    del acquisition

    assert not hasattr(
        bridge,
        "__dict__",
    )


def test_owner_imports_exact_two_customer_side_owners(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_bootstrap_bridge.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    commercial_modules = {
        node.module
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
            and node.module.startswith(
                "backend.commercial."
            )
        )
    }

    assert commercial_modules == {
        (
            "backend.commercial."
            "customer_setup_access_code_http_client"
        ),
        (
            "backend.commercial."
            "customer_setup_bootstrap_acquisition"
        ),
    }


def test_owner_has_no_server_business_persistence_or_payment_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_bootstrap_bridge.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    identifiers = set()
    called_names = set()
    imported_modules = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Name,
        ):
            identifiers.add(
                node.id
            )

        elif isinstance(
            node,
            ast.Attribute,
        ):
            identifiers.add(
                node.attr
            )

        elif isinstance(
            node,
            ast.FunctionDef,
        ):
            for argument in (
                list(
                    node.args.posonlyargs
                )
                + list(
                    node.args.args
                )
                + list(
                    node.args.kwonlyargs
                )
            ):
                identifiers.add(
                    argument.arg
                )

        if isinstance(
            node,
            ast.Call,
        ):
            if isinstance(
                node.func,
                ast.Name,
            ):
                called_names.add(
                    node.func.id
                )

            elif isinstance(
                node.func,
                ast.Attribute,
            ):
                called_names.add(
                    node.func.attr
                )

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_modules.add(
                    alias.name
                )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        ):
            imported_modules.add(
                node.module
            )

    forbidden_identifiers = {
        "customer_id",
        "setup_activation_id",
        "deployment_id",
        "payment_id",
        "subscription_id",
        "agent_id",
    }

    assert forbidden_identifiers.isdisjoint(
        identifiers
    )

    forbidden_actions = {
        "initialize_empty",
        "open_existing",
        "issue",
        "authorize",
        "revoke",
        "grant",
        "register",
        "bind",
        "write",
        "write_text",
        "write_bytes",
        "dump",
        "dumps",
    }

    assert forbidden_actions.isdisjoint(
        called_names
    )

    assert (
        "backend.main"
        not in imported_modules
    )


def test_owner_does_not_expose_or_read_private_code_verifier(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_bootstrap_bridge.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    executable_identifiers = {
        node.id
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Name,
        )
    }

    executable_identifiers.update(
        node.attr
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Attribute,
        )
    )

    assert (
        "code_verifier"
        not in executable_identifiers
    )

    assert (
        "code_challenge_s256"
        in executable_identifiers
    )