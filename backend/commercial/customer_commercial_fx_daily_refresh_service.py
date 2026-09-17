"""
TODOBA Customer Commercial Daily FX Refresh.

P9B3 composes:

    VietcombankFXAdapter.fetch()
        -> provider-neutral result
        -> authoritative snapshot_date in Vietnam
        -> CustomerCommercialFXSnapshotRecord
        -> CustomerCommercialFXSnapshotStore.save()

The scheduler owns timing only:

    every day at 07:00 Vietnam time
        -> refresh_once()

Important convergence rule:

- P9B1 durable identity is date + source + currency pair.
- fetched_at is observation metadata, not new FX authority.
- repeated fetch of the same authoritative provider facts
  for the same durable identity converges to the existing
  snapshot even when fetched_at differs.
- changed authoritative facts for the same identity fail closed.

This owner does NOT define freshness TTL, stale policy,
order pricing, payment verification, settlement, or
entitlement authority.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotRecord,
    CustomerCommercialFXSnapshotStore,
)
from backend.commercial.customer_commercial_vietcombank_fx_adapter import (
    VIETNAM_TIMEZONE,
    VietcombankFXAdapter,
)


_REFRESH_HOUR = 7
_REFRESH_MINUTE = 0


class CustomerCommercialFXDailyRefreshService:
    """
    Compose one provider fetch into one durable FX snapshot.
    """

    def __init__(
        self,
        *,
        adapter: VietcombankFXAdapter,
        snapshot_store: CustomerCommercialFXSnapshotStore,
    ) -> None:
        if not isinstance(
            adapter,
            VietcombankFXAdapter,
        ):
            raise TypeError(
                "adapter must be VietcombankFXAdapter."
            )

        if not isinstance(
            snapshot_store,
            CustomerCommercialFXSnapshotStore,
        ):
            raise TypeError(
                "snapshot_store must be "
                "CustomerCommercialFXSnapshotStore."
            )

        if not snapshot_store.is_ready():
            raise RuntimeError(
                "Commercial FX snapshot store "
                "must be initialized."
            )

        self._adapter = adapter
        self._snapshot_store = snapshot_store

    def refresh_once(
        self,
    ) -> CustomerCommercialFXSnapshotRecord:
        """
        Fetch and durably publish one authoritative daily FX truth.
        """

        provider_result = (
            self._adapter.fetch()
        )

        snapshot_date = (
            provider_result
            .published_at
            .astimezone(
                VIETNAM_TIMEZONE
            )
            .date()
        )

        candidate = CustomerCommercialFXSnapshotRecord(
            snapshot_date=snapshot_date,
            source_id=provider_result.source_id,
            base_currency=provider_result.base_currency,
            quote_currency=provider_result.quote_currency,
            usd_vnd_rate=provider_result.usd_vnd_rate,
            published_at=provider_result.published_at,
            fetched_at=provider_result.fetched_at,
        )

        existing = self._snapshot_store.get(
            snapshot_date=candidate.snapshot_date,
            source_id=candidate.source_id,
            base_currency=candidate.base_currency,
            quote_currency=candidate.quote_currency,
        )

        if existing is not None:
            if self._same_authoritative_facts(
                existing=existing,
                candidate=candidate,
            ):
                return existing

            raise ValueError(
                "Commercial FX snapshot identity "
                "already exists with different "
                "authoritative facts."
            )

        return self._snapshot_store.save(
            candidate
        )

    @staticmethod
    def _same_authoritative_facts(
        *,
        existing: CustomerCommercialFXSnapshotRecord,
        candidate: CustomerCommercialFXSnapshotRecord,
    ) -> bool:
        """
        fetched_at is deliberately excluded.

        It records when TODOBA observed the provider response,
        not a new authoritative FX fact.
        """

        return (
            existing.snapshot_date
            == candidate.snapshot_date

            and existing.source_id
            == candidate.source_id

            and existing.base_currency
            == candidate.base_currency

            and existing.quote_currency
            == candidate.quote_currency

            and existing.usd_vnd_rate
            == candidate.usd_vnd_rate

            and existing.published_at
            == candidate.published_at
        )


@dataclass(
    frozen=True,
)
class CustomerCommercialFXDailyRefreshCycle:
    """
    Result of one explicitly executed refresh cycle.
    """

    cycle_number: int
    snapshot: CustomerCommercialFXSnapshotRecord


class CustomerCommercialFXDailyRefreshScheduler:
    """
    Daily 07:00 Vietnam timing owner.

    Business work remains in
    CustomerCommercialFXDailyRefreshService.
    """

    def __init__(
        self,
        *,
        refresh_service: CustomerCommercialFXDailyRefreshService,
        clock: Callable[
            [],
            datetime,
        ],
    ) -> None:
        if not isinstance(
            refresh_service,
            CustomerCommercialFXDailyRefreshService,
        ):
            raise TypeError(
                "refresh_service must be "
                "CustomerCommercialFXDailyRefreshService."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self._refresh_service = (
            refresh_service
        )
        self._clock = clock

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = (
            asyncio.Event()
        )

        self._cycle_count = 0

        self._last_cycle: Optional[
            CustomerCommercialFXDailyRefreshCycle
        ] = None

        self._last_error: Optional[
            Exception
        ] = None

    @property
    def running(
        self,
    ) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    @property
    def cycle_count(
        self,
    ) -> int:
        return self._cycle_count

    @property
    def last_cycle(
        self,
    ) -> (
        CustomerCommercialFXDailyRefreshCycle
        | None
    ):
        return self._last_cycle

    @property
    def last_error(
        self,
    ) -> Exception | None:
        return self._last_error

    def run_cycle(
        self,
    ) -> CustomerCommercialFXDailyRefreshCycle:
        snapshot = (
            self._refresh_service
            .refresh_once()
        )

        self._cycle_count += 1

        cycle = (
            CustomerCommercialFXDailyRefreshCycle(
                cycle_number=self._cycle_count,
                snapshot=snapshot,
            )
        )

        self._last_cycle = cycle

        return cycle

    async def start(
        self,
    ) -> bool:
        if self.running:
            return True

        self._stop_event = (
            asyncio.Event()
        )

        self._last_error = None

        self._task = asyncio.create_task(
            self._run(),
            name=(
                "todoba-commercial-fx-"
                "daily-refresh-scheduler"
            ),
        )

        return True

    async def stop(
        self,
    ) -> bool:
        if self._task is None:
            return True

        self._stop_event.set()

        await self._task

        self._task = None

        return True

    @staticmethod
    def next_run_at(
        current_time: datetime,
    ) -> datetime:
        """
        Return the next 07:00 Vietnam execution boundary.

        At exactly 07:00, today's boundary is already reached,
        so the next execution boundary is tomorrow.
        """

        normalized = (
            CustomerCommercialFXDailyRefreshScheduler
            ._normalize_clock_time(
                current_time
            )
        )

        local = normalized.astimezone(
            VIETNAM_TIMEZONE
        )

        candidate = datetime.combine(
            local.date(),
            time(
                hour=_REFRESH_HOUR,
                minute=_REFRESH_MINUTE,
                tzinfo=VIETNAM_TIMEZONE,
            ),
        )

        if local >= candidate:
            candidate = (
                candidate
                + timedelta(
                    days=1
                )
            )

        return candidate

    async def _run(
        self,
    ) -> None:
        """
        Wait until each daily 07:00 Vietnam boundary,
        then run one refresh cycle.
        """

        try:
            while not self._stop_event.is_set():
                current_time = (
                    self._read_clock()
                )

                next_run = (
                    self.next_run_at(
                        current_time
                    )
                )

                delay_seconds = (
                    next_run
                    .astimezone(
                        current_time.tzinfo
                    )
                    - current_time
                ).total_seconds()

                if delay_seconds < 0:
                    delay_seconds = 0

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=delay_seconds,
                    )

                    continue

                except asyncio.TimeoutError:
                    pass

                if self._stop_event.is_set():
                    continue

                self.run_cycle()

        except asyncio.CancelledError:
            raise

        except Exception as error:
            self._last_error = error
            self._stop_event.set()

    def _read_clock(
        self,
    ) -> datetime:
        value = self._clock()

        return self._normalize_clock_time(
            value
        )

    @staticmethod
    def _normalize_clock_time(
        value: datetime,
    ) -> datetime:
        if not isinstance(
            value,
            datetime,
        ):
            raise RuntimeError(
                "FX scheduler clock must return "
                "timezone-aware datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise RuntimeError(
                "FX scheduler clock must return "
                "timezone-aware datetime."
            )

        return value
