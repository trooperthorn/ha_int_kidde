"""Constants for the Kidde HomeSafe integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "kidde_homesafe"
MANUFACTURER: Final = "Kidde"

# Config entry data keys
CONF_CONNECTION_TYPE: Final = "connection_type"
CONF_COOKIES: Final = "cookies"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Connection types
CONNECTION_TYPE_CLOUD: Final = "cloud"
CONNECTION_TYPE_BLUETOOTH: Final = "bluetooth"

# Cloud polling
DEFAULT_UPDATE_INTERVAL: Final = 30
MIN_UPDATE_INTERVAL: Final = 5
MAX_UPDATE_INTERVAL: Final = 3600
CLOUD_TIMEOUT: Final = 30

# Event entity
EVENT_TYPE_STATUS_CHANGED: Final = "status_changed"
