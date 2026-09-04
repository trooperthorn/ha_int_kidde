[![HACS Custom](https://img.shields.io/badge/HACS-custom-blue.svg?style=for-the-badge)](https://hacs.xyz)
[![Tests](https://img.shields.io/github/actions/workflow/status/trooperthorn/ha_int_kidde/tests.yaml?style=for-the-badge&label=tests)](https://github.com/trooperthorn/ha_int_kidde/actions/workflows/tests.yaml)

# Kidde HomeSafe Integration

Home Assistant integration for Kidde smoke, fire, and carbon monoxide
alarms, with **two connection paths**:

| Path | Devices | Data | Latency |
| ---- | ------- | ---- | ------- |
| **Cloud** (Kidde HomeSafe account) | WiFi "smart" models | Full: smoke/CO alarm state, IAQ, battery, faults, test/hush/identify commands | Polling (configurable, default 30 s, min 5 s) |
| **Local Bluetooth** (experimental) | Verified `KIDDE SMOKE CO` fingerprint | Presence, signal strength, identity correlation, raw unmapped protocol payload | Push, fully local; payload changes are diagnostic only |
| **Local Wi-Fi/LAN** (research) | Owner-identified 30CUAR-W installation | No operational properties mapped yet | Ayla Local Connect feasibility under investigation |

> [!IMPORTANT]
> Kidde publishes no LAN API for these alarms, but that does not prove one is
> absent. The installed 30CUAR-W units exposed no unauthenticated idle listener,
> and an app Ping produced no direct IPv4 phone-to-alarm traffic in an AP-level
> capture. Ayla documents optional authenticated Local Connect support, so LAN
> enrollment, key exchange, property reads, and WAN-loss behavior remain an
> active research track. See [docs/BLE_PROTOCOL.md](docs/BLE_PROTOCOL.md).

## Supported devices

Cloud (verified unless noted):

- Smoke + CO Alarm with Indoor Air Quality Monitor (**P4010ACSCOAQ-WF**)
- Smoke Alarm with Indoor Air Quality Monitor (**P4010ACSAQ-WF**)
- Smoke + CO Alarm with smart features (**P4010ACSCO-WF**), unverified
- Smoke Alarm with smart features (**P4010ACS-WF**)
- Water Leak + Freeze Detector (**60WLDR-W**)
- CO Alarm with Indoor Air Quality Monitor (**KN-COP-DP-10YL-AQ-WF**)
- Kidde DETECT™ Series Alarms (**30CUAR-W, 20SAR-W**)

Local Bluetooth (experimental):

- Devices matching the verified `KIDDE SMOKE CO`, Kidde manufacturer-data,
  and identity-frame fingerprint. The installed test units are owner-identified
  30CUAR-W alarms; the advertised name alone does not prove a printed model.

## Installation (HACS)

1. Add `https://github.com/trooperthorn/ha_int_kidde` as a custom
   repository in HACS (category: integration).
2. Install **Kidde HomeSafe** and restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → *Kidde HomeSafe*.

### Cloud setup

Choose **Kidde HomeSafe account (cloud)** and sign in with the account
from the Kidde app. The polling interval is adjustable afterwards via the
entry's **Configure** button. Re-authentication and reconfiguration flows
are built in, if the Kidde cloud invalidates your session you will be
prompted rather than the integration silently failing.

> [!CAUTION]
> You may get a notification from the Kidde app once you complete setup.
> Allow it, or it will break updates to Home Assistant.

### Local Bluetooth setup

If Home Assistant has a Bluetooth adapter or a
[Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html) in
range, discovered Kidde alarms appear automatically under Settings →
Devices & Services. You can also add them manually via **Add
Integration** → *Kidde HomeSafe* → **Bluetooth alarm (local)**.

Each alarm provides:

- **Bluetooth signal strength** (RSSI) sensor
- **Status payload** diagnostic sensor (live hex broadcast)
- **Status broadcast** diagnostic event, fires on a raw payload change for
  protocol capture; it is not a smoke, CO, or fault signal
- Locally correlated identity; exported diagnostics redact serial, MAC, and
  System ID values

The advertisement payload `0240020201` and GATT `0x1D02` value `00` are
verified idle fixtures across three installed alarms. Other values remain
unmapped and do not create alarm/problem entities.

## Entities (cloud)

Smoke/CO/water/freeze alarm binary sensors, hush state, fault/problem
sensors (low battery, end-of-life, sensor faults), air quality (IAQ,
TVOC, CO₂, humidity, pressure, temperature), battery, WiFi diagnostics,
plus **Test**, **Hush**, and **Identify** controls.

## Blueprints

Importable automation blueprints ship with the repository:

- [Smoke/CO Emergency Response](blueprints/automation/kidde_homesafe/smoke_co_emergency_response.yaml)
  - notify occupants, light the evacuation path, and run extra actions.
  The extra-actions hook is designed for pairing with other
  integrations, e.g. **UniFi Protect** (`camera.snapshot`, recording
  mode) or an **ELK-M1** panel (announcements, tasks).
- [BLE Protocol Capture](blueprints/automation/kidde_homesafe/ble_status_capture.yaml)
  - record an unmapped Bluetooth payload change for controlled protocol
  research. Do not use it for life-safety notification.

Import via **Settings → Automations & Scenes → Blueprints → Import
Blueprint** using the raw GitHub URL of the blueprint file.

## Diagnostics & debugging

- Every config entry supports **Download diagnostics** (secrets
  redacted).
- Enable debug logging via the entry's three-dot menu, or:

  ```yaml
  logger:
    logs:
      custom_components.kidde_homesafe: debug
  ```

## Local-first development status

Phase 0 foundations now include exact BLE fingerprinting, deterministic
capture redaction, embedded BLE/LAN identity correlation, and a canonical
field model carrying source, timestamp, freshness, and confidence. Transport
adapters must produce that model rather than creating entities directly. Raw
or provisional protocol bytes are never eligible for smoke/CO entities.

## Documentation

See [docs/README.md](docs/README.md) for protocol facts, architecture
rationale, and dated design decisions.

## Credits

- Cloud API originally mapped by
  [865charlesw/kidde-homesafe](https://github.com/865charlesw/kidde-homesafe)
  (MIT). The client is now vendored here with connection reuse and
  concurrent fetching for lower latency.
- Forked from
  [snell-evan-itt/Kidde-HomeSafe](https://github.com/snell-evan-itt/Kidde-HomeSafe).
