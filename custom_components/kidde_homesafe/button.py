"""Button platform for Kidde Homesafe integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import KiddeCommand
from .coordinator import KiddeConfigEntry
from .entity import KiddeEntity

PARALLEL_UPDATES = 1

KEY_MODEL = "model"

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KiddeButtonEntityDescription(ButtonEntityDescription):
    """Describes Kidde Button entity."""

    kidde_command: KiddeCommand


_BUTTON_DESCRIPTIONS = (
    KiddeButtonEntityDescription(
        key="test",
        icon="mdi:smoke-detector-variant-alert",
        name="Test",
        kidde_command=KiddeCommand.TEST,
    ),
    KiddeButtonEntityDescription(
        key="hush",
        icon="mdi:smoke-detector-variant-off",
        name="Hush",
        kidde_command=KiddeCommand.HUSH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KiddeConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the button platform."""
    coordinator = entry.runtime_data
    sensors = []

    for device_id in coordinator.data.devices:
        match coordinator.data.devices[device_id].get(KEY_MODEL, None):
            case "wifiiaqdetector" | "wifidetector" | "EssWFAC":
                for entity_description in _BUTTON_DESCRIPTIONS:
                    sensors.append(
                        KiddeButtonEntity(coordinator, device_id, entity_description)
                    )

            case "waterleakdetector" | "cowifidetector":
                pass

            case _:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.warning(
                        "Unverified Kidde Device Model: [%s]",
                        coordinator.data.devices[device_id].get(KEY_MODEL, None),
                    )

    async_add_devices(sensors)


class KiddeButtonEntity(KiddeEntity, ButtonEntity):
    """Button for Kidde HomeSafe."""

    entity_description: KiddeButtonEntityDescription

    async def async_press(self) -> None:
        """Press the entity."""
        await self.kidde_command(self.entity_description.kidde_command)
