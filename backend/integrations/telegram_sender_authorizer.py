"""
TODOBA Telegram Sender Authorizer

Allows only configured Telegram technicians to cross
the trading and remote-control boundary.
"""


class TelegramSenderAuthorizer:
    """
    Authorize Telegram senders by immutable user ID.
    """

    def __init__(
        self,
        *,
        authorized_sender_ids: tuple[int, ...],
    ) -> None:
        if not isinstance(
            authorized_sender_ids,
            tuple,
        ):
            raise TypeError(
                "authorized_sender_ids must be tuple."
            )

        if not authorized_sender_ids:
            raise ValueError(
                "authorized_sender_ids cannot be empty."
            )

        normalized_sender_ids: set[int] = set()

        for sender_id in authorized_sender_ids:
            if (
                isinstance(
                    sender_id,
                    bool,
                )
                or not isinstance(
                    sender_id,
                    int,
                )
            ):
                raise TypeError(
                    "authorized sender ID must be int."
                )

            if sender_id <= 0:
                raise ValueError(
                    "authorized sender ID "
                    "must be positive."
                )

            normalized_sender_ids.add(
                sender_id
            )

        self.authorized_sender_ids = frozenset(
            normalized_sender_ids
        )

    def is_authorized(
        self,
        sender_id: int | None,
    ) -> bool:
        if (
            sender_id is None
            or isinstance(
                sender_id,
                bool,
            )
            or not isinstance(
                sender_id,
                int,
            )
            or sender_id <= 0
        ):
            return False

        return (
            sender_id
            in self.authorized_sender_ids
        )