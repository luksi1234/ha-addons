from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType

DOMAIN = "doorbell"

ATTR_NAME = "name"
DEFAULT_NAME = "World"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up is called when Home Assistant is loading our component."""

    @callback
    def handle_test(call: ServiceCall) -> None:
        """Handle the service action call."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.async_set("doorbell.test", name)

    hass.services.async_register(DOMAIN, "test", handle_test)

    # Return boolean to indicate that initialization was successful.
    return True