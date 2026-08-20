[![HACS Custom](https://img.shields.io/badge/HACS-custom-blue.svg?style=for-the-badge)](https://hacs.xyz)
[![Tests](https://img.shields.io/github/actions/workflow/status/trooperthorn/ha_int_kidde/tests.yaml?style=for-the-badge&label=tests)](https://github.com/trooperthorn/ha_int_kidde/actions/workflows/tests.yaml)

# Kidde HomeSafe Integration

Home Assistant integration for Kidde smoke, fire, and carbon monoxide
alarms — with **two connection paths**:

| Path | Devices | Data | Latency |
| ---- | ------- | ---- | ------- |
| **Cloud** (Kidde HomeSafe account) | WiFi "smart" models | Full: smoke/CO alarm state, IAQ, battery, faults, test/hush/identify commands | Polling (configurable, default 30 s, min 5 s) |
| **Local Bluetooth** (new) | BLE wireless-interconnect alarms (`KIDDE SMOKE CO`) | Identity, presence, signal strength, live status payload | Push — 1–3 s, fully local, works via ESPHome/Shelly Bluetooth proxies |

> [!NOTE]
> Kidde offers **no local IP/LAN API** — the WiFi models speak only to the
> Kidde cloud. Local Bluetooth monitoring is the only cloud-free channel,
> and this integration consumes it passively (no connections, no battery
> impact on the alarms). See [docs/BLE_PROTOCOL.md](docs/BLE_PROTOCOL.md)
> for the protocol details and how you can help map the remaining bytes.

## Supported devices

Cloud (verified unless noted):

- Smoke + CO Alarm with Indoor Air Quality Monitor (**P4010ACSCOAQ-WF**)
- Smoke Alarm with Indoor Air Quality Monitor (**P4010ACSAQ-WF**)
- Smoke + CO Alarm with smart features (**P4010ACSCO-WF**) — unverified
- Smoke Alarm with smart features (**P4010ACS-WF**)
- Water Leak + Freeze Detector (**60WLDR-W**)
- CO Alarm with Indoor Air Quality Monitor (**KN-COP-DP-10YL-AQ-WF**)
- Kidde DETECT™ Series Alarms (**30CUAR-W, 20SAR-W**)

Local Bluetooth:

- Wireless-interconnect BLE smoke/CO alarms advertising as
  `KIDDE SMOKE CO` (e.g. the P4010ACS/DCS wire-free interconnect family)

## Installation (HACS)

1. Add `https://github.com/trooperthorn/ha_int_kidde` as a custom
   repository in HACS (category: integration).
2. Install **Kidde HomeSafe** and restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → *Kidde HomeSafe*.

### Cloud setup

Choose **Kidde HomeSafe account (cloud)** and sign in with the account
from the Kidde app. The polling interval is adjustable afterwards via the
entry's **Configure** button. Re-authentication and reconfiguration flows
are built in — if the Kidde cloud invalidates your session you will be
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
- **Non-idle status** problem sensor — on when the alarm broadcasts
  anything other than its known idle pattern
- **Status broadcast** event entity — fires within seconds of any
  payload change, ideal for automations
- Device identity: serial number, MAC, System ID — decoded locally

## Entities (cloud)

Smoke/CO/water/freeze alarm binary sensors, hush state, fault/problem
sensors (low battery, end-of-life, sensor faults), air quality (IAQ,
TVOC, CO₂, humidity, pressure, temperature), battery, WiFi diagnostics,
plus **Test**, **Hush**, and **Identify** controls.

## Blueprints

Importable automation blueprints ship with the repository:

- [Smoke/CO Emergency Response](blueprints/automation/kidde_homesafe/smoke_co_emergency_response.yaml)
  — notify occupants, light the evacuation path, and run extra actions.
  The extra-actions hook is designed for pairing with other
  integrations, e.g. **UniFi Protect** (`camera.snapshot`, recording
  mode) or an **ELK-M1** panel (announcements, tasks).
- [BLE Status Capture](blueprints/automation/kidde_homesafe/ble_status_capture.yaml)
  — get notified the moment a Bluetooth alarm changes its broadcast, and
  help map the protocol.

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

## Credits

- Cloud API originally mapped by
  [865charlesw/kidde-homesafe](https://github.com/865charlesw/kidde-homesafe)
  (MIT). The client is now vendored here with connection reuse and
  concurrent fetching for lower latency.
- Forked from
  [snell-evan-itt/Kidde-HomeSafe](https://github.com/snell-evan-itt/Kidde-HomeSafe).
