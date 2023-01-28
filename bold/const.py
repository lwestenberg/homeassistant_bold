"""Constants for the Bold integration."""
from homeassistant.const import Platform

DOMAIN = "bold"

PLATFORMS = [
    Platform.LOCK,
]

OAUTH2_AUTHORIZE = "https://auth.boldsmartlock.com/"
OAUTH2_TOKEN = "https://api.boldsmartlock.com/v2/oauth/token"

CONF_ACTUAL_FIRMWARE_VERSION = "actualFirmwareVersion"
CONF_BATTERY_LAST_MEASUREMENT = "batteryLastMeasurement"
CONF_BATTERY_LEVEL = "batteryLevel"
CONF_GATEWAY = "gateway"
CONF_GATEWAY_ID = "gatewayId"
CONF_MAKE = "make"
CONF_PERMISSION_REMOTE_ACTIVATE = "permissionRemoteActivate"
CONF_SETTINGS = "settings"
CONF_SETTINGS_CONTROLLERFUNCTIONALITY = "controllerFunctionality"
