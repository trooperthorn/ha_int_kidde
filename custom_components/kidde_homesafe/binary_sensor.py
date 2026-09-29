"""Binary sensor platform for Kidde Homesafe integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KiddeBLECoordinator, KiddeConfigEntry
from .entity import KiddeBLEEntity, KiddeEntity

PARALLEL_UPDATES = 0

# Constants for dictionary keys
KEY_MODEL = "model"

logger = logging.getLogger(__name__)


_BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="smoke_alarm",
        icon="mdi:smoke-detector-variant-alert",
        name="Smoke Alarm",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    BinarySensorEntityDescription(
        key="smoke_hushed",
        icon="mdi:smoke-detector-variant-off",
        name="Smoke Hushed",
    ),
    BinarySensorEntityDescription(
        key="co_alarm",
        icon="mdi:molecule-co",
        name="CO Alarm",
        device_class=BinarySensorDeviceClass.CO,
    ),
    BinarySensorEntityDescription(
        key="hardwire_smoke",
        icon="mdi:smoke-detector-variant-alert",
        name="Hardwire Smoke Alarm",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    BinarySensorEntityDescription(
        key="too_much_smoke",
        icon="mdi:smoke-detector-variant-alert",
        name="Too Much Smoke",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    BinarySensorEntityDescription(
        key="contact_lost",
        icon="mdi:smoke-detector-variant-off",
        name="Contact Lost",
    ),
    BinarySensorEntityDescription(
        key="lost",
        icon="mdi:smoke-detector-variant-off",
        name="Lost",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="water_alarm",
        icon="mdi:water-alert",
        name="Water Alert",
    ),
    BinarySensorEntityDescription(
        key="low_temp_alarm",
        icon="mdi:snowflake-alert",
        name="Freeze Alert",
    ),
    BinarySensorEntityDescription(
        key="low_battery_alarm",
        icon="mdi:battery-alert-variant",
        name="Battery Low Alert",
    ),
    BinarySensorEntityDescription(
        key="reset_flag",
        icon="mdi:history",
        name="Reset Flag",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="flt_lwbat_mb",
        icon="mdi:battery-alert",
        name="Main Board Low Battery Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_lwbat_wb",
        icon="mdi:battery-alert",
        name="Wireless Board Low Battery Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_fat_lwbat",
        icon="mdi:battery-alert",
        name="Fatal Low Battery Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_fat_eol",
        icon="mdi:calendar-alert",
        name="Fatal End of Life Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_eol",
        icon="mdi:calendar-alert",
        name="End of Life Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_pho",
        icon="mdi:alert-circle",
        name="Photoelectric Sensor Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_co",
        icon="mdi:alert-circle",
        name="CO Sensor Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="flt_i2c",
        icon="mdi:alert-circle",
        name="I2C Bus Fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)

_INVERSE_BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="offline",
        icon="mdi:wifi-alert",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)

_BATTERY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="battery_state",
        icon="mdi:battery",
        name="Battery State",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
)


_BLE_CLOUD_LINK_DESCRIPTION = BinarySensorEntityDescription(
    key="cloud_link",
    translation_key="cloud_link",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiddeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data
    if isinstance(coordinator, KiddeBLECoordinator):
        async_add_devices(
            [KiddeBLECloudLinkEntity(coordinator, _BLE_CLOUD_LINK_DESCRIPTION)]
        )
        return
    sensors: list[BinarySensorEntity] = []

    for device_id, device_data in coordinator.data.devices.items():
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Checking model: [%s]",
                coordinator.data.devices[device_id].get(KEY_MODEL, "Unknown"),
            )

        for entity_description in _BINARY_SENSOR_DESCRIPTIONS:
            if entity_description.key in device_data:
                sensors.append(
                    KiddeBinarySensorEntity(coordinator, device_id, entity_description)
                )

        for entity_description in _INVERSE_BINARY_SENSOR_DESCRIPTIONS:
            if entity_description.key in device_data:
                sensors.append(
                    KiddeInverseBinarySensorEntity(
                        coordinator, device_id, entity_description
                    )
                )

        for entity_description in _BATTERY_SENSOR_DESCRIPTIONS:
            if entity_description.key in device_data:
                sensors.append(
                    KiddeBatteryStateSensorEntity(
                        coordinator, device_id, entity_description
                    )
                )

    async_add_devices(sensors)


class KiddeBinarySensorEntity(KiddeEntity, BinarySensorEntity):
    """Binary sensor for Kidde HomeSafe."""

    @property
    def is_on(self) -> bool | None:
        """Return the value of the binary sensor."""
        return self.kidde_device.get(self.entity_description.key)


class KiddeInverseBinarySensorEntity(KiddeEntity, BinarySensorEntity):
    """Online sensor: on when the cloud does not report the device offline."""

    _available_when_offline = True

    @property
    def is_on(self) -> bool | None:
        """Return the value of the binary sensor."""
        value = self.kidde_device.get(self.entity_description.key)
        if value is None:
            return None
        return not value


class KiddeBatteryStateSensorEntity(KiddeEntity, BinarySensorEntity):
    """Binary sensor for Kidde HomeSafe."""

    @property
    def is_on(self) -> bool | None:
        """Return the value of the binary sensor."""
        value = self.kidde_device.get(self.entity_description.key)
        if value is None:
            return None
        return value not in ("Good", "ok")


class KiddeBLECloudLinkEntity(KiddeBLEEntity, BinarySensorEntity):
    """Cloud link as reported by the alarm in its BLE broadcast.

    Works during an internet outage, when the cloud entry cannot report it.
    """

    coordinator: KiddeBLECoordinator

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle an updated advertisement."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return True while the alarm reports a working cloud link."""
        advertisement = self.coordinator.advertisement
        return advertisement.cloud_link if advertisement else None
