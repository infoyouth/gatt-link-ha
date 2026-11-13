"""Constants for the GATT Link integration."""

from typing import Final

DOMAIN: Final = "gatt_link"

CONF_ADDRESS: Final = "address"
CONF_CONNECTION_MODE: Final = "connection_mode"
CONF_SCAN_INTERVAL: Final = "scan_interval"

CONNECTION_MODE_PUSH: Final = "push"
CONNECTION_MODE_POLL_AND_DISCONNECT: Final = "poll_and_disconnect"

DEFAULT_CONNECTION_MODE: Final = CONNECTION_MODE_PUSH
DEFAULT_SCAN_INTERVAL: Final = 300
