
from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from . import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StopButton(data["coordinator"], data["client"])])

class StopButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Stop"
    _attr_unique_id = "doorbell_stop"

    def __init__(self, coordinator, client):
        super().__init__(coordinator)
        self._client = client

    async def async_press(self) -> None:
        await self._client.stop()   # GET /stop
