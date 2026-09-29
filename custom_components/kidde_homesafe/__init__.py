"""The Kidde HomeSafe integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .api import KiddeClient
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_COOKIES,
    CONF_UPDATE_INTERVAL,
    CONNECTION_TYPE_BLUETOOTH,
    CONNECTION_TYPE_CLOUD,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import KiddeBLECoordinator, KiddeConfigEntry, KiddeCoordinator

_LOGGER = logging.getLogger(__name__)

CLOUD_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

BLE_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SENSOR,
]


def _connection_type(entry: KiddeConfigEntry) -> str:
    """Return the connection type of a config entry."""
    return entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD)


def _platforms(entry: KiddeConfigEntry) -> list[Platform]:
    """Return the platforms for a config entry."""
    if _connection_type(entry) == CONNECTION_TYPE_BLUETOOTH:
        return BLE_PLATFORMS
    return CLOUD_PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: KiddeConfigEntry) -> bool:
    """Set up Kidde HomeSafe from a config entry."""
    if _connection_type(entry) == CONNECTION_TYPE_BLUETOOTH:
        await _async_setup_ble_entry(hass, entry)
    else:
        await _async_setup_cloud_entry(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_setup_cloud_entry(
    hass: HomeAssistant, entry: KiddeConfigEntry
) -> None:
    """Set up a cloud (Kidde HomeSafe account) config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = KiddeClient(entry.data[CONF_COOKIES], session)
    update_interval = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )
    coordinator = KiddeCoordinator(hass, entry, client, update_interval)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator


async def _async_setup_ble_entry(
    hass: HomeAssistant, entry: KiddeConfigEntry
) -> None:
    """Set up a local Bluetooth config entry for a single alarm."""
    address: str = entry.data["address"]
    coordinator = KiddeBLECoordinator(hass, address)
    entry.runtime_data = coordinator
    if coordinator.advertisement is None:
        _LOGGER.debug(
            "No advertisement seen yet for Kidde alarm %s; "
            "entities will populate on the next broadcast",
            address,
        )
    # Start listening for advertisements; stops automatically on unload.
    entry.async_on_unload(coordinator.async_start())


async def _async_update_listener(
    hass: HomeAssistant, entry: KiddeConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: KiddeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, _platforms(entry)
    )


async def async_migrate_entry(hass: HomeAssistant, entry: KiddeConfigEntry) -> bool:
    """Migrate old config entries to the current format."""
    if entry.version > 2:
        # Downgrade from a future version is not supported.
        return False

    if entry.version == 1:
        data = dict(entry.data)
        options = dict(entry.options)
        data.setdefault(CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD)
        if CONF_UPDATE_INTERVAL in data:
            options.setdefault(CONF_UPDATE_INTERVAL, data.pop(CONF_UPDATE_INTERVAL))
        hass.config_entries.async_update_entry(
            entry, data=data, options=options, version=2
        )
        _LOGGER.debug("Migrated Kidde HomeSafe entry %s to version 2", entry.entry_id)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: KiddeConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removal of a device that the coordinator no longer reports."""
    coordinator = entry.runtime_data
    if isinstance(coordinator, KiddeBLECoordinator):
        # A BLE entry maps 1:1 to its device; removing the device should
        # be done by removing the entry instead.
        return False
    if coordinator.data is None or coordinator.data.devices is None:
        return True
    active_labels = {
        str(device.get("label"))
        for device in coordinator.data.devices.values()
    }
    return not any(
        identifier[0] == DOMAIN and identifier[1] in active_labels
        for identifier in device_entry.identifiers
    )
