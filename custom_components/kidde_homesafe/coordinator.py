"""Coordinators for the Kidde HomeSafe integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    KiddeClient,
    KiddeClientAuthError,
    KiddeClientCommunicationError,
    KiddeDataset,
)
from .ble import KiddeBLEAdvertisement, parse_service_info
from .const import CLOUD_TIMEOUT, DOMAIN
from .identity import diagnostic_token

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

type KiddeConfigEntry = ConfigEntry[KiddeCoordinator | KiddeBLECoordinator]


class KiddeCoordinator(DataUpdateCoordinator[KiddeDataset]):
    """Coordinator for Kidde HomeSafe cloud polling."""

    config_entry: KiddeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KiddeConfigEntry,
        client: KiddeClient,
        update_interval: int,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client

    async def _async_update_data(self) -> KiddeDataset:
        """Fetch data from the Kidde cloud."""
        try:
            async with asyncio.timeout(CLOUD_TIMEOUT):
                return await self.client.get_data(get_events=False)
        except KiddeClientAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (KiddeClientCommunicationError, TimeoutError) as err:
            raise UpdateFailed(
                f"Error communicating with the Kidde cloud: {err}"
            ) from err


class KiddeBLECoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Coordinator receiving passive BLE advertisements from a Kidde alarm.

    Updates arrive as soon as an advertisement is relayed by any local
    Bluetooth adapter or ESPHome/Shelly Bluetooth proxy — no polling and
    no connection to the alarm, so latency is the advertising interval
    of the alarm itself (a few seconds).
    """

    config_entry: KiddeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            address=address,
            mode=BluetoothScanningMode.PASSIVE,
            connectable=False,
        )
        self.advertisement: KiddeBLEAdvertisement | None = None
        self.last_service_info: BluetoothServiceInfoBleak | None = None
        # Seed with the most recent advertisement HA has already seen, so
        # entities have data immediately after setup.
        if service_info := bluetooth.async_last_service_info(
            hass, address, connectable=False
        ):
            self._parse(service_info)

    def _parse(self, service_info: BluetoothServiceInfoBleak) -> bool:
        """Parse an advertisement; return True if it parsed as a Kidde one."""
        parsed = parse_service_info(service_info)
        if parsed is None:
            return False
        self.last_service_info = service_info
        self.advertisement = parsed
        return True

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth advertisement event."""
        previous = self.advertisement
        if not self._parse(service_info):
            return
        current = self.advertisement
        if (
            previous is not None
            and current is not None
            and previous.status_payload != current.status_payload
        ):
            _LOGGER.info(
                (
                    "Unmapped Kidde BLE payload changed for device token %s "
                    "from %s to %s; this is diagnostic protocol data, not a "
                    "verified alarm or fault"
                ),
                diagnostic_token(service_info.address),
                previous.status_payload_hex,
                current.status_payload_hex,
            )
        super()._async_handle_bluetooth_event(service_info, change)
