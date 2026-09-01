"""Canonical local-first data model for Kidde observations.

This module intentionally has no Home Assistant imports so protocol captures and
reconciliation rules can be tested independently of Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Iterable, Mapping


class DataSource(StrEnum):
    """Transport that produced an observation."""

    LAN = "lan"
    BLUETOOTH = "bluetooth"
    INTERCONNECT = "interconnect"
    CLOUD = "cloud"


class Confidence(StrEnum):
    """How strongly a protocol field's meaning has been established."""

    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    RAW = "raw"


_CONFIDENCE_RANK = {
    Confidence.RAW: 0,
    Confidence.PROVISIONAL: 1,
    Confidence.VERIFIED: 2,
}

DEFAULT_SOURCE_ORDER = (
    DataSource.LAN,
    DataSource.BLUETOOTH,
    DataSource.INTERCONNECT,
    DataSource.CLOUD,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class FieldObservation:
    """One value reported by one transport at one point in time."""

    device_id: str
    field: str
    value: Any
    source: DataSource
    observed_at: datetime
    confidence: Confidence
    expires_at: datetime | None = None
    raw_field: str | None = None

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        if self.expires_at is not None:
            _require_aware(self.expires_at, "expires_at")
            if self.expires_at < self.observed_at:
                raise ValueError("expires_at cannot precede observed_at")
        if not self.device_id or not self.field:
            raise ValueError("device_id and field are required")

    def is_stale(self, now: datetime | None = None) -> bool:
        """Return whether this value is past its explicit freshness limit."""
        if self.expires_at is None:
            return False
        instant = now or _utc_now()
        _require_aware(instant, "now")
        return instant > self.expires_at


@dataclass(frozen=True, slots=True)
class ResolvedField:
    """Selected canonical value plus its provenance."""

    value: Any
    source: DataSource
    observed_at: datetime
    confidence: Confidence
    stale: bool
    raw_field: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceSnapshot:
    """Canonical per-device state assembled from multiple transports."""

    device_id: str
    fields: Mapping[str, ResolvedField] = field(default_factory=dict)
    transport_last_seen: Mapping[DataSource, datetime] = field(default_factory=dict)


def _sort_key(
    observation: FieldObservation,
    source_rank: Mapping[DataSource, int],
) -> tuple[datetime, int, int]:
    return (
        observation.observed_at,
        _CONFIDENCE_RANK[observation.confidence],
        -source_rank.get(observation.source, len(source_rank)),
    )


def resolve_field(
    observations: Iterable[FieldObservation],
    *,
    now: datetime | None = None,
    source_order: Iterable[DataSource] = DEFAULT_SOURCE_ORDER,
    safety_critical: bool = False,
    previous: ResolvedField | None = None,
) -> ResolvedField | None:
    """Resolve observations without silently converting uncertainty to safety.

    Raw/unmapped protocol bytes are never eligible for canonical entities. For a
    safety-critical boolean, a fresh positive beats a concurrent negative. A
    prior positive is held as stale until a newer verified negative clears it.
    Callers can expose ``stale`` as unavailable while retaining the positive
    value; they must not publish it as an all-clear.
    """
    instant = now or _utc_now()
    _require_aware(instant, "now")
    candidates = [
        item for item in observations if item.confidence is not Confidence.RAW
    ]
    if not candidates:
        return replace(previous, stale=True) if previous is not None else None

    device_fields = {(item.device_id, item.field) for item in candidates}
    if len(device_fields) != 1:
        raise ValueError("observations must describe exactly one device field")

    rank = {source: index for index, source in enumerate(source_order)}
    fresh = [item for item in candidates if not item.is_stale(instant)]

    if safety_critical:
        fresh_positive = [item for item in fresh if item.value is True]
        if fresh_positive:
            selected = max(fresh_positive, key=lambda item: _sort_key(item, rank))
            return _resolved(selected, stale=False)
        if previous is not None and previous.value is True:
            clearing = [
                item
                for item in fresh
                if item.value is False
                and item.confidence is Confidence.VERIFIED
                and item.observed_at > previous.observed_at
            ]
            if not clearing:
                return replace(previous, stale=True)

    pool = fresh or candidates
    selected = max(pool, key=lambda item: _sort_key(item, rank))
    return _resolved(selected, stale=selected.is_stale(instant))


def _resolved(observation: FieldObservation, *, stale: bool) -> ResolvedField:
    return ResolvedField(
        value=observation.value,
        source=observation.source,
        observed_at=observation.observed_at,
        confidence=observation.confidence,
        stale=stale,
        raw_field=observation.raw_field,
    )
