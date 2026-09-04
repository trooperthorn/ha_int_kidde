"""Redacted JSONL capture harness for Kidde protocol research.

The harness records observations; it does not send BLE GATT writes, detector
commands, or cloud requests. Use a private key file outside the repository so
the same device can be correlated across captures without publishing its raw
identifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

IDENTITY_SERVICE_UUIDS = {
    "0000180a-0000-1000-8000-00805f9b34fb",
    "00002a23-0000-1000-8000-00805f9b34fb",
}
SECRET_KEYS = {
    "cookie",
    "cookies",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "lan_key",
    "wifi_password",
}
IDENTIFIER_KEYS = {
    "address",
    "bluetooth_address",
    "mac",
    "wifi_mac",
    "serial",
    "serial_number",
    "system_id",
    "dsn",
    "hostname",
    "ip",
    "ip_address",
    "ssid",
}
_MAC_RE = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")


class CaptureRedactor:
    """Deterministically tokenize identifiers and remove secrets."""

    def __init__(self, key: bytes) -> None:
        if len(key) < 16:
            raise ValueError("redaction key must contain at least 16 bytes")
        self._key = key

    def token(self, kind: str, value: object) -> str:
        """Return a stable HMAC token scoped to an identifier kind."""
        normalized = f"{kind.lower()}\0{str(value).strip().upper()}".encode()
        digest = hmac.new(self._key, normalized, hashlib.sha256).hexdigest()[:16]
        return f"{kind.lower()}_{digest}"

    def redact(self, value: Any, key: str | None = None) -> Any:
        """Recursively redact a capture structure."""
        normalized_key = key.lower() if key else None
        if normalized_key in SECRET_KEYS:
            return "**REDACTED**"
        if normalized_key in IDENTIFIER_KEYS and value is not None:
            return self.token(normalized_key, value)
        if isinstance(value, Mapping):
            if normalized_key == "service_data":
                return {
                    str(uuid): (
                        self.token("service_identity", payload)
                        if str(uuid).lower() in IDENTITY_SERVICE_UUIDS
                        else self.redact(payload, str(uuid))
                    )
                    for uuid, payload in value.items()
                }
            return {
                str(item_key): self.redact(item, str(item_key))
                for item_key, item in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            return _MAC_RE.sub(
                lambda match: self.token("embedded_mac", match.group(0)), value
            )
        return value


def build_record(
    redactor: CaptureRedactor,
    *,
    capture_type: str,
    model: str,
    firmware: str | None,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one timestamped, redacted capture record."""
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "capture_type": capture_type,
        "model": model,
        "firmware": firmware,
        "observation": redactor.redact(observation),
    }


def append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    """Append one compact JSON record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True))
        stream.write("\n")


def _load_key(path: Path) -> bytes:
    key = path.read_bytes().strip()
    if len(key) < 16:
        raise ValueError("redaction key file must contain at least 16 bytes")
    return key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture-type", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--firmware")
    parser.add_argument(
        "--observation-json",
        required=True,
        help="JSON object containing the raw observation to redact and append",
    )
    args = parser.parse_args()

    observation = json.loads(args.observation_json)
    if not isinstance(observation, dict):
        raise ValueError("observation-json must be a JSON object")
    redactor = CaptureRedactor(_load_key(args.key_file))
    append_jsonl(
        args.output,
        build_record(
            redactor,
            capture_type=args.capture_type,
            model=args.model,
            firmware=args.firmware,
            observation=observation,
        ),
    )


if __name__ == "__main__":
    main()
