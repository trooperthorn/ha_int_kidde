"""Event platform for Kidde HomeSafe (Bluetooth entries)."""

from __future__ import annotations

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import EVENT_TYPE_STATUS_CHANGED
from .coordinator import KiddeBLECoordinator, KiddeConfigEntry
from .entity import KiddeBLEEntity

PARALLEL_UPDATES = 0

_EVENT_DESCRIPTION = EventEntityDescription(
    key="status",
    translation_key="ble_status",
    entity_category=EntityCategory.DIAGNOSTIC,
    event_types=[EVENT_TYPE_STATUS_CHANGED],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KiddeConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the event platform for a Bluetooth entry."""
    coordinator = entry.runtime_data
    if not isinstance(coordinator, KiddeBLECoordinator):
        return
    async_add_devices([KiddeBLEEventEntity(coordinator, _EVENT_DESCRIPTION)])


class KiddeBLEEventEntity(KiddeBLEEntity, EventEntity):
    """Fires an event whenever the advertised status payload changes.

    Attach an automation to this entity to be notified the moment the
    alarm starts broadcasting something other than its previous state —
    typically within a couple of seconds of the physical event.
    """

    coordinator: KiddeBLECoordinator

    def __init__(
        self,
        coordinator: KiddeBLECoordinator,
        entity_description: EventEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entity_description)
        advertisement = coordinator.advertisement
        self._last_payload = (
            advertisement.status_payload_hex if advertisement else None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an event when the status payload changes."""
        advertisement = self.coordinator.advertisement
        if advertisement is None:
            return
        payload = advertisement.status_payload_hex
        if self._last_payload is None:
            # No baseline (e.g. first advertisement after a restart with
            # no cached history) - adopt silently instead of firing.
            self._last_payload = payload
            return
        if payload != self._last_payload:
            self._trigger_event(
                EVENT_TYPE_STATUS_CHANGED,
                {
                    "previous_payload": self._last_payload,
                    "payload": payload,
                    "is_idle_payload": advertisement.is_idle_payload,
                },
            )
            self._last_payload = payload
            self.async_write_ha_state()
