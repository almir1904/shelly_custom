"""Constants for the Shelly Custom integration."""
from datetime import timedelta

DOMAIN = "shelly_custom"
DEFAULT_SCAN_INTERVAL = 1  # 1 second polling
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 60

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_NAME = "Shelly Switch"

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"