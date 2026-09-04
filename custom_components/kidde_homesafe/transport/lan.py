"""Conservative scaffolding for a future authenticated Ayla LAN adapter.

The installed alarms did not expose an idle listener on the commonly observed
Ayla port. This module can probe a user-supplied endpoint, but it deliberately
does not guess property paths, bootstrap cloud credentials, or claim LAN
capabilities before an exact-model capture proves them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from ..models import DataSource, FieldObservation
from .base import KiddeTransport, TransportCapabilities

DEFAULT_AYLA_LAN_PORT = 10275


class LanProtocolNotVerifiedError(RuntimeError):
    """Raised when code attempts to consume an unmapped LAN protocol."""


@dataclass(frozen=True, slots=True)
class LanEndpoint:
    """Manual local endpoint associated with a stable device identity."""

    host: str
    port: int = DEFAULT_AYLA_LAN_PORT

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("host is required")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")


async def probe_tcp_endpoint(endpoint: LanEndpoint, timeout: float = 2.0) -> bool:
    """Test TCP reachability without sending application data."""
    writer: asyncio.StreamWriter | None = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(endpoint.host, endpoint.port), timeout
        )
        return True
    except (OSError, TimeoutError):
        return False
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()


Probe = Callable[[LanEndpoint, float], Awaitable[bool]]


class AylaLanTransport(KiddeTransport):
    """Disabled-by-design LAN transport pending authenticated captures."""

    source = DataSource.LAN

    def __init__(
        self,
        endpoints: Mapping[str, LanEndpoint],
        *,
        timeout: float = 2.0,
        probe: Probe = probe_tcp_endpoint,
    ) -> None:
        self._endpoints = dict(endpoints)
        self._timeout = timeout
        self._probe = probe

    async def discover(self) -> Mapping[str, TransportCapabilities]:
        """Report endpoint reachability but no unverified properties."""
        results = await asyncio.gather(
            *(
                self._probe(endpoint, self._timeout)
                for endpoint in self._endpoints.values()
            )
        )
        return {
            device_id: TransportCapabilities(
                metadata={
                    "endpoint_configured": "true",
                    "tcp_reachable": str(reachable).lower(),
                    "protocol_verified": "false",
                }
            )
            for device_id, reachable in zip(
                self._endpoints, results, strict=True
            )
        }

    async def read(self, device_id: str) -> tuple[FieldObservation, ...]:
        """Refuse property reads until the exact protocol is verified."""
        if device_id not in self._endpoints:
            raise KeyError(device_id)
        raise LanProtocolNotVerifiedError(
            "Kidde/Ayla LAN property mapping and authentication are not verified"
        )
