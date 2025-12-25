
from __future__ import annotations

import os
import aiohttp
import logging
import async_timeout
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.components import persistent_notification
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.hassio import AddonError, AddonManager
from .const import DOMAIN, ADDON_SLUG

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)

from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

#DOMAIN = "doorbell"
#ADDON_SLUG = "local_doorbell"  # our slug from config.yaml

SERVICE_TASK_PLAY   = "play"
SERVICE_TASK_TTS    = "tts"
SERVICE_TASK_LOOP   = "loop"
SERVICE_TASK_BEEP   = "beep"
SERVICE_TASK_STOP   = "stop"
SERVICE_TASK_CHECK  = "check"
SERVICE_TASK_INFO   = "info"
SERVICE_TASK_STATUS = "status"

SCHEMA_TASK_PLAY = vol.Schema({vol.Required("filename"): cv.string,       vol.Optional("volume",default=100): vol.Coerce(int)})
SCHEMA_TASK_TTS  = vol.Schema({vol.Required("message"):  cv.string,       vol.Optional("volume",default=100): vol.Coerce(int)})
SCHEMA_TASK_LOOP = vol.Schema({vol.Required("filename"): cv.string,       vol.Optional("volume",default=100): vol.Coerce(int)})
SCHEMA_TASK_BEEP = vol.Schema({vol.Required("number"):   vol.Coerce(int), vol.Optional("volume",default=100): vol.Coerce(int)})

PLATFORMS = []
type DoorbellConfigEntry = ConfigEntry[DoorbellData]


@dataclass
class DoorbellData:
    """Adguard data type."""
    #port: int
    version: str


SUPERVISOR_BASE = "http://supervisor"


def addon_dns_host(repository: str, slug: str) -> str:
    # {REPO}_{SLUG} with underscores replaced by hyphens for DNS inside the Supervisor network
    return f"{slug}".replace("_", "-")

async def async_get_addon_full_id(session: aiohttp.ClientSession, token: str, slug: str) -> str | None:
    # Query /addons and pick the one with our slug to get the repository prefix
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(f"{SUPERVISOR_BASE}/addons", headers=headers) as resp:
        data = await resp.json()
    _LOGGER.info("addons data: %s", data)
    data_addons = data.get("data", [])
    for addon in data_addons.get("addons", []):
        loc_slug = addon.get("slug")
        _LOGGER.info("addons slug: %s", loc_slug)
        if addon.get("slug") == slug:
            #return f"{addon.get('repository')}_{slug}"
            return addon.get("slug")
    return None

async def async_get_addon_info(session: aiohttp.ClientSession, token: str, full_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    _LOGGER.info("async_get_addon_info")
    with async_timeout.timeout(10):
        async with session.get(f"{SUPERVISOR_BASE}/addons/{full_id}/info", headers=headers) as resp:
            return await resp.json()

async def async_start_addon(session: aiohttp.ClientSession, token: str, full_id: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    _LOGGER.info("async_start_addon")
    async with session.post(f"{SUPERVISOR_BASE}/addons/{full_id}/start", headers=headers) as resp:
        await resp.text()  # ignore body

async def async_setup(hass: HomeAssistant, config):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        # Running outside Supervisor? Log & continue without supervisor checks.
        _LOGGER.warning("%s: SUPERVISOR_TOKEN not found; supervisor checks disabled", DOMAIN)
    _LOGGER.info("SUPERVISOR_TOKEN found")
    session = aiohttp.ClientSession()

    async def ensure_running_and_port() -> tuple[str | None, int | None, dict]:
        if not token:
            return None, None, {}

        full_id = await async_get_addon_full_id(session, token, ADDON_SLUG)
        _LOGGER.info("full_id: %s",full_id)
        if not full_id:
            _LOGGER.error("%s: add-on with slug %s not found", DOMAIN, ADDON_SLUG)
            return None, None, {}

        info_response = await async_get_addon_info(session, token, full_id)
        info = info_response.get('data')
        _LOGGER.info("addon info: %s",info)
        state = info.get("state")
        network = info.get("network") or {}
        repository = info.get("repository")
        hostname = info.get("hostname")
        ip = info.get("ip_address")
        host_network = info.get("host_network")

        # Find our published port (5000/tcp in this example)
        published_port = None
        if isinstance(network, dict):
            port = network.get("5000/tcp")
            if isinstance(port, int):
                published_port = port

        # If stopped, try to start it
        if state != "started":
            _LOGGER.info("%s: add-on is %s; starting…", DOMAIN, state)
            await async_start_addon(session, token, full_id)

        # Compute DNS name for internal calls if needed
        dns = addon_dns_host(repository, ADDON_SLUG)
        return dns or hostname, published_port, {"state": state, "ip": ip, "host_network": host_network}

    async def handle_task_play(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/play" if port else f"http://{dns}/play"
        filename = call.data["filename"]
        volume = call.data.get("volume",100)
        _LOGGER.info("filename: %s",filename)
        _LOGGER.info("volume: %s",volume)
        payload = {"filename": call.data["filename"]}
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_play_done", {"response": data, "meta": meta})

    async def handle_task_tts(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/tts" if port else f"http://{dns}/tts"
        message = call.data["message"]
        volume = call.data.get("volume",100)
        _LOGGER.info("message: %s",message)
        _LOGGER.info("volume: %s",volume)
        payload = {"message": call.data["message"]}
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_tts_done", {"response": data, "meta": meta})

    async def handle_task_beep(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/beep" if port else f"http://{dns}/beep"
        number = call.data["number"]
        volume = call.data.get("volume",100)
        _LOGGER.info("number: %s",number)
        _LOGGER.info("volume: %s",volume)
        payload = {"number": call.data["number"]}
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_beep_done", {"response": data, "meta": meta})

    async def handle_task_stop(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/stop" if port else f"http://{dns}/stop"
        ##payload = {"name": call.data["name"]}
        async with session.get(url, json=None) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_stop_done", {"response": data, "meta": meta})

    async def handle_task_info(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/info" if port else f"http://{dns}/info"
        ##payload = {"name": call.data["name"]}
        async with session.get(url, json=None) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_stop_done", {"response": data, "meta": meta})

    async def handle_task_status(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/status" if port else f"http://{dns}/status"
        ##payload = {"name": call.data["name"]}
        async with session.get(url, json=None) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_stop_done", {"response": data, "meta": meta})


    async def handle_task_loop(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        url = f"http://{dns}:{port}/loop" if port else f"http://{dns}/loop"
        payload = {"filename": call.data["filename"],"volume": call.data["volume"]}
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
        hass.bus.async_fire(f"{DOMAIN}_task_loop_done", {"response": data, "meta": meta})

    async def handle_check(call: ServiceCall):
        dns, port, meta = await ensure_running_and_port()
        #persistent_notification.create(hass, msg, "Sensor alpha_vantage")
        #hass.components.persistent_notification.async_create(
        persistent_notification.async_create(hass,
            title="Add-on status",
            message=f"DNS: {dns}\nPort: {port}\nMeta: {meta}",
            notification_id=f"{DOMAIN}_status",
        )

    hass.services.async_register(DOMAIN, SERVICE_TASK_PLAY,   handle_task_play,   schema=SCHEMA_TASK_PLAY)
    hass.services.async_register(DOMAIN, SERVICE_TASK_TTS,    handle_task_tts,    schema=SCHEMA_TASK_TTS)
    hass.services.async_register(DOMAIN, SERVICE_TASK_BEEP,   handle_task_beep,   schema=SCHEMA_TASK_BEEP)
    hass.services.async_register(DOMAIN, SERVICE_TASK_STOP,   handle_task_stop,   schema=None)
    hass.services.async_register(DOMAIN, SERVICE_TASK_INFO,   handle_task_info,   schema=None)
    hass.services.async_register(DOMAIN, SERVICE_TASK_STATUS, handle_task_status, schema=None)
    hass.services.async_register(DOMAIN, SERVICE_TASK_LOOP,   handle_task_loop,   schema=SCHEMA_TASK_LOOP)
    hass.services.async_register(DOMAIN, SERVICE_TASK_CHECK,  handle_check,       schema=vol.Schema({}))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    """Set up AdGuard Home from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=False)

    port=entry.data[CONF_PORT]

    try:
        _LOGGER.info("check addon is up/and runnung")
    except Exception as exception:
        raise ConfigEntryNotReady from exception

    #entry.runtime_data = AdGuardData(adguard, version)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_check(call: ServiceCall):
        #dns, port, meta = await ensure_running_and_port()

        dns = "test dns"
        port = 9999
        meta = "meta"
        #persistent_notification.create(hass, msg, "Sensor alpha_vantage")
        #hass.components.persistent_notification.async_create(
        persistent_notification.async_create(hass,
            title="Add-on status",
            message=f"DNS: {dns}\nPort: {port}\nMeta: {meta}",
            notification_id=f"{DOMAIN}_status",
        )

    hass.services.async_register(
        DOMAIN, SERVICE_TASK_CHECK,  handle_check,       schema=vol.Schema({})
    )


    return True


async def async_unload_entry(hass: HomeAssistant, entry: DoobellConfigEntry) -> bool:
    """Unload AdGuard Home config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        # This is the last loaded instance of AdGuard, deregister any services
        hass.services.async_remove(DOMAIN, SERVICE_TASK_CHECK)


    return unload_ok
