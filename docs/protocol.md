# Kidde Cloud API Device Facts

Facts about the `mb_model` field returned by the Kidde HomeSafe cloud API for
each device, and how the integration uses it. This is cloud/API data, not
BLE advertisement data; for that, see [BLE_PROTOCOL.md](BLE_PROTOCOL.md).

## mb_model values

| `mb_model` | Meaning | Verified |
| ---------- | ------- | -------- |
| `48` | DETECT-series Smoke/CO alarm | Verified against a live device |
| `46` | DETECT-series Smoke-only alarm | Verified against a live device |
| anything else, or missing | Older or non-DETECT model | Unverified, no live device confirms an exhaustive list |

`sensor.py` collects `48` and `46` into `MB_MODELS_DETECT_SERIES` and uses
that set for two things:

- **Life-remaining unit**: DETECT-series devices report days until sensor
  replacement (`LIFE_SENSOR_CONFIG`); older devices report weeks. The
  `KiddeSensorLifeEntity` looks up the right name and unit from
  `LIFE_SENSOR_CONFIG` at entity construction, keyed by `mb_model`, falling
  back to the `"default"` (weeks) entry.
- **Battery voltage exclusion**: `batt_volt` and `battery_voltage` read back
  as `0` or otherwise unhelpful values on DETECT-series devices, so those
  sensors are skipped entirely for any device whose `mb_model` is in
  `MB_MODELS_DETECT_SERIES` (`_SKIP_SIMPLE_SENSOR_KEYS`).

If a future capture shows a `mb_model` outside `{46, 48}` that also needs
either behavior, add it to `MB_MODELS_DETECT_SERIES` and update this table.
