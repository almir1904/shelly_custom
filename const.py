"""Constants for the Shelly Custom integration."""
from datetime import timedelta

DOMAIN = "shelly_custom"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_NAME = "Shelly Switch"

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"
