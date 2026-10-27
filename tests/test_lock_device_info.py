"""Test device metadata without Home Assistant, network access, or devices."""

import datetime
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


INTEGRATION = Path(__file__).resolve().parents[1] / "custom_components" / "bold"
MISSING = object()


class CoordinatorEntityStub:
    """Accept a coordinator without starting Home Assistant."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


class LockEntityStub:
    """Supply the independent lock base class."""


def load_lock_module():
    """Import the actual sources, replacing only external dependencies."""
    attributes = {
        "bold_smart_lock": {},
        "bold_smart_lock.enums": {"DeviceType": object},
        "bold_smart_lock.exceptions": {
            name: type(name, (Exception,), {})
            for name in (
                "DeviceFirmwareOutdatedError", "GatewayNotFoundError", "TooManyRequestsError"
            )
        },
        "homeassistant": {},
        "homeassistant.components": {},
        "homeassistant.components.lock": {"LockEntity": LockEntityStub},
        "homeassistant.config_entries": {"ConfigEntry": object},
        "homeassistant.const": {
            "CONF_ID": "id", "CONF_MODEL": "model", "CONF_NAME": "name",
            "CONF_TYPE": "type", "Platform": SimpleNamespace(LOCK="lock"),
        },
        "homeassistant.core": {"HomeAssistant": object, "callback": lambda fn: fn},
        "homeassistant.exceptions": {"HomeAssistantError": Exception},
        "homeassistant.helpers": {},
        "homeassistant.helpers.entity": {"DeviceInfo": dict},
        "homeassistant.helpers.entity_platform": {"AddEntitiesCallback": object},
        "homeassistant.helpers.entity_registry": {},
        "homeassistant.helpers.event": {"async_track_point_in_utc_time": object},
        "homeassistant.helpers.update_coordinator": {
            "CoordinatorEntity": CoordinatorEntityStub,
        },
        "homeassistant.util": {},
        "homeassistant.util.dt": {
            "utcnow": lambda: datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        },
        "_bold_device_info_tests": {},
        "_bold_device_info_tests.coordinator": {"BoldCoordinator": object},
    }
    modules = {}
    for name, values in attributes.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        modules[name] = module
    for name, module in modules.items():
        parent, _, child = name.rpartition(".")
        if parent in modules:
            setattr(modules[parent], child, module)

    with patch.dict(sys.modules, modules):
        for filename in ("const", "lock"):
            name = f"_bold_device_info_tests.{filename}"
            spec = importlib.util.spec_from_file_location(name, INTEGRATION / f"{filename}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
    return module


class DeviceInfoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = load_lock_module()
        cls.entity_types = (cls.lock.BoldLockEntity, cls.lock.BoldGatewayEntity)

    def device_data(self, actual=2, required=10):
        return {
            self.lock.CONF_ID: 123,
            self.lock.CONF_NAME: "Test device",
            self.lock.CONF_MODEL: {self.lock.CONF_MODEL: "Test model"},
            self.lock.CONF_GATEWAY: {self.lock.CONF_GATEWAY_ID: 456},
            self.lock.CONF_ACTUAL_FIRMWARE_VERSION: actual,
            self.lock.CONF_REQUIRED_FIRMWARE_VERSION: required,
        }

    def test_firmware_metadata(self):
        cases = ((42, "42"), ("1.2.3", "1.2.3"), (None, None), (MISSING, None), (0, "0"))
        for entity_type in self.entity_types:
            for firmware, expected in cases:
                with self.subTest(entity=entity_type.__name__, firmware=firmware):
                    data = self.device_data()
                    entity = entity_type(coordinator=object(), data=data)
                    # Constructors require comparable versions. Exercise the metadata
                    # property independently for null, absent, and string values.
                    if firmware is MISSING:
                        del data[self.lock.CONF_ACTUAL_FIRMWARE_VERSION]
                    else:
                        data[self.lock.CONF_ACTUAL_FIRMWARE_VERSION] = firmware
                    original = data.copy()
                    expected_info = {
                        "identifiers": {(self.lock.DOMAIN, "123")},
                        "name": "Test device",
                        "manufacturer": self.lock.MANUFACTURER,
                        "model": "Test model",
                        "sw_version": expected,
                    }
                    if entity_type is self.lock.BoldLockEntity:
                        expected_info["via_device"] = (self.lock.DOMAIN, 456)

                    self.assertEqual(entity.device_info, expected_info)
                    self.assertEqual(data, original)
                    if firmware is not MISSING:
                        self.assertIs(data[self.lock.CONF_ACTUAL_FIRMWARE_VERSION], firmware)

    def test_update_detection_remains_numeric(self):
        for entity_type in self.entity_types:
            for actual, required, expected in ((2, 10, True), (10, 10, False), (11, 10, False)):
                with self.subTest(entity=entity_type.__name__, actual=actual, required=required):
                    data = self.device_data(actual, required)
                    entity = entity_type(coordinator=object(), data=data)
                    self.assertIs(entity._attr_extra_state_attributes["update_available"], expected)
                    self.assertEqual(entity.device_info["sw_version"], str(actual))
                    self.assertIs(type(data[self.lock.CONF_ACTUAL_FIRMWARE_VERSION]), int)
                    self.assertIs(type(data[self.lock.CONF_REQUIRED_FIRMWARE_VERSION]), int)
                    self.assertEqual(data[self.lock.CONF_ACTUAL_FIRMWARE_VERSION], actual)
                    self.assertEqual(data[self.lock.CONF_REQUIRED_FIRMWARE_VERSION], required)


if __name__ == "__main__":
    unittest.main()
