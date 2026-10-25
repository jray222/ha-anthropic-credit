"""Sensors for Anthropic Credit. All money is in US dollars."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnthropicCreditConfigEntry
from .const import DOMAIN
from .coordinator import AnthropicCreditCoordinator, CreditData


@dataclass(frozen=True, kw_only=True)
class CreditSensorDescription(SensorEntityDescription):
    value: Callable[[CreditData], float]


SENSORS = (
    CreditSensorDescription(key="remaining", icon="mdi:cash", value=lambda d: d.remaining),
    CreditSensorDescription(
        key="spent_since_top_up", icon="mdi:cash-minus", value=lambda d: d.spent_since_top_up
    ),
    CreditSensorDescription(key="spent_today", icon="mdi:calendar-today", value=lambda d: d.spent_today),
    CreditSensorDescription(
        key="spent_yesterday", icon="mdi:calendar-arrow-left", value=lambda d: d.spent_yesterday
    ),
    CreditSensorDescription(
        key="spent_this_month", icon="mdi:calendar-month", value=lambda d: d.spent_this_month
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnthropicCreditConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(CreditSensor(entry.runtime_data, d) for d in SENSORS)


class CreditSensor(CoordinatorEntity[AnthropicCreditCoordinator], SensorEntity):
    """One dollar figure from the cost report."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "USD"
    _attr_suggested_display_precision = 2
    entity_description: CreditSensorDescription

    def __init__(self, coordinator: AnthropicCreditCoordinator, description: CreditSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Anthropic API credit",
            manufacturer="Anthropic",
            model="Admin API cost report",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://platform.claude.com/settings/billing",
        )

    @property
    def native_value(self) -> float:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key not in ("remaining", "spent_since_top_up"):
            return None
        data = self.coordinator.data
        return {
            "balance_at_top_up": data.balance_at_top_up,
            "top_up_date": data.top_up_date.isoformat(),
            "note": "Estimate: balance you entered minus spend reported by Anthropic since that day (UTC).",
        }
