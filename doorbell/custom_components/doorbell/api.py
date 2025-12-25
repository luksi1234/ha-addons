
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

class DoorbellClient:
    def __init__(self, hass, base_url: str, token: Optional[str] = None) -> None:
        self._hass = hass
        self._base = base_url.rstrip("/")
        self._session = async_get_clientsession(hass)  # shared web session
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def _get_json(self, path: str) -> Dict[str, Any]:
        async with self._session.get(f"{self._base}{path}", headers=self._headers) as r:
            _LOGGER.info("_get_json %s ... %s",self._base,path)
            r.raise_for_status()
            return await r.json()

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with self._session.post(f"{self._base}{path}", json=payload, headers=self._headers) as r:
            _LOGGER.info("_post_json %s ... %s",self._base,path)
            r.raise_for_status()
            return await r.json()

    # GET actions
    async def stop(self) -> Dict[str, Any]:
        _LOGGER.info("stop executed ...")
        return await self._get_json("/stop")

    async def status(self) -> Dict[str, Any]:
        _LOGGER.info("status executed ...")
        return await self._get_json("/status")

    async def info(self) -> Dict[str, Any]:
        _LOGGER.info("info executed ...")
        return await self._get_json("/info")

    # POST actions
    async def tts(self, message: str, volume: int) -> Dict[str, Any]:
        _LOGGER.info("tts executed ...")
        return await self._post_json("/tts", {"message": message, "volume": volume})

    async def play(self, filename: str, volume: int) -> Dict[str, Any]:
        _LOGGER.info("play executed ...")
        return await self._post_json("/play", {"filename": filename, "volume": volume})

    async def loop(self, filename: str, volume: int) -> Dict[str, Any]:
        _LOGGER.info("loop executed ...")
        return await self._post_json("/loop", {"filename": filename, "volume": volume})

    async def beep(self, number: int, volume: int) -> Dict[str, Any]:
        _LOGGER.info("beep executed ...")
        return await self._post_json("/beep", {"number": number, "volume": volume})