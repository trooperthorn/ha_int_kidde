"""Config flow for the Kidde HomeSafe integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import KiddeClient, KiddeClientAuthError, KiddeClientCommunicationError
from .ble import parse_service_info
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_COOKIES,
    CONF_UPDATE_INTERVAL,
    CONNECTION_TYPE_BLUETOOTH,
    CONNECTION_TYPE_CLOUD,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_CLOUD_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _format_ble_title(service_info: BluetoothServiceInfoBleak) -> str:
    """Build a friendly title for a discovered BLE alarm."""
    parsed = parse_service_info(service_info)
    name = (service_info.name or "Kidde Alarm").title()
    if parsed and parsed.serial_number:
        return f"{name} ({parsed.serial_number})"
    return f"{name} ({service_info.address})"


class KiddeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kidde HomeSafe."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick between cloud and local Bluetooth."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["cloud", "pick_bluetooth"],
        )

    # ------------------------------------------------------------------
    # Cloud (Kidde HomeSafe account)
    # ------------------------------------------------------------------

    async def _async_try_login(
        self, email: str, password: str, errors: dict[str, str]
    ) -> KiddeClient | None:
        """Attempt a cloud login, populating errors on failure."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            return await KiddeClient.from_login(email, password, session)
        except KiddeClientAuthError:
            errors["base"] = "invalid_auth"
        except KiddeClientCommunicationError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error logging in to Kidde cloud")
            errors["base"] = "unknown"
        return None

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle cloud account setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            client = await self._async_try_login(
                email, user_input[CONF_PASSWORD], errors
            )
            if client is not None:
                await self.async_set_unique_id(f"cloud_{email.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Kidde ({email})",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_CLOUD,
                        CONF_EMAIL: email,
                        CONF_COOKIES: client.cookies,
                    },
                    options={CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL},
                )

        return self.async_show_form(
            step_id="cloud", data_schema=STEP_CLOUD_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication of an expired cloud session."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for fresh credentials and update the entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            unique_id = f"cloud_{email.lower()}"
            if reauth_entry.unique_id and reauth_entry.unique_id != unique_id:
                return self.async_abort(reason="wrong_account")
            client = await self._async_try_login(
                email, user_input[CONF_PASSWORD], errors
            )
            if client is not None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    unique_id=unique_id,
                    data_updates={
                        CONF_EMAIL: email,
                        CONF_COOKIES: client.cookies,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CLOUD_DATA_SCHEMA,
                {CONF_EMAIL: reauth_entry.data.get(CONF_EMAIL, "")},
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow reconfiguring the cloud credentials."""
        reconfigure_entry = self._get_reconfigure_entry()
        if (
            reconfigure_entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD)
            == CONNECTION_TYPE_BLUETOOTH
        ):
            return self.async_abort(reason="nothing_to_reconfigure")

        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            unique_id = f"cloud_{email.lower()}"
            if reconfigure_entry.unique_id and reconfigure_entry.unique_id != unique_id:
                return self.async_abort(reason="wrong_account")
            client = await self._async_try_login(
                email, user_input[CONF_PASSWORD], errors
            )
            if client is not None:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    unique_id=unique_id,
                    data_updates={
                        CONF_EMAIL: email,
                        CONF_COOKIES: client.cookies,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CLOUD_DATA_SCHEMA,
                {CONF_EMAIL: reconfigure_entry.data.get(CONF_EMAIL, "")},
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Local Bluetooth
    # ------------------------------------------------------------------

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a Kidde alarm discovered via Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": _format_ble_title(discovery_info)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered alarm."""
        assert self._discovery_info is not None
        title = _format_ble_title(self._discovery_info)
        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_BLUETOOTH,
                    CONF_ADDRESS: self._discovery_info.address,
                },
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": title},
        )

    async def async_step_pick_bluetooth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from already-discovered Kidde alarms."""
        current_addresses = self._async_current_ids(include_ignore=False)
        discovered: dict[str, BluetoothServiceInfoBleak] = {}
        for service_info in async_discovered_service_info(
            self.hass, connectable=False
        ):
            if service_info.address in current_addresses:
                continue
            parsed = parse_service_info(service_info)
            if parsed is not None:
                discovered[service_info.address] = service_info

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if (service_info := discovered.get(address)) is None:
                return self.async_abort(reason="no_devices_found")
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_format_ble_title(service_info),
                data={
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_BLUETOOTH,
                    CONF_ADDRESS: address,
                },
            )

        if not discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_bluetooth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: _format_ble_title(service_info)
                            for address, service_info in discovered.items()
                        }
                    )
                }
            ),
        )

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return KiddeOptionsFlowHandler()


class KiddeOptionsFlowHandler(OptionsFlow):
    """Handle options for a Kidde HomeSafe entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if (
            self.config_entry.data.get(
                CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD
            )
            == CONNECTION_TYPE_BLUETOOTH
        ):
            return self.async_abort(reason="nothing_to_configure")

        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL])
                }
            )

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self.config_entry.data.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            ),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL, default=current
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    )
                }
            ),
        )
