import ast
import base64
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_master_key import (
    decode_customer_deployment_master_key,
)


def encode_key(
    raw_key: bytes,
) -> str:
    return (
        base64.urlsafe_b64encode(
            raw_key
        )
        .decode(
            "ascii"
        )
    )


def test_valid_32_byte_master_key_decodes_exactly(
) -> None:
    raw_key = bytes(
        range(32)
    )

    encoded_key = encode_key(
        raw_key
    )

    decoded_key = (
        decode_customer_deployment_master_key(
            encoded_key
        )
    )

    assert decoded_key == raw_key
    assert isinstance(
        decoded_key,
        bytes,
    )
    assert len(
        decoded_key
    ) == 32


def test_urlsafe_base64_alphabet_is_supported(
) -> None:
    raw_key = (
        b"\xfb\xff" * 16
    )

    encoded_key = encode_key(
        raw_key
    )

    assert (
        "-" in encoded_key
        or "_" in encoded_key
    )

    assert (
        decode_customer_deployment_master_key(
            encoded_key
        )
        == raw_key
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        None,
        b"not-a-string",
    ],
)
def test_non_string_master_key_is_rejected(
    invalid_value,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "^Customer deployment master key "
            "must be str\\.$"
        ),
    ):
        decode_customer_deployment_master_key(
            invalid_value
        )


def test_empty_master_key_is_rejected(
) -> None:
    with pytest.raises(
        RuntimeError,
        match=(
            "^TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "is required\\.$"
        ),
    ):
        decode_customer_deployment_master_key(
            ""
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        "not valid base64!!!",
        "khóa-không-ascii-✓",
    ],
)
def test_invalid_base64_master_key_is_rejected(
    invalid_value: str,
) -> None:
    with pytest.raises(
        RuntimeError,
        match=(
            "^TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "must contain valid URL-safe base64\\.$"
        ),
    ):
        decode_customer_deployment_master_key(
            invalid_value
        )


@pytest.mark.parametrize(
    "raw_key",
    [
        b"A" * 31,
        b"B" * 33,
    ],
)
def test_master_key_must_decode_to_exactly_32_bytes(
    raw_key: bytes,
) -> None:
    encoded_key = encode_key(
        raw_key
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "^TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "must decode to exactly 32 bytes\\.$"
        ),
    ):
        decode_customer_deployment_master_key(
            encoded_key
        )


def test_master_key_input_is_not_whitespace_normalized(
) -> None:
    encoded_key = encode_key(
        b"C" * 32
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "^TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "must contain valid URL-safe base64\\.$"
        ),
    ):
        decode_customer_deployment_master_key(
            encoded_key + " "
        )


def test_main_uses_shared_master_key_decoder_only(
) -> None:
    main_path = Path(
        "backend/main.py"
    )

    source = main_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules: list[str] = []

    shared_decoder_import_count = 0

    for node in tree.body:
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imported_modules.append(
                node.module or ""
            )

            if (
                node.module
                == (
                    "backend.commercial."
                    "customer_deployment_master_key"
                )
            ):
                shared_decoder_import_count += sum(
                    1
                    for alias in node.names
                    if (
                        alias.name
                        == (
                            "decode_customer_"
                            "deployment_master_key"
                        )
                    )
                )

    assert (
        "base64"
        not in imported_modules
    )

    assert (
        shared_decoder_import_count
        == 1
    )

    top_level_functions = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    assert (
        "_decode_customer_deployment_master_key"
        not in top_level_functions
    )

    shared_calls = 0
    private_calls = 0

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        if (
            node.func.id
            == (
                "decode_customer_"
                "deployment_master_key"
            )
        ):
            shared_calls += 1

        if (
            node.func.id
            == (
                "_decode_customer_"
                "deployment_master_key"
            )
        ):
            private_calls += 1

    assert shared_calls == 1
    assert private_calls == 0
