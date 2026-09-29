# Kidde BLE Advertisement Protocol Notes

Status of the reverse-engineering effort for Bluetooth Low Energy data
broadcast by alarms named `KIDDE SMOKE CO`. The installed test units are
owner-identified 30CUAR-W alarms; the BLE name alone is not a model identifier.

Kidde publishes no local API documentation. Live testing has not found an
unauthenticated idle LAN listener, but Ayla documents optional authenticated
LAN and BLE Local Connect. The repository therefore treats LAN support as
unproven rather than impossible. Advertisement monitoring remains passive;
the separate GATT findings below came from explicitly controlled reads.

## Advertisement layout

Example raw advertisement (captured via a Home Assistant Bluetooth proxy):

```
0201060f094b4944444520534d4f4b4520434f08ff810c0240020201
12160a185445535443415054555245303030310916232a8407c4000010
```

| AD type | Content | Meaning |
| ------- | ------- | ------- |
| `0x01` Flags | `06` | LE General Discoverable, no BR/EDR |
| `0x09` Complete Local Name | `KIDDE SMOKE CO` | Device name |
| `0xFF` Manufacturer Data | company `0x0C81` (3201, Walter Kidde Portable Equipment) + 5-byte payload | Status payload (below) |
| `0x16` Service Data, UUID `0x180A` | 15 ASCII bytes | Serial-like device identity (synthetic example above: `TESTCAPTURE0001`) |
| `0x16` Service Data, UUID `0x2A23` (System ID) | 6 bytes | Base MAC of the module (advertising MAC − 1) |

## Manufacturer status payload

All observed units broadcast the same payload in the idle state:

```
02 40 02 02 01
```

**Field-verified (2026-08-20):** this payload was confirmed against live
alarms with fire, smoke, and carbon monoxide all inactive, it is the
authoritative "all clear" pattern the integration's *Non-idle status*
sensor compares against.

### Cloud link byte

**Field-verified (2026-09-29):** byte 3 reports the alarm's link to the
Kidde cloud. `0x02` is connected; `0x05` is disconnected, the state in
which the alarm blinks red for lost internet.

```
02 40 02 02 01   connected (idle)
02 40 02 05 01   cloud disconnected
```

Evidence: four alarms on one site, compared with Home Assistant's Nabu
Casa Remote UI connectivity over seven days. Every internet outage showed
up on all four alarms within seconds, with no alarm, test, or hush:

| Outage | Alarms to `05` | Remote UI lost | Alarms back to `02` | Remote UI back |
| --- | --- | --- | --- | --- |
| 2026-09-24, ~11 h | 00:09:35 to 00:09:52 | 00:09:45 | 11:16:34 to 11:16:37 | 11:19:33 |
| 2026-09-25, ~9.5 h | 19:15:36 to 19:16:12 | 19:16:21 | 04:51:27 (all four) | 04:51:16 |
| 2026-09-26, ~7 s | 16:26:47 (one alarm) | 16:26:56 | 16:26:54 | 16:27:07 |

The alarms report the loss up to about 10 seconds before Remote UI does,
and recover within about 11 seconds of it. The outages came from the IoT
network losing DNS, so `05` may mean "cannot reach the cloud" for any
reason (DNS, WAN, Kidde service). Whether loss of Wi-Fi itself produces a
different value is not yet captured.

The integration maps byte 3 only when the other four bytes equal the idle
fixture; any other combination stays `unmapped`. It uses the value for the
Bluetooth entry's **Cloud link** sensor and to mark a cloud entry's
entities unavailable while the same alarm (matched by serial number)
reports `05`.

### Remaining bytes

Byte meanings other than byte 3 are **not yet mapped**, mapping them requires captures
taken while an alarm is testing, hushed, alarming (smoke/CO), or
reporting low battery / end-of-life. The integration is built to make
those captures easy:

* The **Status payload** diagnostic sensor shows the live hex payload.
* The **Status broadcast** diagnostic event records a payload change.
* A payload change is logged with an opaque device token rather than an address.
* Downloaded diagnostics redact serial-like service data and System ID.

If you capture a payload other than `0240020201`, record the controlled state
and firmware/model provenance. Do not publish raw serial, MAC, System ID, DSN,
LAN key, Wi-Fi credentials, account data, or location information.

## Known device identity facts (verified against live units)

* Serial-like identities decode as ASCII from `0x180A` service data and match
  the serial component of observed LAN hostnames.
* System ID (`0x2A23`) equals the advertising MAC address minus one.
* These UUIDs are service-data keys in the advertisement; they do not prove
  that the corresponding standard GATT services are exposed.

## Read-only proprietary GATT findings

Service discovery on a matching installed alarm exposed proprietary service
`0x1D00`, write-only characteristic `0x1D01`, and read/notify characteristic
`0x1D02`. A single read of `0x1D02` on each of three apparently idle alarms
returned the same one-byte value, `00`.

`00` is therefore an idle fixture, not a decoded alarm state. No notification
subscription, pairing, or write was performed. `0x1D01` remains prohibited for
exploratory writes. The integration does not actively connect to installed
alarms during normal operation.

## Latency characteristics

Home Assistant delivers passive advertisements as push updates. Actual
latency depends on detector firmware, scan coverage, and any Bluetooth proxy;
RSSI or advertisement presence by itself is not detector-health evidence.
