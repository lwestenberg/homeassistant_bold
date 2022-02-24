"""DataUpdateCoordinator for the Bold integration."""
import asyncio
from datetime import datetime
import logging

from aiohttp import ClientConnectionError, ClientConnectorError, ClientError
from bold_smart_lock.bold_smart_lock import BoldSmartLock
from bold_smart_lock.exceptions import TokenMissing

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_EXPIRATION_TIME, DOMAIN, RESPONSE_EXPIRATION_TIME, SCAN_INTERVAL
from .helpers import convert_expiration_time_to_isoformat

_LOGGER = logging.getLogger(__name__)


class BoldCoordinator(DataUpdateCoordinator[any]):
    """The Bold Coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Bold coordinator."""
        self.hass = hass
        self.config_entry = config_entry
        self.bold = BoldSmartLock(async_get_clientsession(hass))
        self.update_token(
            self.config_entry.data[CONF_EXPIRATION_TIME],
            self.config_entry.data[CONF_TOKEN],
        )
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    def update_token(self, expiration_time: str, token: str):
        """Update token and schedule for next update."""
        self.bold.set_token(token)
        self._expiration_trigger = async_track_point_in_utc_time(
            self.hass, self.async_refresh_token, datetime.fromisoformat(expiration_time)
        )
        _LOGGER.debug("Token updated, scheduled next update")

    async def _async_update_data(self) -> any:
        """Fetch device persmissions."""
        try:
            return await self.bold.get_device_permissions()
        except (ClientConnectorError, asyncio.TimeoutError, ClientError):
            _LOGGER.error("Cannot connect")

    async def async_refresh_token(self):
        """Refresh the token and expiration time."""
        try:
            re_login_response = await self.bold.re_login()
            new_data = {
                **self.config_entry.data,
                [CONF_TOKEN]: re_login_response["token"],
                [CONF_EXPIRATION_TIME]: convert_expiration_time_to_isoformat(
                    re_login_response[RESPONSE_EXPIRATION_TIME]
                ),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            self.update_token(new_data[CONF_EXPIRATION_TIME], new_data[CONF_TOKEN])
        except TokenMissing:
            _LOGGER.error("Current token is missing")
        except (
            ClientConnectionError,
            ClientConnectorError,
            asyncio.TimeoutError,
            ClientError,
        ):
            _LOGGER.error("Cannot connect")

    async def remote_activation(self, device_id: int):
        """Remote activate the lock."""
        try:
            return await self.bold.remote_activation(device_id)
        except (
            ClientConnectionError,
            ClientConnectorError,
            asyncio.TimeoutError,
            ClientError,
        ):
            _LOGGER.error("Cannot connect")
