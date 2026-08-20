"""Diagnostics support for Kidde HomeSafe."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import KiddeBLECoordinator, KiddeConfigEntry

TO_REDACT = {
    "cookies",
    "email",
    "serial_number",
    "ssid",
    "address",
    "address1",
    "address2",
    "city",
    "state",
    "postal_code",
    "zip",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "phone",
    "wifi_mac",
    "mac",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KiddeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    diagnostics: dict[str, Any] = {
        "entry": {
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
    }

    if isinstance(coordinator, KiddeBLECoordinator):
        advertisement = coordinator.advertisement
        service_info = coordinator.last_service_info
        diagnostics["ble"] = {
            "available": coordinator.available,
            "advertisement": (
                async_redact_data(
                    {
                        **asdict(advertisement),
                        "status_payload": advertisement.status_payload_hex,
                    },
                    TO_REDACT,
                )
                if advertisement
                else None
            ),
            "status_payload_hex": (
                advertisement.status_payload_hex if advertisement else None
            ),
            "raw_service_info": (
                {
                    "name": service_info.name,
                    "rssi": service_info.rssi,
                    "manufacturer_data": {
                        str(mid): data.hex()
                        for mid, data in service_info.manufacturer_data.items()
                    },
                    "service_data": {
                        uuid: data.hex()
                        for uuid, data in service_info.service_data.items()
                    },
                    "service_uuids": list(service_info.service_uuids),
                }
                if service_info
                else None
            ),
        }
    elif coordinator.data is not None:
        diagnostics["cloud"] = {
            "locations": async_redact_data(
                coordinator.data.locations or {}, TO_REDACT
            ),
            "devices": async_redact_data(
                coordinator.data.devices or {}, TO_REDACT
            ),
        }

    return diagnostics
