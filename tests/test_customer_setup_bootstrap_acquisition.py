"""
Owner tests for customer-side setup bootstrap acquisition.
"""

from __future__ import annotations

import ast
import base64
import hashlib
from pathlib import Path
import re

import pytest

import backend.commercial.customer_setup_bootstrap_acquisition as acquisition_module
from backend.commercial.customer_setup_bootstrap_acquisition import (
    CustomerSetupBootstrapAcquisition,
)


SETUP_BASE_URL = (
    "https://setup.todoba.example"
)

AUTHORIZATION_CODE = (
    "tdbba."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

CODE_VERIFIER = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-._~"
)

ROAMING_PATH = Path(
    r"C:\Users\Customer\AppData\Roaming"
)


def _expected_challenge(
    verifier: str,
) -> str:
    return (
        base64.urlsafe_b64encode(
            hashlib.sha256(
                verifier.encode(
                    "ascii"
                )
            ).digest()
        )
        .decode(
            "ascii"
        )
        .rstrip("=")
    )


def _build_acquisition(
    monkeypatch,
    *,
    verifier: str = CODE_VERIFIER,
):
    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        lambda: verifier,
    )

    return CustomerSetupBootstrapAcquisition(
        setup_base_url=(
            SETUP_BASE_URL
        ),
        mt5_module=object(),
        roaming_appdata_path=(
            ROAMING_PATH
        ),
    )


def test_generates_verifier_once_at_construction(
    monkeypatch,
) -> None:
    calls = []

    def generate():
        calls.append(
            "generate"
        )
        return CODE_VERIFIER

    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        generate,
    )

    CustomerSetupBootstrapAcquisition(
        setup_base_url=SETUP_BASE_URL,
        mt5_module=object(),
        roaming_appdata_path=ROAMING_PATH,
    )

    assert calls == [
        "generate",
    ]


def test_public_challenge_matches_rfc7636_s256(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    assert (
        acquisition.code_challenge_s256
        == _expected_challenge(
            CODE_VERIFIER
        )
    )


def test_public_challenge_is_43_char_urlsafe_base64(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    challenge = (
        acquisition.code_challenge_s256
    )

    assert len(challenge) == 43

    assert (
        re.fullmatch(
            r"[A-Za-z0-9_-]{43}",
            challenge,
        )
        is not None
    )

    assert "=" not in challenge


def test_generated_verifier_uses_token_urlsafe_32(
    monkeypatch,
) -> None:
    observed = {}

    generated = (
        "A" * 43
    )

    def token_urlsafe(
        size,
    ):
        observed[
            "size"
        ] = size

        return generated

    monkeypatch.setattr(
        acquisition_module.secrets,
        "token_urlsafe",
        token_urlsafe,
    )

    result = (
        acquisition_module
        ._generate_code_verifier()
    )

    assert result == generated

    assert observed == {
        "size": 32,
    }


@pytest.mark.parametrize(
    "verifier",
    [
        "A" * 43,
        "a" * 128,
        (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopq"
        ),
        (
            "0123456789"
            "-._~"
            + ("A" * 29)
        ),
    ],
)
def test_valid_pkce_verifiers_are_accepted(
    verifier,
) -> None:
    assert (
        acquisition_module
        ._normalize_code_verifier(
            verifier
        )
        == verifier
    )


@pytest.mark.parametrize(
    "verifier",
    [
        "",
        "A" * 42,
        "A" * 129,
        "A" * 42 + "=",
        "A" * 42 + "+",
        "A" * 42 + "/",
        "A" * 42 + " ",
    ],
)
def test_invalid_pkce_verifiers_are_rejected(
    verifier,
) -> None:
    with pytest.raises(
        ValueError,
        match="code_verifier is invalid",
    ):
        acquisition_module._normalize_code_verifier(
            verifier
        )


def test_non_string_verifier_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match="code_verifier must be str",
    ):
        acquisition_module._normalize_code_verifier(
            123
        )


def test_launch_passes_exact_material_to_coordinator(
    monkeypatch,
) -> None:
    observed = {}

    mt5_module = object()

    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        lambda: CODE_VERIFIER,
    )

    class FakeCoordinator:
        def __init__(
            self,
            **kwargs,
        ):
            observed.update(
                kwargs
            )

        def run(
            self,
        ):
            observed[
                "run"
            ] = (
                observed.get(
                    "run",
                    0,
                )
                + 1
            )

    monkeypatch.setattr(
        acquisition_module,
        "CustomerSetupBootstrapCoordinator",
        FakeCoordinator,
    )

    acquisition = (
        CustomerSetupBootstrapAcquisition(
            setup_base_url=(
                SETUP_BASE_URL
            ),
            mt5_module=mt5_module,
            roaming_appdata_path=(
                ROAMING_PATH
            ),
        )
    )

    acquisition.launch(
        authorization_code=(
            AUTHORIZATION_CODE
        ),
    )

    assert observed[
        "setup_base_url"
    ] == SETUP_BASE_URL

    assert observed[
        "authorization_code"
    ] == AUTHORIZATION_CODE

    assert observed[
        "code_verifier"
    ] == CODE_VERIFIER

    assert (
        observed[
            "mt5_module"
        ]
        is mt5_module
    )

    assert observed[
        "roaming_appdata_path"
    ] == ROAMING_PATH

    assert observed[
        "run"
    ] == 1


def test_launch_does_not_regenerate_verifier(
    monkeypatch,
) -> None:
    generate_calls = []

    def generate():
        generate_calls.append(
            "generate"
        )
        return CODE_VERIFIER

    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        generate,
    )

    class FakeCoordinator:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        acquisition_module,
        "CustomerSetupBootstrapCoordinator",
        FakeCoordinator,
    )

    acquisition = (
        CustomerSetupBootstrapAcquisition(
            setup_base_url=SETUP_BASE_URL,
            mt5_module=object(),
            roaming_appdata_path=ROAMING_PATH,
        )
    )

    acquisition.launch(
        authorization_code=AUTHORIZATION_CODE
    )

    assert generate_calls == [
        "generate",
    ]


def test_launch_preserves_same_private_verifier_for_retry(
    monkeypatch,
) -> None:
    observed = []

    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        lambda: CODE_VERIFIER,
    )

    class FakeCoordinator:
        def __init__(
            self,
            **kwargs,
        ):
            observed.append(
                kwargs[
                    "code_verifier"
                ]
            )

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        acquisition_module,
        "CustomerSetupBootstrapCoordinator",
        FakeCoordinator,
    )

    acquisition = (
        CustomerSetupBootstrapAcquisition(
            setup_base_url=SETUP_BASE_URL,
            mt5_module=object(),
            roaming_appdata_path=ROAMING_PATH,
        )
    )

    acquisition.launch(
        authorization_code=AUTHORIZATION_CODE
    )

    acquisition.launch(
        authorization_code=AUTHORIZATION_CODE
    )

    assert observed == [
        CODE_VERIFIER,
        CODE_VERIFIER,
    ]


def test_authorization_code_is_required(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    with pytest.raises(
        ValueError,
        match="authorization_code must not be empty",
    ):
        acquisition.launch(
            authorization_code="   "
        )


def test_non_string_authorization_code_is_rejected(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    with pytest.raises(
        TypeError,
        match="authorization_code must be str",
    ):
        acquisition.launch(
            authorization_code=123
        )


def test_setup_base_url_is_required(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        lambda: CODE_VERIFIER,
    )

    with pytest.raises(
        ValueError,
        match="setup_base_url must not be empty",
    ):
        CustomerSetupBootstrapAcquisition(
            setup_base_url="   ",
            mt5_module=object(),
            roaming_appdata_path=ROAMING_PATH,
        )


def test_mt5_module_is_required(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        lambda: CODE_VERIFIER,
    )

    with pytest.raises(
        TypeError,
        match="mt5_module must not be None",
    ):
        CustomerSetupBootstrapAcquisition(
            setup_base_url=SETUP_BASE_URL,
            mt5_module=None,
            roaming_appdata_path=ROAMING_PATH,
        )


def test_roaming_appdata_path_must_be_path(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        acquisition_module,
        "_generate_code_verifier",
        lambda: CODE_VERIFIER,
    )

    with pytest.raises(
        TypeError,
        match="roaming_appdata_path must be Path",
    ):
        CustomerSetupBootstrapAcquisition(
            setup_base_url=SETUP_BASE_URL,
            mt5_module=object(),
            roaming_appdata_path=(
                r"C:\Users\Customer\AppData\Roaming"
            ),
        )


def test_no_public_code_verifier_property(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    assert not hasattr(
        type(acquisition),
        "code_verifier",
    )

    assert (
        "code_verifier"
        not in dir(type(acquisition))
    )


def test_instance_has_no_dynamic_dict_for_secret_attachment(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    assert not hasattr(
        acquisition,
        "__dict__",
    )


def test_repr_redacts_code_verifier(
    monkeypatch,
) -> None:
    acquisition = _build_acquisition(
        monkeypatch
    )

    rendered = repr(
        acquisition
    )

    assert (
        CODE_VERIFIER
        not in rendered
    )

    assert (
        "code_verifier=<redacted>"
        in rendered
    )

    assert (
        acquisition.code_challenge_s256
        in rendered
    )


def test_owner_has_no_persistence_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / (
            "customer_setup_bootstrap_"
            "acquisition.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    forbidden_calls = {
        "open",
        "write",
        "write_text",
        "write_bytes",
        "dump",
        "dumps",
        "mkdir",
        "touch",
        "initialize_empty",
        "open_existing",
    }

    called_names = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Name,
        ):
            called_names.add(
                node.func.id
            )

        if isinstance(
            node.func,
            ast.Attribute,
        ):
            called_names.add(
                node.func.attr
            )

    assert forbidden_calls.isdisjoint(
        called_names
    )


def test_owner_has_no_http_server_or_business_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / (
            "customer_setup_bootstrap_"
            "acquisition.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules = set()

    for node in ast.walk(tree):
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
            and node.module
        ):
            imported_modules.add(
                node.module
            )

    forbidden_roots = {
        "fastapi",
        "httpx",
        "requests",
        "uvicorn",
    }

    assert forbidden_roots.isdisjoint(
        {
            module.split(
                ".",
                1,
            )[0]
            for module in imported_modules
        }
    )

    assert (
        "backend.main"
        not in imported_modules
    )

    forbidden_authorities = (
        "CustomerIdentityRegistry",
        "CustomerDeployment",
        "CustomerOnboardingService",
        "CustomerSetupActivationService",
        "CustomerSetupLaunchCredentialService",
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupBootstrapAuthorizationStore",
        "CustomerSetupBootstrapLaunchGrantService",
        "customer_id",
        "deployment_id",
        "agent_id",
        "payment_id",
        "subscription_id",
    )

    for token in forbidden_authorities:
        assert token not in source


def test_owner_imports_only_coordinator_from_commercial(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / (
            "customer_setup_bootstrap_"
            "acquisition.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    commercial_modules = {
        node.module
        for node in ast.walk(tree)
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
            "customer_setup_bootstrap_"
            "coordinator"
        )
    }


def test_owner_uses_os_backed_secret_generation(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / (
            "customer_setup_bootstrap_"
            "acquisition.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Import,
        )
        for alias in node.names
    }

    assert "secrets" in imports

    calls = {
        (
            ast.get_source_segment(
                source,
                node.func,
            )
            or ""
        )
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Call,
        )
    }

    assert (
        "secrets.token_urlsafe"
        in calls
    )


def test_owner_does_not_import_server_pkce_owner(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / (
            "customer_setup_bootstrap_"
            "acquisition.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        )
    }

    assert (
        "backend.commercial."
        "customer_setup_bootstrap_"
        "authorization_service"
        not in imported_modules
    )


def test_owner_exposes_exact_public_surface(
) -> None:
    public_members = {
        name
        for name in dir(
            CustomerSetupBootstrapAcquisition
        )
        if not name.startswith(
            "_"
        )
    }

    assert public_members == {
        "code_challenge_s256",
        "launch",
    }


def test_local_derivation_matches_server_contract(
) -> None:
    from backend.commercial.customer_setup_bootstrap_authorization_service import (
        derive_pkce_s256_code_challenge,
    )

    assert (
        acquisition_module
        ._derive_pkce_s256_code_challenge(
            CODE_VERIFIER
        )
        == derive_pkce_s256_code_challenge(
            CODE_VERIFIER
        )
    )
