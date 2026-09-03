# Design

## BLE path is push-only, with no polling fallback

`KiddeBLECoordinator` (`coordinator.py`) is a
`PassiveBluetoothDataUpdateCoordinator`: it never connects to the alarm and
never polls. Updates arrive only when an advertisement is relayed by a local
Bluetooth adapter or an ESPHome/Shelly Bluetooth proxy, so observed latency
is the alarm's own advertising interval (a few seconds). There is no polling
fallback for this path because passive BLE advertisement monitoring has no
connection to poll: the alternative would be to actively connect to the
alarm, which the integration deliberately avoids (see
[BLE_PROTOCOL.md](BLE_PROTOCOL.md), "Read-only proprietary GATT findings").
The cloud path (`KiddeCoordinator`) is a conventional polling
`DataUpdateCoordinator` because the cloud API has no push mechanism.

## Entity identity spans BLE and cloud transports

`KiddeBLEEntity.__init__` (`entity.py`) keeps the existing
`{address}_{key}` unique ID for entities, so upgrading does not orphan
existing entity registrations, while also registering the device under a
second identifier: the stable ID derived from the embedded serial/system ID
in the advertisement (`KiddeIdentity.stable_local_id`). This lets the device
registry correlate a BLE-only device with the same physical alarm if it is
later also added over the cloud path, without breaking entities that
already exist under the advertiser MAC address.
