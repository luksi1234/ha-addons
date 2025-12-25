
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN
from .const import DEFAULT_PORT

class DoorbellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            base_url = user_input.get("base_url", "").strip()
            #token = user_input.get("token", "").strip() or None

            if not base_url:
                errors["base_url"] = "required"
            else:
                return self.async_create_entry(
                    title="Doorbell Add-on",
                    data={
                        "base_url": base_url,
                        #"token": token
                    }
                )

        data_schema = vol.Schema({
            vol.Required("base_url", description={"suggested_value": "http://localhost:"+DEFAULT_PORT}): str,
            #vol.Optional("token"): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @callback
    def async_get_options_flow(self, config_entry):
        return DoorbellOptionsFlowHandler(config_entry)

class DoorbellOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Example: allow changing polling interval later
            return self.async_create_entry(title="Options updated", data=user_input)

        schema = vol.Schema({
            # Add options here if needed, e.g. vol.Optional("poll_interval", default=10): int
            #vol.Optional("port", default=self.config_entry.data.get("port", 1234)): int,
        })
        return self.async_show_form(step_id="init", data_schema=schema)