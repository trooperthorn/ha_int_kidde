# Kidde capture harness

`kidde_capture.py` creates timestamped, redacted JSONL fixtures for protocol
research. It performs no network or Bluetooth operations itself. Feed it data
from a passive scan, read-only GATT check, packet summary, or app/cloud sample.

Keep the redaction key and raw captures outside the repository. Example:

```powershell
python tools/kidde_capture.py `
  --key-file C:\private\kidde-capture.key `
  --output C:\private\captures\idle.jsonl `
  --capture-type ble_gatt_read `
  --model 30CUAR-W `
  --observation-json '{"address":"84:07:C4:00:00:01","value_hex":"00"}'
```

The key must contain at least 16 random bytes. Identifier tokens remain stable
only for captures processed with the same key. Cookies, passwords, tokens,
Wi-Fi credentials, and LAN keys are removed rather than tokenized.

Do not record or execute unknown GATT writes. Do not use real smoke or CO.
