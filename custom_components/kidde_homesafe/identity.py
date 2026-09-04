"""Exact-device BLE/LAN identity helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

KIDDE_BLE_NAME = "KIDDE SMOKE CO"
KIDDE_OUI = "84:07:C4"
_ADDRESS_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")


def normalize_address(address: str) -> str:
    """Normalize and validate a public Bluetooth/Wi-Fi MAC address."""
    value = address.strip().replace("-", ":").upper()
    if not _ADDRESS_RE.fullmatch(value):
        raise ValueError("invalid MAC address")
    return value


def address_matches_system_id(address: str, system_id: str) -> bool:
    """Check the verified Windows-advertiser = System ID + 1 relationship."""
    advertised = bytes.fromhex(normalize_address(address).replace(":", ""))
    base = bytes.fromhex(normalize_address(system_id).replace(":", ""))
    return advertised[:5] == base[:5] and advertised[5] == (base[5] + 1) % 256


def diagnostic_token(value: str) -> str:
    """Return a non-reversible short token for local diagnostic correlation."""
    return hashlib.sha256(value.strip().upper().encode("utf-8")).hexdigest()[:12]


def friendly_ble_name(address: str) -> str:
    """Return a distinguishable label without exposing a full identifier."""
    normalized = normalize_address(address)
    return f"Kidde Smoke/CO {normalized[-5:]}"


@dataclass(frozen=True, slots=True)
class KiddeIdentity:
    """Correlated identity fields observed through BLE and LAN."""

    advertised_address: str
    serial_number: str | None = None
    system_id: str | None = None

    @property
    def correlation_verified(self) -> bool:
        if self.system_id is None:
            return False
        try:
            return address_matches_system_id(
                self.advertised_address, self.system_id
            )
        except ValueError:
            return False

    @property
    def stable_local_id(self) -> str:
        """Prefer stable embedded identity over scanner-specific address forms."""
        if self.system_id:
            normalized = normalize_address(self.system_id).replace(":", "").lower()
            return f"system_{normalized}"
        if self.serial_number:
            return f"serial_{self.serial_number.strip().lower()}"
        normalized = normalize_address(self.advertised_address).replace(":", "").lower()
        return f"ble_{normalized}"
