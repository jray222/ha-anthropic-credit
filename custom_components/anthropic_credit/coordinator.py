"""Polls the cost report and works out what is left."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AnthropicAuthError, AnthropicCostClient, AnthropicError
from .const import CONF_BALANCE, CONF_SCAN_INTERVAL, CONF_TOP_UP_DATE, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class CreditData:
    """What the sensors show. Money is in US dollars."""

    balance_at_top_up: float
    top_up_date: date
    spent_since_top_up: float
    remaining: float
    spent_today: float
    spent_yesterday: float
    spent_this_month: float


class AnthropicCreditCoordinator(DataUpdateCoordinator[CreditData]):
    """One poll of the cost report every scan interval."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AnthropicCostClient) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client

    def _setting(self, key: str):
        return self.config_entry.options.get(key, self.config_entry.data.get(key))

    async def _async_update_data(self) -> CreditData:
        balance = float(self._setting(CONF_BALANCE) or 0)
        top_up = date.fromisoformat(str(self._setting(CONF_TOP_UP_DATE)))
        # Anthropic buckets are whole UTC days.
        today = dt_util.utcnow().date()
        month_start = today.replace(day=1)
        try:
            days = await self.client.daily_costs(min(top_up, month_start, today - timedelta(days=1)))
        except AnthropicAuthError as err:
            raise ConfigEntryAuthFailed("The Anthropic admin key was refused") from err
        except AnthropicError as err:
            raise UpdateFailed(f"Anthropic cost report failed: {err}") from err

        def spent(since: date, until: date = today) -> float:
            return round(sum(v for d, v in days.items() if since <= d <= until), 2)

        since_top_up = spent(top_up)
        return CreditData(
            balance_at_top_up=round(balance, 2),
            top_up_date=top_up,
            spent_since_top_up=since_top_up,
            remaining=round(balance - since_top_up, 2),
            spent_today=spent(today),
            spent_yesterday=spent(today - timedelta(days=1), today - timedelta(days=1)),
            spent_this_month=spent(month_start),
        )
