"""Sensor platform for Kidde HomeSafe integration."""

from __future__ import annotations

import datetime
import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import KiddeBLECoordinator, KiddeConfigEntry, KiddeCoordinator
from .entity import KiddeBLEEntity, KiddeEntity

PARALLEL_UPDATES = 0

KEY_MODEL = "model"
KEY_VALUE = "value"
KEY_STATUS = "status"
KEY_UNIT = "Unit"
KEY_CAPABILITIES = "capabilities"
KEY_IAQ = "iaq"
KEY_TEMPERATURE = "temperature"
KEY_MB_MODEL: Final = "mb_model"
LIFE_SENSOR_KEY: Final = "life"

logger = logging.getLogger(__name__)

# mb_model values; see docs/protocol.md for the full device model table.
MB_MODELS_DETECT_SERIES: Final = {48, 46}

# batt_volt/battery_voltage read as 0 on DETECT-series devices; see docs/protocol.md.
_SKIP_SIMPLE_SENSOR_KEYS: Final = {"batt_volt", "battery_voltage"}

LIFE_SENSOR_CONFIG: Final[dict] = {
    48: {
        "name": "Days to replace",
        "unit": UnitOfTime.DAYS,
    },
    46: {
        "name": "Days to replace",
        "unit": UnitOfTime.DAYS,
    },
    "default": {
        "name": "Weeks to replace",
        "unit": UnitOfTime.WEEKS,
    },
}


_TIMESTAMP_DESCRIPTIONS = (
    SensorEntityDescription(
        key="last_seen",
        icon="mdi:home-clock",
        name="Last Seen",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="last_test_time",
        icon="mdi:home-clock",
        name="Last Test Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="iaq_last_test_time",
        icon="mdi:home-clock",
        name="IAQ Last Test Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)

_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="overall_iaq_status",
        icon="mdi:air-filter",
        name="Overall Air Quality",
        device_class=SensorDeviceClass.ENUM,
        options=["Very Bad", "Bad", "Moderate", "Good"],
    ),
    SensorEntityDescription(
        key="smoke_level",
        icon="mdi:smoke",
        name="Smoke Level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co_level",
        icon="mdi:molecule-co",
        name="CO Level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co_ppm",
        icon="mdi:molecule-co",
        name="CO PPM",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    SensorEntityDescription(
        key="batt_volt",
        icon="mdi:battery",
        name="Battery Voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=LIFE_SENSOR_KEY,
        icon="mdi:calendar-clock",
        name="Weeks to replace",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
    ),
    SensorEntityDescription(
        key="ap_rssi",
        icon="mdi:wifi-strength-3",
        name="Signal strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="ssid",
        icon="mdi:wifi",
        name="SSID",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="alarm_interval",
        icon="mdi:alarm-check",
        name="Alarm Interval",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="alarm_reset_time",
        icon="mdi:alarm-snooze",
        name="Alarm Reset Time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_level",
        icon="mdi:battery-high",
        name="Battery Level",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery_voltage",
        icon="mdi:battery",
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    SensorEntityDescription(
        key="checkin_interval",
        icon="mdi:clock-check",
        name="Checkin Interval",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    SensorEntityDescription(
        key="hold_alarm_time",
        icon="mdi:alarm-plus",
        name="Alarm Hold Time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="rapid_temperature_variation_status",
        icon="mdi:swap-vertical-variant",
        name="Temperature Variation Status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="temperature_variation_value",
        icon="mdi:swap-vertical-variant",
        name="Temperature Variation",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:home-thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
)

_SENSOR_MEASUREMENT_DESCRIPTIONS = (
    SensorEntityDescription(
        key="iaq_temperature",
        name="Indoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hpa",
        name="Air Pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tvoc",
        name="Total VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="iaq",
        name="Indoor Air Quality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        name="CO₂ Level",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


_BLE_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="status_payload",
        translation_key="status_payload",
        icon="mdi:hexadecimal",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KiddeConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    if isinstance(coordinator, KiddeBLECoordinator):
        async_add_devices(
            KiddeBLESensorEntity(coordinator, description)
            for description in _BLE_SENSOR_DESCRIPTIONS
        )
        return
    sensors: list[SensorEntity] = []

    life_description = next(
        (desc for desc in _SENSOR_DESCRIPTIONS if desc.key == LIFE_SENSOR_KEY),
        None,
    )

    for device_id, device_data in coordinator.data.devices.items():
        mb_model = device_data.get(KEY_MB_MODEL)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Checking model: [%s] (MB:%s)",
                coordinator.data.devices[device_id].get(KEY_MODEL, "Unknown"),
                mb_model,
            )

        for entity_description in _TIMESTAMP_DESCRIPTIONS:
            if entity_description.key in device_data:
                sensors.append(
                    KiddeSensorTimestampEntity(
                        coordinator, device_id, entity_description
                    )
                )

        if LIFE_SENSOR_KEY in device_data and life_description:
            sensors.append(
                KiddeSensorLifeEntity(coordinator, device_id, life_description)
            )

        for entity_description in _SENSOR_DESCRIPTIONS:
            # 'life' is handled above by KiddeSensorLifeEntity, which varies
            # name/unit by mb_model.
            if entity_description.key == LIFE_SENSOR_KEY:
                continue

            if (
                entity_description.key in _SKIP_SIMPLE_SENSOR_KEYS
                and mb_model in MB_MODELS_DETECT_SERIES
            ):
                logger.debug(
                    "Skipping sensor '%s' because mb_model %s is DETECT series.",
                    entity_description.key,
                    mb_model,
                )
                continue

            if entity_description.key in device_data:
                sensors.append(
                    KiddeSensorEntity(coordinator, device_id, entity_description)
                )

        for entity_description in _SENSOR_MEASUREMENT_DESCRIPTIONS:
            if entity_description.key in device_data:
                sensors.append(
                    KiddeSensorMeasurementEntity(
                        coordinator, device_id, entity_description
                    )
                )

    async_add_devices(sensors)


class KiddeSensorTimestampEntity(KiddeEntity, SensorEntity):
    """A KiddeSensoryEntity which returns a datetime."""

    @property
    def native_value(self) -> datetime.datetime | None:
        """Return the native value of the sensor."""
        value = self.kidde_device.get(self.entity_description.key)
        dtype = type(value)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "%s, of type %s is %s",
                self.entity_description.key,
                dtype,
                value,
            )
        if value is None:
            return value
        stripped = value.strip("Z").split(".")[0]
        try:
            return datetime.datetime.strptime(stripped, "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=datetime.UTC
            )
        except ValueError as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.error("Error parsing datetime '%s': %s", value, e)
            return None


class KiddeSensorLifeEntity(KiddeEntity, SensorEntity):
    """Custom entity for the 'life' sensor to conditionally adjust units."""

    def __init__(
        self,
        coordinator: KiddeCoordinator,
        device_id: int,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the custom life sensor."""
        super().__init__(coordinator, device_id, entity_description)
        # Set as instance attributes, not properties: the base entity_description
        # already exposes name/unit as attributes, and these must vary per device.
        config = self._model_config
        self._attr_native_unit_of_measurement = config["unit"]
        self._attr_name = config["name"]

    @property
    def _model_config(self) -> dict:
        """Get the specific config (name/unit) based on the device mb_model."""
        device_identifier = self.kidde_device.get(KEY_MB_MODEL, "default")
        return LIFE_SENSOR_CONFIG.get(device_identifier, LIFE_SENSOR_CONFIG["default"])

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        return self.kidde_device.get(LIFE_SENSOR_KEY)


class KiddeSensorEntity(KiddeEntity, SensorEntity):
    """Sensor for Kidde HomeSafe."""

    @property
    def native_value(self) -> str | None | float | int:
        """Return the native value of the sensor."""
        value = self.kidde_device.get(self.entity_description.key)
        dtype = type(value)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "%s, of type %s is %s",
                self.entity_description.key,
                dtype,
                value,
            )
        return value


class KiddeSensorMeasurementEntity(KiddeEntity, SensorEntity):
    """Measurement Sensor for Kidde HomeSafe."""

    @property
    def state_class(self) -> str:
        """Return the state class of sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        entity_dict = self.kidde_device.get(self.entity_description.key)
        if isinstance(entity_dict, dict):
            sensor_value = entity_dict.get(KEY_VALUE)
        else:
            ktype = type(entity_dict)
            if logger.isEnabledFor(logging.DEBUG):
                logger.warning(
                    "Unexpected type [%s], expected entity dict for [%s]",
                    ktype,
                    self.entity_description.key,
                )
            sensor_value = None
        return sensor_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement of the sensor."""
        entity_dict = self.kidde_device.get(self.entity_description.key)

        if not isinstance(entity_dict, dict):
            if logger.isEnabledFor(logging.DEBUG):
                logger.warning(
                    "Unexpected type [%s], expected entity dict for [%s]",
                    type(entity_dict),
                    self.entity_description.key,
                )
            return None

        entity_unit = entity_dict.get(KEY_UNIT, "").upper()

        match entity_unit:
            case "C":
                return UnitOfTemperature.CELSIUS
            case "F":
                return UnitOfTemperature.FAHRENHEIT
            case "%RH":
                return PERCENTAGE
            case "HPA":
                return UnitOfPressure.PA
            case "PPB":
                return CONCENTRATION_PARTS_PER_BILLION
            case "PPM":
                return CONCENTRATION_PARTS_PER_MILLION
            case "V":
                return UnitOfElectricPotential.VOLT
            case _:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.warning(
                        "Unknown unit [%s] for sensor [%s]",
                        entity_unit,
                        self.entity_description.key,
                    )
                return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes for the value sensor (Status)."""
        entity_dict = self.kidde_device.get(self.entity_description.key)
        attribute_dict = None
        if isinstance(entity_dict, dict):
            attribute_dict = {"Status": entity_dict.get(KEY_STATUS)}
        else:
            ktype = type(entity_dict)
            if logger.isEnabledFor(logging.DEBUG):
                logger.warning(
                    "Unexpected type [%s], expected state attributes dict for [%s]",
                    ktype,
                    self.entity_description.key,
                )
            attribute_dict = {"Status": None}
        return attribute_dict


class KiddeBLESensorEntity(KiddeBLEEntity, SensorEntity):
    """Sensor sourced from passive BLE advertisements."""

    coordinator: KiddeBLECoordinator

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle an updated advertisement."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | None:
        """Return the native value of the sensor."""
        advertisement = self.coordinator.advertisement
        if advertisement is None:
            return None
        if self.entity_description.key == "rssi":
            return advertisement.rssi
        if self.entity_description.key == "status_payload":
            return advertisement.status_payload_hex
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | bool] | None:
        """Expose confidence metadata without assigning alarm semantics."""
        if self.entity_description.key != "status_payload":
            return None
        advertisement = self.coordinator.advertisement
        if advertisement is None:
            return None
        return {
            "classification": advertisement.status_payload_classification,
            "fingerprint_verified": advertisement.fingerprint_verified,
            "identity_correlation_verified": (
                advertisement.identity_correlation_verified
            ),
            "semantics": "unmapped",
        }
