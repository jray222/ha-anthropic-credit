"""Constants for Anthropic Credit."""

DOMAIN = "anthropic_credit"

CONF_ADMIN_KEY = "admin_key"
CONF_BALANCE = "balance"
CONF_TOP_UP_DATE = "top_up_date"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 30  # minutes. Anthropic asks for at most one poll a minute.
