"""Regression checks against the installed Home Assistant API."""

from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from bold_smart_lock.bold_smart_lock import BoldSmartLock
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.bold.coordinator import BoldCoordinator
from custom_components.bold.lock import BoldGatewayEntity, BoldLockEntity


class CompatibilityTests(IsolatedAsyncioTestCase):
    """Exercise entity metadata and refreshes with real Home Assistant classes."""

    async def asyncSetUp(self):
        config_dir = TemporaryDirectory()
        self.addCleanup(config_dir.cleanup)
        self.hass = HomeAssistant(config_dir.name)
        frame.async_setup(self.hass)
        self.addAsyncCleanup(self.hass.async_stop)
        self.bold = AsyncMock(spec=BoldSmartLock)
        self.coordinator = BoldCoordinator(self.hass, self.bold)

    async def test_device_info(self):
        """Both device types must support the keyword-only DeviceInfo API."""
        data = {
            "id": 42,
            "name": "Front door",
            "model": {"model": "SX-33"},
            "actualFirmwareVersion": "1.0",
            "requiredFirmwareVersion": "1.1",
            "gateway": {"gatewayId": "24"},
        }
        for entity_type in (BoldLockEntity, BoldGatewayEntity):
            with self.subTest(entity_type=entity_type.__name__):
                info = entity_type(self.coordinator, data).device_info
                self.assertEqual(info["identifiers"], {("bold", "42")})
                self.assertEqual(info["name"], "Front door")
                self.assertEqual(info["manufacturer"], "Bold")
                self.assertEqual(info["model"], "SX-33")
                self.assertEqual(info["sw_version"], "1.0")

    async def test_refresh(self):
        """Fetching devices works without the optional async_timeout package."""
        self.bold.get_device_permissions.return_value = [{"id": 42}]
        await self.coordinator.async_refresh()
        self.assertTrue(self.coordinator.last_update_success)
        self.assertEqual(self.coordinator.data, [{"id": 42}])
        self.bold.get_device_permissions.assert_awaited_once_with()

    async def test_refresh_error(self):
        """API errors still use Home Assistant's coordinator error type."""
        self.bold.get_device_permissions.side_effect = TimeoutError
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()
