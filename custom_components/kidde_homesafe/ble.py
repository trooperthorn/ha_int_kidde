"""Parser for Kidde BLE advertisements.

Kidde wireless-interconnect smoke/CO alarms (advertised local name
"KIDDE SMOKE CO") broadcast BLE advertisements that carry:

* Manufacturer data under Bluetooth SIG company ID ``0x0C81`` (3201,
  Walter Kidde Portable Equipment) — a short status payload.
* Service data for the Device Information service (``0x180A``) — the
  ASCII serial number of the alarm.
* Service data for the System ID characteristic (``0x2A23``) — a 6-byte
  identifier derived from the device's Bluetooth MAC address.

Observed payload in the idle (no alarm) state on multiple units:

    manufacturer_data[3201] = 02 40 02 02 01

The payload is not publicly documented by Kidde. The parser therefore
exposes the raw payload (for diagnostics and for capturing alarm-state
samples) alongside the fields that are stable and verified. See
``docs/BLE_PROTOCOL.md`` in the repository for the current state of the
reverse-engineering effort.

This module is intentionally free of Home Assistant imports so it can be
unit-tested standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KIDDE_MANUFACTURER_ID = 3201  # 0x0C81

DEVICE_INFORMATION_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
SYSTEM_ID_UUID = "00002a23-0000-1000-8000-00805f9b34fb"

# The idle-state status payload observed on P4010ACS/DCS-class BLE alarms.
IDLE_STATUS_PAYLOAD = bytes.fromhex("0240020201")


@dataclass(frozen=True)
class KiddeBLEAdvertisement:
    """Parsed fields from a Kidde BLE advertisement."""

    address: str
    local_name: str | None
    rssi: int | None
    serial_number: str | None
    system_id: str | None
    status_payload: bytes | None

    @property
    def status_payload_hex(self) -> str | None:
        """Raw manufacturer status payload as a hex string."""
        if self.status_payload is None:
            return None
        return self.status_payload.hex()

    @property
    def is_idle_payload(self) -> bool | None:
        """Whether the status payload matches the known idle pattern.

        Returns None when no payload is present. A False value means the
        alarm is reporting *something* other than the known idle state —
        which may be an alarm, a fault, or an as-yet-unmapped state.
        """
        if self.status_payload is None:
            return None
        return self.status_payload == IDLE_STATUS_PAYLOAD


def _decode_serial(data: bytes) -> str | None:
    """Decode the ASCII serial number from 0x180A service data."""
    try:
        serial = data.decode("ascii").strip("\x00 ")
    except UnicodeDecodeError:
        return None
    return serial or None


def _decode_system_id(data: bytes) -> str | None:
    """Decode the 0x2A23 System ID service data as colon-separated hex."""
    if not data:
        return None
    return ":".join(f"{byte:02X}" for byte in data)


def parse_advertisement(
    address: str,
    local_name: str | None,
    rssi: int | None,
    manufacturer_data: dict[int, bytes],
    service_data: dict[str, bytes],
) -> KiddeBLEAdvertisement | None:
    """Parse a BLE advertisement from a Kidde alarm.

    Returns None if the advertisement does not look like a Kidde alarm.
    """
    status_payload = manufacturer_data.get(KIDDE_MANUFACTURER_ID)
    is_kidde_name = bool(local_name) and local_name.upper().startswith("KIDDE")
    if status_payload is None and not is_kidde_name:
        return None

    serial_number = None
    if (dis_data := service_data.get(DEVICE_INFORMATION_SERVICE_UUID)) is not None:
        serial_number = _decode_serial(dis_data)

    system_id = None
    if (sysid_data := service_data.get(SYSTEM_ID_UUID)) is not None:
        system_id = _decode_system_id(sysid_data)

    return KiddeBLEAdvertisement(
        address=address,
        local_name=local_name,
        rssi=rssi,
        serial_number=serial_number,
        system_id=system_id,
        status_payload=bytes(status_payload) if status_payload is not None else None,
    )


def parse_service_info(service_info: Any) -> KiddeBLEAdvertisement | None:
    """Parse a Home Assistant ``BluetoothServiceInfoBleak``-like object.

    Duck-typed so this module stays importable without Home Assistant.
    """
    return parse_advertisement(
        address=service_info.address,
        local_name=service_info.name,
        rssi=service_info.rssi,
        manufacturer_data={
            mid: bytes(data)
            for mid, data in service_info.manufacturer_data.items()
        },
        service_data={
            uuid: bytes(data)
            for uuid, data in service_info.service_data.items()
        },
    )
