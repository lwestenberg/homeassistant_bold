"""The Bold integration."""
from __future__ import annotations

import logging
import secrets

from aiohttp.web import Request, Response

from bold_smart_lock.bold_smart_lock import BoldSmartLock

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.network import get_url

from . import api
from .const import (
    CONF_BOLD_WEBHOOK_ID,
    CONF_ORGANIZATION_ID,
    CONF_WEBHOOK_ID,
    DATA_LOCK_ENTITIES,
    DOMAIN,
    EVENT_BOLD_LOCK_EVENT,
    PLATFORMS,
    WEBHOOK_TOPICS,
)
from .coordinator import BoldCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bold from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_manager = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    bold_api = BoldSmartLock(auth_manager)

    coordinator = BoldCoordinator(hass, bold_api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    # Initialize device_id -> entity mapping for webhook handler
    hass.data[DOMAIN].setdefault(DATA_LOCK_ENTITIES, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up webhook for receiving Bold events
    await _async_setup_webhook(hass, entry, bold_api)

    return True


async def _async_setup_webhook(
    hass: HomeAssistant, entry: ConfigEntry, bold_api: BoldSmartLock
) -> None:
    """Register HA webhook and create Bold webhook pointing to it."""
    # Generate a unique webhook ID for this config entry
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = f"bold_{secrets.token_hex(16)}"
        data = dict(entry.data)
        data[CONF_WEBHOOK_ID] = webhook_id
        hass.config_entries.async_update_entry(entry, data=data)

    # Register the webhook handler in HA
    webhook.async_register(
        hass, DOMAIN, "Bold Smart Lock", webhook_id, handle_webhook
    )

    # Try to get the organization ID and create a Bold webhook
    try:
        external_url = get_url(hass, prefer_external=True, allow_cloud=True)
        webhook_url = f"{external_url}{webhook.async_generate_path(webhook_id)}"

        # Get organization ID from v2 devices API
        devices_v2 = await bold_api.get_devices_v2()
        organization_id = None
        device_ids = []

        if isinstance(devices_v2, list):
            for device in devices_v2:
                owner = device.get("owner", {})
                if owner and owner.get("organizationId"):
                    organization_id = owner["organizationId"]
                device_id = device.get("id")
                if device_id:
                    device_ids.append(device_id)
        elif isinstance(devices_v2, dict):
            # Response might be wrapped in a data key
            device_list = devices_v2.get("data", devices_v2.get("devices", []))
            if isinstance(device_list, list):
                for device in device_list:
                    owner = device.get("owner", {})
                    if owner and owner.get("organizationId"):
                        organization_id = owner["organizationId"]
                    device_id = device.get("id")
                    if device_id:
                        device_ids.append(device_id)

        if organization_id and device_ids:
            result = await bold_api.create_webhook(
                organization_id=organization_id,
                webhook_url=webhook_url,
                device_ids=device_ids,
                topics=WEBHOOK_TOPICS,
            )
            bold_webhook_id = None
            if isinstance(result, dict):
                bold_webhook_id = result.get("id") or result.get("webhookId")
            _LOGGER.debug(
                "Created Bold webhook %s pointing to %s",
                bold_webhook_id,
                webhook_url,
            )
            # Store the Bold webhook ID and org ID for cleanup
            data = dict(entry.data)
            if bold_webhook_id:
                data[CONF_BOLD_WEBHOOK_ID] = bold_webhook_id
            data[CONF_ORGANIZATION_ID] = organization_id
            hass.config_entries.async_update_entry(entry, data=data)
        else:
            _LOGGER.warning(
                "Could not determine organization ID or device IDs from Bold API; "
                "webhook events will not be available"
            )
    except Exception:
        _LOGGER.exception(
            "Failed to set up Bold webhook; events will not be available"
        )


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response:
    """Handle incoming Bold webhook events."""
    try:
        payload = await request.json()
    except Exception:
        _LOGGER.warning("Received Bold webhook with invalid JSON payload")
        return Response(status=400)

    _LOGGER.debug("Bold webhook received payload: %s", payload)

    # Attempt to extract useful fields from the payload.
    # The exact schema is undocumented so we handle this generically.
    device_id = str(
        payload.get("deviceId")
        or payload.get("device_id")
        or payload.get("id")
        or ""
    )
    event_type = (
        payload.get("topic")
        or payload.get("eventType")
        or payload.get("event_type")
        or payload.get("type")
        or "unknown"
    )
    user_name = payload.get("userName") or payload.get("user_name") or ""
    if not user_name and isinstance(payload.get("user"), dict):
        user_name = payload["user"].get("name", "")
    timestamp = payload.get("timestamp") or payload.get("createdAt") or ""

    # Fire a Home Assistant event for automations
    event_data = {
        "device_id": device_id,
        "event_type": event_type,
        "user_name": user_name,
        "timestamp": timestamp,
        "raw_payload": payload,
    }
    hass.bus.async_fire(EVENT_BOLD_LOCK_EVENT, event_data)

    # Try to update the lock entity if we can identify the device
    lock_entities = hass.data.get(DOMAIN, {}).get(DATA_LOCK_ENTITIES, {})
    entity = lock_entities.get(device_id)
    if entity:
        entity.handle_webhook_event(event_type, user_name, payload)
    else:
        _LOGGER.debug(
            "Received webhook for device %s but no matching entity found",
            device_id,
        )

    return Response(status=200)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unregister the HA webhook
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if webhook_id:
        webhook.async_unregister(hass, webhook_id)

    # Delete the Bold webhook
    bold_webhook_id = entry.data.get(CONF_BOLD_WEBHOOK_ID)
    if bold_webhook_id:
        try:
            coordinator: BoldCoordinator = hass.data[DOMAIN][entry.entry_id]
            await coordinator.bold.delete_webhook(bold_webhook_id)
            _LOGGER.debug("Deleted Bold webhook %s", bold_webhook_id)
        except Exception:
            _LOGGER.exception("Failed to delete Bold webhook %s", bold_webhook_id)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.get(DOMAIN).pop(entry.entry_id)

    return unload_ok
