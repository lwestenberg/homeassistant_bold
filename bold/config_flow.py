"""Config flow for Bold integration."""
from __future__ import annotations

import asyncio
import logging

from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientConnectorError,
    ClientError,
)
from aiohttp.web import HTTPUnauthorized
from async_timeout import timeout
from bold_smart_lock.bold_smart_lock import BoldSmartLock
from bold_smart_lock.exceptions import (
    AuthenticateFailed,
    EmailOrPhoneNotSpecified,
    InvalidEmail,
    VerificationNotFound,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_EXPIRATION_TIME,
    CONF_VERIFICATION_CODE,
    DOMAIN,
    RESPONSE_EXPIRATION_TIME,
    RESPONSE_TOKEN,
)
from .helpers import convert_expiration_time_to_isoformat

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bold."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}
        self.bold: BoldSmartLock = None
        self.request_validation_id_response = None

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Handle user step."""
        errors = {}

        if user_input is not None:
            self.data["email"] = user_input[CONF_EMAIL]

            try:
                async with timeout(10):
                    self.bold = BoldSmartLock(async_get_clientsession(self.hass))
                    self.request_validation_id_response = (
                        await self.bold.request_validation_id(user_input[CONF_EMAIL])
                    )
                    _LOGGER.debug("E-mail verification code requested")
                    return await self.async_step_validate()
            except (InvalidEmail, EmailOrPhoneNotSpecified):
                errors[CONF_EMAIL] = "invalid_email"
                _LOGGER.error("Invalid e-mail")
            except (
                ClientConnectorError,
                asyncio.TimeoutError,
                ClientError,
                ClientConnectionError,
            ):
                errors["base"] = "cannot_connect"
                _LOGGER.error("Cannot connect")

        schema = vol.Schema({vol.Required(CONF_EMAIL): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_validate(self, user_input: dict[str, str | int] | None = None):
        """Handle validation step."""
        errors = {}

        if self.request_validation_id_response is not None and user_input is not None:
            try:
                async with timeout(10):
                    authenticate_response = await self.bold.authenticate(
                        self.request_validation_id_response[CONF_EMAIL],
                        user_input[CONF_PASSWORD],
                        user_input[CONF_VERIFICATION_CODE],
                        self.request_validation_id_response[CONF_ID],
                    )

                    self.data[CONF_TOKEN] = authenticate_response[RESPONSE_TOKEN]
                    self.data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                    self.data[
                        CONF_EXPIRATION_TIME
                    ] = convert_expiration_time_to_isoformat(
                        authenticate_response[RESPONSE_EXPIRATION_TIME]
                    )

                    _LOGGER.debug(
                        "Token set with expiration time %s",
                        authenticate_response[RESPONSE_EXPIRATION_TIME],
                    )
                    return self.async_create_entry(
                        title=self.data[CONF_EMAIL], data=self.data
                    )
            except (HTTPUnauthorized, VerificationNotFound, AuthenticateFailed):
                errors["base"] = "invalid_auth"
                _LOGGER.error("Invalid auth")
            except (
                ClientConnectorError,
                asyncio.TimeoutError,
                ClientError,
                ClientConnectionError,
            ):
                errors["base"] = "cannot_connect"
                _LOGGER.error("Cannot connect")

        schema = vol.Schema(
            {
                vol.Required(CONF_VERIFICATION_CODE): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="validate", data_schema=schema, errors=errors, last_step=True
        )
