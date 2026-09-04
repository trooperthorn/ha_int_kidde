"""Tests for the Phase 0 capture redactor."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).parents[1] / "tools" / "kidde_capture.py"
_spec = importlib.util.spec_from_file_location("kidde_capture", _PATH)
assert _spec is not None and _spec.loader is not None
capture = importlib.util.module_from_spec(_spec)
sys.modules["kidde_capture"] = capture
_spec.loader.exec_module(capture)


def test_redactor_removes_secrets_and_tokenizes_identity() -> None:
    redactor = capture.CaptureRedactor(b"0123456789abcdef-test-key")
    result = redactor.redact(
        {
            "address": "84:07:C4:00:00:11",
            "cookies": "secret-cookie",
            "service_data": {
                "0000180a-0000-1000-8000-00805f9b34fb": "54455354",
                "other": "00",
            },
        }
    )
    assert result["cookies"] == "**REDACTED**"
    assert result["address"].startswith("address_")
    assert "84:07:C4" not in result["address"]
    assert result["service_data"]["other"] == "00"
    assert result["service_data"]["0000180a-0000-1000-8000-00805f9b34fb"].startswith(
        "service_identity_"
    )


def test_same_key_produces_stable_tokens() -> None:
    first = capture.CaptureRedactor(b"0123456789abcdef-test-key")
    second = capture.CaptureRedactor(b"0123456789abcdef-test-key")
    assert first.token("serial", "TEST") == second.token("serial", "TEST")
