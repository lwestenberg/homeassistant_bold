"""Coordinator to fetch the data."""
from datetime import timedelta
import logging

import async_timeout
from bold_smart_lock.bold_smart_lock import BoldSmartLock

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class BoldCoordinator(DataUpdateCoordinator):
    """Bold data coordinator."""

    def __init__(self, hass, bold: BoldSmartLock):
        """Initialize Bold coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Bold",
            update_interval=timedelta(minutes=60),
        )
        self.bold = bold

    async def _async_update_data(self):
        """Fetch data from Bold Smart Lock API."""
        try:
            async with async_timeout.timeout(10):
                return await self.bold.get_device_permissions()
        except Exception as exc:
            raise UpdateFailed("Error communicating with API") from exc
