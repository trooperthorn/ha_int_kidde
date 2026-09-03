"""Parser for Kidde BLE advertisements.

Kidde smoke/CO alarms with the advertised local name ``KIDDE SMOKE CO``
broadcast BLE advertisements that carry:

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
KIDDE_LOCAL_NAME = "KIDDE SMOKE CO"
KIDDE_ADDRESS_PREFIX = "84:07:C4:"

DEVICE_INFORMATION_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
SYSTEM_ID_UUID = "00002a23-0000-1000-8000-00805f9b34fb"

# See docs/BLE_PROTOCOL.md "Manufacturer status payload".
IDLE_STATUS_PAYLOAD = bytes.fromhex("0240020201")
EXPECTED_STATUS_PAYLOAD_LENGTH = len(IDLE_STATUS_PAYLOAD)


@dataclass(frozen=True)
class KiddeBLEAdvertisement:
    """Parsed fields from a Kidde BLE advertisement."""

    address: str
    local_name: str | None
    rssi: int | None
    serial_number: str | None
    system_id: str | None
    status_payload: bytes | None
    fingerprint_verified: bool
    identity_correlation_verified: bool

    @property
    def status_payload_hex(self) -> str | None:
        """Raw manufacturer status payload as a hex string."""
        if self.status_payload is None:
            return None
        return self.status_payload.hex()

    @property
    def is_idle_payload(self) -> bool | None:
        """Whether the status payload matches the known idle pattern.

        Returns None when no payload is present. A False value means only that
        the bytes differ from the observed idle fixture. It must not be
        interpreted as an alarm or problem until the payload is mapped.
        """
        if self.status_payload is None:
            return None
        return self.status_payload == IDLE_STATUS_PAYLOAD

    @property
    def status_payload_classification(self) -> str:
        """Classify protocol confidence without inventing state semantics."""
        if self.status_payload is None:
            return "missing"
        if len(self.status_payload) != EXPECTED_STATUS_PAYLOAD_LENGTH:
            return "malformed"
        if self.status_payload == IDLE_STATUS_PAYLOAD:
            return "verified_idle_fixture"
        return "unmapped"


def _decode_serial(data: bytes) -> str | None:
    """Decode the ASCII serial number from 0x180A service data."""
    try:
        serial = data.decode("ascii").strip("\x00 ")
    except UnicodeDecodeError:
        return None
    return serial or None


def _decode_system_id(data: bytes) -> str | None:
    """Decode the 0x2A23 System ID service data as colon-separated hex."""
    if len(data) != 6:
        return None
    return ":".join(f"{byte:02X}" for byte in data)


def _identity_correlation_verified(address: str, system_id: str | None) -> bool:
    """Check the observed advertiser-address = System-ID + 1 relation."""
    if system_id is None:
        return False
    try:
        advertised = bytes.fromhex(address.replace("-", ":").replace(":", ""))
        base = bytes.fromhex(system_id.replace(":", ""))
    except ValueError:
        return False
    return (
        len(advertised) == 6
        and advertised[:5] == base[:5]
        and advertised[5] == (base[5] + 1) % 256
    )


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
    exact_name = bool(local_name) and local_name.strip().upper() == KIDDE_LOCAL_NAME
    has_verified_oui = address.replace("-", ":").upper().startswith(
        KIDDE_ADDRESS_PREFIX
    )
    if not exact_name and not (status_payload is not None and has_verified_oui):
        return None

    serial_number = None
    if (dis_data := service_data.get(DEVICE_INFORMATION_SERVICE_UUID)) is not None:
        serial_number = _decode_serial(dis_data)

    system_id = None
    if (sysid_data := service_data.get(SYSTEM_ID_UUID)) is not None:
        system_id = _decode_system_id(sysid_data)

    fingerprint_verified = (
        exact_name
        and status_payload is not None
        and len(status_payload) == EXPECTED_STATUS_PAYLOAD_LENGTH
        and (serial_number is not None or system_id is not None)
    )

    return KiddeBLEAdvertisement(
        address=address,
        local_name=local_name,
        rssi=rssi,
        serial_number=serial_number,
        system_id=system_id,
        status_payload=bytes(status_payload) if status_payload is not None else None,
        fingerprint_verified=fingerprint_verified,
        identity_correlation_verified=_identity_correlation_verified(
            address, system_id
        ),
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
