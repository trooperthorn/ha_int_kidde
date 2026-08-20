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

# Real captures from Kidde "KIDDE SMOKE CO" alarms via a Home Assistant
# Bluetooth proxy (idle state).
REAL_CAPTURES = [
    ("84:07:C4:3C:3A:35", "343032343330314132413132424146", "8407c43c3a34", "4024301A2A12BAF", "84:07:C4:3C:3A:34"),
    ("84:07:C4:3C:3A:A7", "343032343330313832413132413230", "8407c43c3aa6", "402430182A12A20", "84:07:C4:3C:3A:A6"),
    ("84:07:C4:3C:25:6B", "343032343330313232384242413244", "8407c43c256a", "4024301228BBA2D", "84:07:C4:3C:25:6A"),
    ("84:07:C4:3C:41:AD", "343032343330313632413439363342", "8407c43c41ac", "402430162A4963B", "84:07:C4:3C:41:AC"),
]


@pytest.mark.parametrize(
    ("address", "dis_hex", "sysid_hex", "expected_serial", "expected_sysid"),
    REAL_CAPTURES,
)
def test_parse_real_capture(
    address: str,
    dis_hex: str,
    sysid_hex: str,
    expected_serial: str,
    expected_sysid: str,
) -> None:
    """Parse real advertisements captured from live alarms."""
    adv = ble.parse_advertisement(
        address=address,
        local_name="KIDDE SMOKE CO",
        rssi=-50,
        manufacturer_data={3201: bytes.fromhex("0240020201")},
        service_data={
            DIS_UUID: bytes.fromhex(dis_hex),
            SYSTEM_ID_UUID: bytes.fromhex(sysid_hex),
        },
    )
    assert adv is not None
    assert adv.serial_number == expected_serial
    assert adv.system_id == expected_sysid
    assert adv.status_payload_hex == "0240020201"
    assert adv.is_idle_payload is True
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
        address="84:07:C4:3C:3A:35",
        local_name="KIDDE SMOKE CO",
        rssi=-60,
        manufacturer_data={},
        service_data={},
    )
    assert adv is not None
    assert adv.status_payload is None
    assert adv.is_idle_payload is None


def test_non_idle_payload_flagged() -> None:
    """A payload differing from the idle pattern is flagged non-idle."""
    adv = ble.parse_advertisement(
        address="84:07:C4:3C:3A:35",
        local_name="KIDDE SMOKE CO",
        rssi=-60,
        manufacturer_data={3201: bytes.fromhex("0240020203")},
        service_data={},
    )
    assert adv is not None
    assert adv.is_idle_payload is False


def test_undecodable_serial_returns_none() -> None:
    """Binary garbage in the DIS service data must not crash the parser."""
    adv = ble.parse_advertisement(
        address="84:07:C4:3C:3A:35",
        local_name="KIDDE SMOKE CO",
        rssi=-60,
        manufacturer_data={3201: bytes.fromhex("0240020201")},
        service_data={DIS_UUID: b"\xff\xfe\x00"},
    )
    assert adv is not None
    assert adv.serial_number is None
