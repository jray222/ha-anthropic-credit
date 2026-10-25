"""Setup screens for Anthropic Credit."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import AnthropicAuthError, AnthropicCostClient, AnthropicError
from .const import (
    CONF_ADMIN_KEY,
    CONF_BALANCE,
    CONF_SCAN_INTERVAL,
    CONF_TOP_UP_DATE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
BALANCE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0, max=1000000, step=0.01, mode=NumberSelectorMode.BOX, unit_of_measurement="USD"
    )
)
INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=5, max=1440, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
)


def _balance_fields(balance: float | None = None, top_up: str | None = None) -> dict:
    today = dt_util.now().date().isoformat()
    return {
        vol.Required(CONF_BALANCE, default=balance if balance is not None else 0): BALANCE_SELECTOR,
        vol.Required(CONF_TOP_UP_DATE, default=top_up or today): DateSelector(),
    }


class AnthropicCreditConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for an admin key and the balance after the last top-up."""

    VERSION = 1

    def __init__(self) -> None:
        self._problem = ""

    async def _check_key(self, key: str) -> str | None:
        """Return an error code, or None if the key works."""
        client = AnthropicCostClient(async_get_clientsession(self.hass), key)
        try:
            await client.daily_costs(dt_util.utcnow().date())
        except AnthropicAuthError:
            return "invalid_auth"
        except AnthropicError as err:
            # Show Anthropic's own answer so the user can see what went wrong.
            _LOGGER.warning("Anthropic cost report check failed: %s", err)
            self._problem = str(err)[:300]
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_ADMIN_KEY].strip()
            if not key.startswith("sk-ant-admin"):
                errors[CONF_ADMIN_KEY] = "not_admin_key"
            elif error := await self._check_key(key):
                errors["base"] = error
            else:
                await self.async_set_unique_id(hashlib.sha256(key.encode()).hexdigest()[:16])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Anthropic API credit",
                    data={
                        CONF_ADMIN_KEY: key,
                        CONF_BALANCE: float(user_input[CONF_BALANCE]),
                        CONF_TOP_UP_DATE: user_input[CONF_TOP_UP_DATE],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADMIN_KEY): KEY_SELECTOR, **_balance_fields()}),
            errors=errors,
            description_placeholders={"problem": self._problem},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_ADMIN_KEY].strip()
            if not key.startswith("sk-ant-admin"):
                errors[CONF_ADMIN_KEY] = "not_admin_key"
            elif error := await self._check_key(key):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_ADMIN_KEY: key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ADMIN_KEY): KEY_SELECTOR}),
            errors=errors,
            description_placeholders={"problem": self._problem},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AnthropicCreditOptionsFlow()


class AnthropicCreditOptionsFlow(OptionsFlow):
    """Change the balance after a top-up, or how often to check."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_BALANCE] = float(user_input[CONF_BALANCE])
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        current = {**entry.data, **entry.options}
        schema = {
            **_balance_fields(current.get(CONF_BALANCE), current.get(CONF_TOP_UP_DATE)),
            vol.Required(
                CONF_SCAN_INTERVAL, default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): INTERVAL_SELECTOR,
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
