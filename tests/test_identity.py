"""Tests for deterministic cross-transport identity handling."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "kidde_homesafe"
    / "identity.py"
)
_spec = importlib.util.spec_from_file_location("kidde_identity", _PATH)
assert _spec is not None and _spec.loader is not None
identity = importlib.util.module_from_spec(_spec)
sys.modules["kidde_identity"] = identity
_spec.loader.exec_module(identity)


def test_verified_system_id_address_relationship() -> None:
    assert identity.address_matches_system_id(
        "84:07:C4:00:00:11", "84:07:C4:00:00:10"
    )
    assert not identity.address_matches_system_id(
        "84:07:C4:00:00:12", "84:07:C4:00:00:10"
    )


def test_embedded_identity_preferred_for_stable_id() -> None:
    value = identity.KiddeIdentity(
        advertised_address="84:07:C4:00:00:11",
        serial_number="TESTCAPTURE0001",
        system_id="84:07:C4:00:00:10",
    )
    assert value.correlation_verified is True
    assert value.stable_local_id == "system_8407c4000010"


def test_diagnostic_token_is_stable_and_does_not_expose_value() -> None:
    first = identity.diagnostic_token("84:07:C4:00:00:11")
    second = identity.diagnostic_token("84:07:C4:00:00:11")
    assert first == second
    assert "8407" not in first
