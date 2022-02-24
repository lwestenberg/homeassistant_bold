"""This component provides support for Bold lock activation buttons."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import BoldCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bold buttons based on a config entry."""
    coordinator: BoldCoordinator = hass.data[DOMAIN][entry.entry_id]
    try:
        device_permissions = await coordinator.bold.get_device_permissions()
        devices = []

        for device in device_permissions:
            if device["model"]["id"] == 3 and device["permissionRemoteActivate"]:
                _LOGGER.debug("Setup device %i", device["id"])
                devices.append(
                    BoldSmartLockActivationButton(
                        coordinator=coordinator, device=device
                    )
                )

        async_add_entities(devices)
    except Exception as exception:
        raise HomeAssistantError(
            f"Error while loading device permissions: {entry.entry_id}"
        ) from exception


class BoldSmartLockActivationButton(ButtonEntity):
    """An implementation of a Bold Smart Lock activation button."""

    _attr_should_poll = False

    def __init__(self, coordinator: BoldCoordinator, device) -> None:
        """Initialize a Bold smart lock activation button."""
        ButtonEntity.__init__(self)
        self.device = device
        self.coordinator = coordinator
        self.unlock_end_time = dt_util.utcnow()

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"bold_smart_lock_{self.device['id']}"

    @property
    def name(self):
        """Return the name of this smart lock."""
        return self.device["name"]

    @property
    def icon(self):
        """Icon of the button."""
        if dt_util.utcnow() < self.unlock_end_time:
            return "mdi:door-open"
        return "mdi:door-closed-lock"

    @callback
    def update_state(self, now: datetime = dt_util.utcnow()):
        """Request new state update."""
        _LOGGER.debug("Request state update")
        self.async_write_ha_state()

    async def async_press(self):
        """Unlock smart lock."""
        try:
            activation_response = await self.coordinator.remote_activation(
                self.device["id"]
            )
            if activation_response:
                self.unlock_end_time = dt_util.utcnow() + datetime.timedelta(
                    seconds=activation_response["activationTime"]
                )
                self.update_state()
                _LOGGER.debug(
                    "Lock deactivated, scheduled activation of lock after %s seconds",
                    activation_response["activationTime"],
                )
                async_track_point_in_utc_time(
                    self.hass, self.update_state, self.unlock_end_time
                )
        except Exception as exception:
            raise HomeAssistantError(
                f"Error while activating: {self.device['name']}"
            ) from exception
