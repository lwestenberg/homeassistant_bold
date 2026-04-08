"""Constants for the Bold integration."""
from homeassistant.const import Platform

DOMAIN = "bold"
MANUFACTURER = "Bold"

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
CONF_PERMISSION_REMOTE_ACTIVATE = "permissionRemoteActivate"
CONF_REQUIRED_FIRMWARE_VERSION = "requiredFirmwareVersion"

# Webhook constants
CONF_WEBHOOK_ID = "webhook_id"
CONF_BOLD_WEBHOOK_ID = "bold_webhook_id"
CONF_ORGANIZATION_ID = "organization_id"
EVENT_BOLD_LOCK_EVENT = "bold_lock_event"
WEBHOOK_TOPICS = [
    "DeviceActivationEvents",
    "DeviceDeactivationEvents",
    "DeviceStatusEvents",
    "DeviceTamperEvents",
]
DATA_LOCK_ENTITIES = "lock_entities"
