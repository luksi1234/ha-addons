"""Config flow to configure the AdGuard Home integration."""

from __future__ import annotations

from typing import Any
import logging

_LOGGER = logging.getLogger(__name__)

#from adguardhome import AdGuardHome, AdGuardHomeConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import (
    CONF_PORT,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DOMAIN



@callback
def get_addon_manager(hass: HomeAssistant, slug: str) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, _LOGGER, "OpenThread Border Router", slug)

async def _title(hass: HomeAssistant, discovery_info: HassioServiceInfo) -> str:
    """Return config entry title."""
    device: str | None = None
    addon_manager = get_addon_manager(hass, discovery_info.slug)

    with suppress(AddonError):
        addon_info = await addon_manager.async_get_addon_info()
        device = addon_info.options.get("device")

    if _is_yellow(hass) and device == "/dev/ttyAMA1":
        return f"Home Assistant Yellow ({discovery_info.name})"

    if device and ("Connect_ZBT-1" in device or "SkyConnect" in device):
        return f"Home Assistant Connect ZBT-1 ({discovery_info.name})"

    if device and "Nabu_Casa_ZBT-2" in device:
        return f"Home Assistant Connect ZBT-2 ({discovery_info.name})"

    return discovery_info.name

class DoorbellFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a AdGuard Home config flow."""

    VERSION = 1

    _hassio_discovery: dict[str, Any] | None = None

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {

                    vol.Required(CONF_PORT, default=5000): vol.Coerce(int),

                }
            ),
            errors=errors or {},
        )

    async def _show_hassio_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the Hass.io confirmation form to the user."""
        assert self._hassio_discovery
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._async_abort_entries_match(
            {CONF_PORT: user_input[CONF_PORT]}
        )

        errors = {}

        session = async_get_clientsession(self.hass, verify_ssl=False)

        port=user_input[CONF_PORT]


        try:
            _LOGGER.info("async_step_user: check Doorbell exists/running")
            #await adguard.version()
        except Exception:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title="Doorbell",
            data={

                CONF_PORT: user_input[CONF_PORT],

            },
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a Hass.io AdGuard Home add-on.

        This flow is triggered by the discovery component.


        """
        _LOGGER.info("async_step_hassio: check Doorbell exists/running ")

        await self._async_handle_discovery_without_unique_id()

        self._hassio_discovery = discovery_info.config
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery."""
        if user_input is None:
            return await self._show_hassio_form()

        errors = {}

        session = async_get_clientsession(self.hass, False)

        assert self._hassio_discovery
        '''
        adguard = AdGuardHome(
            self._hassio_discovery[CONF_HOST],
            port=self._hassio_discovery[CONF_PORT],
            tls=False,
            session=session,
        )'''

        try:
            #await adguard.version()
            _LOGGER.info("async_step_hassio_confirm: check Doorbell exists/running ")
        except Exception:
            errors["base"] = "cannot_connect"
            return await self._show_hassio_form(errors)

        #title=await _title(self.hass, discovery_info)
        title2=self._hassio_discovery["addon"]

        #_LOGGER.info("title: %s",title)
        _LOGGER.info("title2: %s",title2)

        return self.async_create_entry(
            title=self._hassio_discovery["addon"],
            data={

                CONF_PORT: self._hassio_discovery[CONF_PORT],

            },
        )
