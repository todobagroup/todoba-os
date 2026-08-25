"""
TODOBA Customer Deployment Master Key Decoder

Owns strict decoding and validation of the configured
Customer Deployment Master Key.

Contract:
- input must be str
- empty input is rejected
- input must contain valid strict URL-safe Base64
- decoded key must be exactly 32 bytes
- no whitespace normalization is performed

This component does not:
- read environment variables
- persist key material
- print key material
- own customer deployment secrets
- import or start application runtime
"""

import base64


def decode_customer_deployment_master_key(
    encoded_master_key: str,
) -> bytes:
    """
    Decode one configured customer deployment master key.

    Behavior intentionally preserves the production
    validation contract previously owned by backend.main.
    """

    if not isinstance(
        encoded_master_key,
        str,
    ):
        raise TypeError(
            "Customer deployment master key "
            "must be str."
        )

    if encoded_master_key == "":
        raise RuntimeError(
            "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "is required."
        )

    try:
        encoded_bytes = (
            encoded_master_key.encode(
                "ascii"
            )
        )

        master_key = base64.b64decode(
            encoded_bytes,
            altchars=b"-_",
            validate=True,
        )
    except (
        UnicodeEncodeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "must contain valid URL-safe base64."
        ) from error

    if len(master_key) != 32:
        raise RuntimeError(
            "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY "
            "must decode to exactly 32 bytes."
        )

    return master_key
