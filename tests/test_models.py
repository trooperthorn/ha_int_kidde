"""Tests for source, freshness, confidence, and safety reconciliation."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_PATH = Path(__file__).parents[1] / "custom_components" / "kidde_homesafe" / "models.py"
_spec = importlib.util.spec_from_file_location("kidde_models", _PATH)
assert _spec is not None and _spec.loader is not None
models = importlib.util.module_from_spec(_spec)
sys.modules["kidde_models"] = models
_spec.loader.exec_module(models)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def observation(value: object, *, source=None, confidence=None, age=0, ttl=30):
    """Build one observation for a shared field."""
    observed = NOW - timedelta(seconds=age)
    return models.FieldObservation(
        device_id="device_test",
        field="smoke_alarm",
        value=value,
        source=source or models.DataSource.LAN,
        observed_at=observed,
        confidence=confidence or models.Confidence.VERIFIED,
        expires_at=observed + timedelta(seconds=ttl),
        raw_field="smoke_alarm",
    )


def test_raw_protocol_bytes_never_resolve_to_entity() -> None:
    assert models.resolve_field(
        [observation("02FF", confidence=models.Confidence.RAW)], now=NOW
    ) is None


def test_fresh_alarm_true_beats_concurrent_false() -> None:
    resolved = models.resolve_field(
        [
            observation(False, source=models.DataSource.CLOUD),
            observation(True, source=models.DataSource.INTERCONNECT, age=1),
        ],
        now=NOW,
        safety_critical=True,
    )
    assert resolved is not None
    assert resolved.value is True
    assert resolved.source is models.DataSource.INTERCONNECT


def test_prior_alarm_is_not_cleared_by_stale_or_provisional_false() -> None:
    previous = models.ResolvedField(
        value=True,
        source=models.DataSource.BLUETOOTH,
        observed_at=NOW - timedelta(seconds=5),
        confidence=models.Confidence.VERIFIED,
        stale=False,
    )
    resolved = models.resolve_field(
        [observation(False, confidence=models.Confidence.PROVISIONAL)],
        now=NOW,
        safety_critical=True,
        previous=previous,
    )
    assert resolved is not None
    assert resolved.value is True
    assert resolved.stale is True


def test_new_verified_false_can_clear_prior_alarm() -> None:
    previous = models.ResolvedField(
        value=True,
        source=models.DataSource.BLUETOOTH,
        observed_at=NOW - timedelta(seconds=5),
        confidence=models.Confidence.VERIFIED,
        stale=False,
    )
    resolved = models.resolve_field(
        [observation(False)],
        now=NOW,
        safety_critical=True,
        previous=previous,
    )
    assert resolved is not None
    assert resolved.value is False
    assert resolved.stale is False


def test_naive_timestamp_rejected() -> None:
    try:
        models.FieldObservation(
            device_id="device_test",
            field="battery",
            value="ok",
            source=models.DataSource.LAN,
            observed_at=datetime(2026, 9, 1),
            confidence=models.Confidence.VERIFIED,
        )
    except ValueError as err:
        assert "timezone-aware" in str(err)
    else:
        raise AssertionError("naive datetime was accepted")
