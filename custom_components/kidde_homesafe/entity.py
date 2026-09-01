"""Entity base classes for Kidde HomeSafe."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import KiddeClientError, KiddeCommand
from .const import DOMAIN, MANUFACTURER
from .coordinator import KiddeBLECoordinator, KiddeCoordinator
from .identity import KiddeIdentity, friendly_ble_name

KEY_MODEL = "model"

logger = logging.getLogger(__name__)

MODEL_NAMES = {
    "wifiiaqdetector": "Smoke Detector with IAQ",
    "waterleakdetector": "Water Leak + Freeze Detector",
    "wifidetector": "Smoke Detector",
    "cowifidetector": "Carbon Monoxide Detector",
    "EssWFAC": "Smoke + CO Alarm (AC)",
}


class KiddeEntity(CoordinatorEntity[KiddeCoordinator]):
    """Entity base class for cloud-connected Kidde devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KiddeCoordinator,
        device_id: int,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description

    @property
    def kidde_device(self) -> dict[str, Any]:
        """The device from the coordinator's data."""
        return self.coordinator.data.devices[self.device_id]

    @property
    def available(self) -> bool:
        """Return whether the device is still present in the dataset."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.devices is not None
            and self.device_id in self.coordinator.data.devices
        )

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return f"{self.kidde_device['label']}_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device information of the device."""
        device = self.kidde_device

        model_type = device.get(KEY_MODEL)
        if model_type in MODEL_NAMES:
            model_string = f"{MODEL_NAMES[model_type]} ({model_type})"
        else:
            model_string = f"{model_type}"
            logger.debug(
                "Unverified Kidde device model: [%s] - please report the "
                "device data to the integration maintainers",
                model_type,
            )

        return DeviceInfo(
            identifiers={(DOMAIN, device["label"])},
            name=device.get("label"),
            hw_version=device.get("hwrev"),
            sw_version=str(device.get("fwrev")),
            model=model_string,
            serial_number=device.get("serial_number"),
            manufacturer=MANUFACTURER,
        )

    async def kidde_command(self, command: KiddeCommand) -> None:
        """Send a Kidde command for this device."""
        client = self.coordinator.client
        device = self.kidde_device
        try:
            await client.device_command(device["location_id"], device["id"], command)
        except KiddeClientError as err:
            raise HomeAssistantError(
                f"Failed to send {command} to {device.get('label')}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()


class KiddeBLEEntity(PassiveBluetoothCoordinatorEntity[KiddeBLECoordinator]):
    """Entity base class for locally (BLE) monitored Kidde alarms."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KiddeBLECoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        address = coordinator.address
        advertisement = coordinator.advertisement
        identity = KiddeIdentity(
            advertised_address=address,
            serial_number=(
                advertisement.serial_number if advertisement else None
            ),
            system_id=advertisement.system_id if advertisement else None,
        )
        try:
            stable_id = identity.stable_local_id
            name = friendly_ble_name(address)
        except ValueError:
            stable_id = address
            name = "Kidde Smoke/CO"
        # Preserve existing entity unique IDs while adding the stable embedded
        # identifier to the device registry for cross-transport correlation.
        self._attr_unique_id = f"{address}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address), (DOMAIN, stable_id)},
            connections={(CONNECTION_BLUETOOTH, address)},
            name=name,
            manufacturer=MANUFACTURER,
            model="Smoke/CO alarm (exact model not encoded in BLE)",
            serial_number=(
                advertisement.serial_number if advertisement else None
            ),
        )
