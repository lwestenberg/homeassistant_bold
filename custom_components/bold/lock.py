"""Lock entity for Bold Smart Lock."""
import datetime
import logging
from typing import Any

from bold_smart_lock.enums import DeviceType
from bold_smart_lock.exceptions import (
    DeviceFirmwareOutdatedError,
    GatewayNotFoundError,
    TooManyRequestsError,
)

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_MODEL, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACTUAL_FIRMWARE_VERSION,
    CONF_BATTERY_LAST_MEASUREMENT,
    CONF_BATTERY_LEVEL,
    CONF_GATEWAY,
    CONF_GATEWAY_ID,
    CONF_PERMISSION_REMOTE_ACTIVATE,
    CONF_REQUIRED_FIRMWARE_VERSION,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import BoldCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create Bold Smart Lock entities"""
    coordinator: BoldCoordinator = hass.data.get(DOMAIN).get(entry.entry_id)
    ent_reg = er.async_get(hass)
    for registry_entry in ent_reg.entities.get_entries_for_config_entry_id(entry.entry_id):
        if isinstance(registry_entry.unique_id, int):
            ent_reg.async_update_entity(registry_entry.entity_id, new_unique_id=str(registry_entry.unique_id))

    gateways = list(
        filter(
            lambda d: d.get(CONF_TYPE).get(CONF_ID) == DeviceType.GATEWAY.value
            and d.get(CONF_PERMISSION_REMOTE_ACTIVATE),
            coordinator.data,
        )
    )
    print("gateways", gateways)
    async_add_entities(
        BoldGatewayEntity(
            coordinator=coordinator,
            data=gateway,
        )
        for gateway in gateways
    )

    locks = list(
        filter(
            lambda d: d.get(CONF_TYPE).get(CONF_ID) == DeviceType.LOCK.value
            and d.get(CONF_PERMISSION_REMOTE_ACTIVATE),
            coordinator.data,
        )
    )
    print("locks", locks)
    async_add_entities(
        BoldLockEntity(coordinator=coordinator, data=lock) for lock in locks
    )


class BoldLockEntity(CoordinatorEntity, LockEntity):
    """Bold Smart Lock entity"""

    entity_registry_enabled_default = True

    def __init__(self, coordinator: BoldCoordinator, data):
        """Init Bold Smart Lock entity"""
        super().__init__(coordinator)
        self._attr_name = data.get(CONF_NAME)
        self._attr_unique_id = str(data.get(CONF_ID))
        self._coordinator: BoldCoordinator = coordinator
        self._data = data
        self._gateway_id = data.get(CONF_GATEWAY, {}).get(CONF_GATEWAY_ID)
        self._unlock_end_time = dt_util.utcnow()
        self._attr_extra_state_attributes = {
            "battery_last_measurement": data.get(CONF_BATTERY_LAST_MEASUREMENT),
            "battery_level": data.get(CONF_BATTERY_LEVEL, 0),
            "device_id": self._attr_unique_id,
            "gateway_id": self._gateway_id,
            "update_available": data.get(CONF_ACTUAL_FIRMWARE_VERSION)
            < data.get(CONF_REQUIRED_FIRMWARE_VERSION),
        }

    @property
    def device_info(self):
        """Return the device information for this entity."""
        return DeviceInfo(
            {
                "identifiers": {(DOMAIN, self._attr_unique_id)},
                "name": self._attr_name,
                "manufacturer": MANUFACTURER,
                "model": self._data.get(CONF_MODEL).get(CONF_MODEL),
                "sw_version": self._data.get(CONF_ACTUAL_FIRMWARE_VERSION),
                "via_device": (DOMAIN, self._gateway_id),
            }
        )

    @property
    def is_locked(self) -> bool:
        """Return the status of the lock."""
        return dt_util.utcnow() >= self._unlock_end_time

    @property
    def available(self) -> bool:
        """Return the reachability of the lock."""
        return self._data.get(CONF_GATEWAY, {}).get(CONF_GATEWAY_ID) is not None

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock Bold Smart Lock."""
        try:
            print("locking", self._attr_unique_id)
            activation_response = await self._coordinator.bold.remote_activation(
                self._attr_unique_id
            )
            if activation_response:
                self._unlock_end_time = dt_util.utcnow() + datetime.timedelta(
                    seconds=activation_response.get("activationTime")
                )
                self.update_state()
                _LOGGER.debug(
                    "Lock deactivated, scheduled activation of lock after %s seconds",
                    activation_response.get("activationTime"),
                )
                async_track_point_in_utc_time(
                    self.hass, self.update_state, self._unlock_end_time
                )
        except TooManyRequestsError as exception:
            raise HomeAssistantError(
                "The user has sent too many requests in a given amount of time."
            ) from exception
        except GatewayNotFoundError as exception:
            raise HomeAssistantError(
                f"No available gateway for device '{self._attr_name}' found."
            ) from exception
        except Exception as exception:
            raise HomeAssistantError(
                f"Error while unlocking: {self._attr_name}"
            ) from exception

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock Bold Smart Lock."""
        try:
            if await self._coordinator.bold.remote_deactivation(self._attr_unique_id):
                self._unlock_end_time = dt_util.utcnow()
                self.update_state()
                _LOGGER.debug("Lock activated")
        except TooManyRequestsError as exception:
            raise HomeAssistantError(
                "The user has sent too many requests in a given amount of time."
            ) from exception
        except DeviceFirmwareOutdatedError as exception:
            raise HomeAssistantError(
                f"Update the firmware of your Bold device '{self._attr_name}' to enable deactivating."
            ) from exception
        except GatewayNotFoundError as exception:
            raise HomeAssistantError(
                f"No available gateway for device '{self._attr_name}' found."
            ) from exception
        except Exception as exception:
            raise HomeAssistantError(
                f"Error while locking: {self._attr_name}"
            ) from exception

    @callback
    def update_state(self, _: datetime = dt_util.utcnow()):
        """Request new state update."""
        self.async_write_ha_state()


class BoldGatewayEntity(CoordinatorEntity, LockEntity):
    """Bold Connect entity"""

    entity_registry_enabled_default = False

    def __init__(self, coordinator: BoldCoordinator, data):
        """Init Connect entity"""
        super().__init__(coordinator)
        self._attr_name = data.get(CONF_NAME)
        self._attr_unique_id = str(data.get(CONF_ID))
        self._coordinator: BoldCoordinator = coordinator
        self._data = data
        self._unlock_end_time = dt_util.utcnow()
        self._attr_extra_state_attributes = {
            "device_id": self._attr_unique_id,
            "update_available": data.get(CONF_ACTUAL_FIRMWARE_VERSION)
            < data.get(CONF_REQUIRED_FIRMWARE_VERSION),
        }

    @property
    def device_info(self):
        """Return the device information for this entity."""
        return DeviceInfo(
            {
                "identifiers": {(DOMAIN, self._attr_unique_id)},
                "name": self._attr_name,
                "manufacturer": MANUFACTURER,
                "model": self._data.get(CONF_MODEL).get(CONF_MODEL),
                "sw_version": self._data.get(CONF_ACTUAL_FIRMWARE_VERSION),
            }
        )

    @property
    def is_locked(self) -> bool:
        """Return the status of the gateway."""
        return dt_util.utcnow() >= self._unlock_end_time

    @property
    def available(self) -> bool:
        """Return the reachability of the gateway."""
        return self._data.get(CONF_GATEWAY, {}).get(CONF_GATEWAY_ID) is not None

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock Bold Connect."""
        try:
            print("locking", self._attr_unique_id)
            activation_response = await self._coordinator.bold.remote_activation(
                self._attr_unique_id
            )
            if activation_response:
                self._unlock_end_time = dt_util.utcnow() + datetime.timedelta(
                    seconds=activation_response.get("activationTime")
                )
                self.update_state()
                _LOGGER.debug(
                    "Lock deactivated, scheduled activation of lock after %s seconds",
                    activation_response.get("activationTime"),
                )
                async_track_point_in_utc_time(
                    self.hass, self.update_state, self._unlock_end_time
                )
        except TooManyRequestsError as exception:
            raise HomeAssistantError(
                "The user has sent too many requests in a given amount of time."
            ) from exception
        except Exception as exception:
            raise HomeAssistantError(
                f"Error while unlocking: {self._attr_name}"
            ) from exception

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock Bold Connect."""
        try:
            if await self._coordinator.bold.remote_deactivation(self._attr_unique_id):
                self._unlock_end_time = dt_util.utcnow()
                self.update_state()
                _LOGGER.debug("Lock activated")
        except TooManyRequestsError as exception:
            raise HomeAssistantError(
                "The user has sent too many requests in a given amount of time."
            ) from exception
        except DeviceFirmwareOutdatedError as exception:
            raise HomeAssistantError(
                f"Update the firmware of your Bold device '{self._attr_name}' to enable deactivating."
            ) from exception
        except Exception as exception:
            raise HomeAssistantError(
                f"Error while locking: {self._attr_name}"
            ) from exception

    @callback
    def update_state(self, _: datetime = dt_util.utcnow()):
        """Request new state update."""
        self.async_write_ha_state()
