"""Tests for the Kidde BLE advertisement parser.

These run without Home Assistant installed:

    pytest tests/test_ble.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load ble.py directly so the test does not import the package __init__
# (which requires Home Assistant).
_BLE_PATH = (
    Path(__file__).parent.parent
    / "custom_components"
    / "kidde_homesafe"
    / "ble.py"
)
_spec = importlib.util.spec_from_file_location("kidde_ble", _BLE_PATH)
assert _spec is not None and _spec.loader is not None
ble = importlib.util.module_from_spec(_spec)
sys.modules["kidde_ble"] = ble
_spec.loader.exec_module(ble)

DIS_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
SYSTEM_ID_UUID = "00002a23-0000-1000-8000-00805f9b34fb"

# Synthetic/redacted fixtures preserving the verified identity relationship.
CAPTURES = [
    ("84:07:C4:00:00:11", "TESTCAPTURE0001", "84:07:C4:00:00:10"),
    ("84:07:C4:00:00:21", "TESTCAPTURE0002", "84:07:C4:00:00:20"),
    ("84:07:C4:00:00:31", "TESTCAPTURE0003", "84:07:C4:00:00:30"),
    ("84:07:C4:00:00:41", "TESTCAPTURE0004", "84:07:C4:00:00:40"),
]


@pytest.mark.parametrize(
    ("address", "expected_serial", "expected_sysid"),
    CAPTURES,
)
def test_parse_verified_capture_shape(
    address: str,
    expected_serial: str,
    expected_sysid: str,
) -> None:
    """Parse a redacted fixture matching the verified advertisement shape."""
    adv = ble.parse_advertisement(
        address=address,
        local_name="KIDDE SMOKE CO",
        rssi=-50,
        manufacturer_data={3201: bytes.fromhex("0240020201")},
        service_data={
            DIS_UUID: expected_serial.encode("ascii"),
            SYSTEM_ID_UUID: bytes.fromhex(expected_sysid.replace(":", "")),
        },
    )
    assert adv is not None
    assert adv.serial_number == expected_serial
    assert adv.system_id == expected_sysid
    assert adv.status_payload_hex == "0240020201"
    assert adv.is_idle_payload is True
    assert adv.status_payload_classification == "verified_idle_fixture"
    assert adv.fingerprint_verified is True
    assert adv.identity_correlation_verified is True
    assert adv.rssi == -50


def test_non_kidde_advertisement_rejected() -> None:
    """An unrelated advertisement must not parse."""
    assert (
        ble.parse_advertisement(
            address="00:11:22:33:44:55",
            local_name="SomeOtherDevice",
            rssi=-60,
            manufacturer_data={76: b"\x02\x15"},
            service_data={},
        )
        is None
    )


def test_name_only_advertisement_accepted() -> None:
    """A Kidde-named advertisement without manufacturer data still parses."""
    adv = ble.parse_advertisement(
        address="84:07:C4:00:00:11",
        local_name="KIDDE SMOKE CO",
        rssi=-60,
        manufacturer_data={},
        service_data={},
    )
    assert adv is not None
    assert adv.status_payload is None
    assert adv.is_idle_payload is None
    assert adv.fingerprint_verified is False


def test_non_idle_payload_flagged() -> None:
    """A differing payload remains explicitly unmapped, not a problem."""
    adv = ble.parse_advertisement(
        address="84:07:C4:00:00:11",
        local_name="KIDDE SMOKE CO",
        rssi=-60,
        manufacturer_data={3201: bytes.fromhex("0240020203")},
        service_data={},
    )
    assert adv is not None
    assert adv.is_idle_payload is False
    assert adv.status_payload_classification == "unmapped"


def test_broad_kidde_name_without_verified_oui_rejected() -> None:
    """Do not claim unrelated Kidde product families from broad filters."""
    assert ble.parse_advertisement(
        address="00:11:22:33:44:55",
        local_name="KIDDE OTHER",
        rssi=-60,
        manufacturer_data={3201: bytes.fromhex("0240020201")},
        service_data={},
    ) is None


def test_fragment_with_verified_oui_and_manufacturer_is_provisional() -> None:
    """Allow merged advertisement fragments without calling them verified."""
    adv = ble.parse_advertisement(
        address="84:07:C4:00:00:11",
        local_name=None,
        rssi=-60,
        manufacturer_data={3201: bytes.fromhex("0240020201")},
        service_data={},
    )
    assert adv is not None
    assert adv.fingerprint_verified is False


def test_undecodable_serial_returns_none() -> None:
    """Binary garbage in the DIS service data must not crash the parser."""
    adv = ble.parse_advertisement(
        address="84:07:C4:00:00:11",
        local_name="KIDDE SMOKE CO",
        rssi=-60,
        manufacturer_data={3201: bytes.fromhex("0240020201")},
        service_data={DIS_UUID: b"\xff\xfe\x00"},
    )
    assert adv is not None
    assert adv.serial_number is None
