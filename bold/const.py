"""Constants for the Bold integration."""
from datetime import timedelta
from typing import Final

DOMAIN = "bold"
SCAN_INTERVAL = timedelta(seconds=1800)

CONF_EXPIRATION_TIME: Final = "expiration_time"
CONF_VERIFICATION_CODE: Final = "verification_code"

RESPONSE_TOKEN: Final = "token"
RESPONSE_EXPIRATION_TIME: Final = "expirationTime"
