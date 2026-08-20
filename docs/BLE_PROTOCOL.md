# Kidde BLE Advertisement Protocol Notes

Status of the reverse-engineering effort for the Bluetooth Low Energy
advertisements broadcast by Kidde wireless-interconnect smoke/CO alarms
(advertised local name `KIDDE SMOKE CO`, e.g. the P4010ACS/DCS "Wire-Free
Interconnect" family).

Kidde publishes no local API documentation. The WiFi ("HomeSafe") models
only talk to `api.homesafe.kidde.com` — there is **no LAN/IP API** to
negotiate with on the local network. The BLE alarms, however, broadcast
useful data continuously, which this integration consumes passively
(no connection, no battery impact, works through ESPHome/Shelly
Bluetooth proxies).

## Advertisement layout

Example raw advertisement (captured via a Home Assistant Bluetooth proxy):

```
0201060f094b4944444520534d4f4b4520434f08ff810c0240020201
12160a1834303234333031413241313242414609 16232a8407c43c3a34
```

| AD type | Content | Meaning |
| ------- | ------- | ------- |
| `0x01` Flags | `06` | LE General Discoverable, no BR/EDR |
| `0x09` Complete Local Name | `KIDDE SMOKE CO` | Device name |
| `0xFF` Manufacturer Data | company `0x0C81` (3201, Walter Kidde Portable Equipment) + 5-byte payload | Status payload (below) |
| `0x16` Service Data, UUID `0x180A` (Device Information) | 15 ASCII bytes | Device **serial number**, e.g. `4024301A2A12BAF` |
| `0x16` Service Data, UUID `0x2A23` (System ID) | 6 bytes | Base MAC of the module (advertising MAC − 1) |

## Manufacturer status payload

All observed units broadcast the same payload in the idle (no alarm,
no fault) state:

```
02 40 02 02 01
```

Byte meanings are **not yet mapped** — mapping them requires captures
taken while an alarm is testing, hushed, alarming (smoke/CO), or
reporting low battery / end-of-life. The integration is built to make
those captures easy:

* The **Status payload** diagnostic sensor shows the live hex payload.
* The **Status broadcast** event entity fires whenever the payload
  changes, recording the previous and new payload.
* A payload change is also logged at WARNING level in the Home
  Assistant log, together with the address.
* The config entry's **Download diagnostics** includes the full raw
  advertisement.

If you capture a payload other than `0240020201`, please open an issue
with the payload, and what the alarm was doing at the time (test button
pressed, hush, real/canned smoke, low battery chirp, etc.).

## Known device identity facts (verified against live units)

* Serial numbers decode as ASCII from the `0x180A` service data:
  `4024301A2A12BAF`, `402430182A12A20`, `4024301228BBA2D`,
  `402430162A4963B`.
* System ID (`0x2A23`) equals the advertising MAC address minus one.
* The alarms advertise as `connectable`, exposing at least the standard
  Device Information service over GATT. Actively connecting is
  deliberately **not** done by this integration: connections wake the
  alarm's radio (battery cost), occupy proxy connection slots, and the
  vendor GATT surface is undocumented. All data above is available
  passively.

## Latency characteristics

Passive advertisements arrive every few seconds. Home Assistant's
Bluetooth stack delivers each advertisement to the integration
immediately (push, no polling), so a payload change is visible in Home
Assistant within one advertising interval — typically 1–3 seconds —
versus up to the configured polling interval (default 30 s) for the
cloud path.
