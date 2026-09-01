"""Transport contract shared by LAN, BLE, interconnect, and cloud adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field

from ..models import DataSource, FieldObservation


@dataclass(frozen=True, slots=True)
class TransportCapabilities:
    """Fields and operations proven for one device/firmware combination."""

    readable_fields: frozenset[str] = field(default_factory=frozenset)
    push_fields: frozenset[str] = field(default_factory=frozenset)
    commands: frozenset[str] = field(default_factory=frozenset)
    metadata: Mapping[str, str] = field(default_factory=dict)


class KiddeTransport(ABC):
    """Side-effect-free observation API for one transport."""

    source: DataSource

    @abstractmethod
    async def discover(self) -> Mapping[str, TransportCapabilities]:
        """Return devices and capabilities proven by this transport."""

    @abstractmethod
    async def read(self, device_id: str) -> tuple[FieldObservation, ...]:
        """Read current observations without sending detector commands."""

    async def subscribe(self, device_id: str) -> AsyncIterator[FieldObservation]:
        """Yield push observations when supported."""
        if False:  # pragma: no cover - makes this an async generator by contract
            yield FieldObservation  # type: ignore[misc]
        raise NotImplementedError("push updates are not supported by this transport")
