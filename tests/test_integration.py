"""End-to-end tests with a mocked Anthropic cost report."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.anthropic_credit.api import COST_REPORT_URL
from custom_components.anthropic_credit.const import (
    CONF_ADMIN_KEY,
    CONF_BALANCE,
    CONF_SCAN_INTERVAL,
    CONF_TOP_UP_DATE,
    DOMAIN,
)

KEY = "sk-ant-admin01-test"
NOW = "2026-10-25 12:00:00+00:00"


def bucket(day: str, *cents: str) -> dict:
    return {
        "starting_at": f"{day}T00:00:00Z",
        "ending_at": f"{day}T23:59:59Z",
        "results": [{"amount": c, "currency": "USD"} for c in cents],
    }


def mock_report(mock: AiohttpClientMocker) -> None:
    """Two pages: September and early October, then the rest of October."""
    mock.get(
        f"{COST_REPORT_URL}?starting_at=2026-09-20T00:00:00Z&bucket_width=1d&limit=31&page=p2",
        json={
            "data": [bucket("2026-10-24", "250"), bucket("2026-10-25", "75.5", "24.5")],
            "has_more": False,
            "next_page": None,
        },
    )
    mock.get(
        f"{COST_REPORT_URL}?starting_at=2026-09-20T00:00:00Z&bucket_width=1d&limit=31",
        json={
            "data": [bucket("2026-09-20", "1000"), bucket("2026-10-01", "500")],
            "has_more": True,
            "next_page": "p2",
        },
    )
    mock.get(COST_REPORT_URL, json={"data": [], "has_more": False, "next_page": None})


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADMIN_KEY: KEY, CONF_BALANCE: 50.0, CONF_TOP_UP_DATE: "2026-09-20"},
        unique_id="abc",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    mock_report(aioclient_mock)
    await setup_entry(hass)

    # $10 + $5 + $2.50 + $1 = $18.50 spent since 2026-09-20.
    assert hass.states.get("sensor.anthropic_api_credit_spent_since_top_up").state == "18.5"
    remaining = hass.states.get("sensor.anthropic_api_credit_credit_remaining")
    assert remaining.state == "31.5"
    assert remaining.attributes["unit_of_measurement"] == "USD"
    assert remaining.attributes["top_up_date"] == "2026-09-20"
    assert hass.states.get("sensor.anthropic_api_credit_spent_today").state == "1.0"
    assert hass.states.get("sensor.anthropic_api_credit_spent_yesterday").state == "2.5"
    assert hass.states.get("sensor.anthropic_api_credit_spent_this_month").state == "8.5"
    # The admin key goes in the header, never in the URL.
    for _method, url, _data, headers in aioclient_mock.mock_calls:
        assert KEY not in str(url)
        assert headers["x-api-key"] == KEY


async def test_new_top_up_from_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    mock_report(aioclient_mock)
    entry = await setup_entry(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        COST_REPORT_URL,
        json={"data": [bucket("2026-10-24", "250"), bucket("2026-10-25", "100")], "has_more": False},
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_BALANCE: 100, CONF_TOP_UP_DATE: "2026-10-25", CONF_SCAN_INTERVAL: 60},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert hass.states.get("sensor.anthropic_api_credit_credit_remaining").state == "99.0"
    assert entry.runtime_data.update_interval == timedelta(minutes=60)


async def test_config_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(COST_REPORT_URL, json={"data": [], "has_more": False})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADMIN_KEY: "sk-ant-api03-normal", CONF_BALANCE: 20, CONF_TOP_UP_DATE: "2026-10-01"},
    )
    assert result["errors"] == {CONF_ADMIN_KEY: "not_admin_key"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADMIN_KEY: f" {KEY} ", CONF_BALANCE: 20, CONF_TOP_UP_DATE: "2026-10-01"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADMIN_KEY: KEY, CONF_BALANCE: 20.0, CONF_TOP_UP_DATE: "2026-10-01"}


async def test_bad_key_in_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(COST_REPORT_URL, status=401, json={"error": {"message": "invalid x-api-key"}})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADMIN_KEY: KEY, CONF_BALANCE: 20, CONF_TOP_UP_DATE: "2026-10-01"},
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_revoked_key_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(COST_REPORT_URL, status=401, json={})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADMIN_KEY: KEY, CONF_BALANCE: 50.0, CONF_TOP_UP_DATE: "2026-09-20"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [config_entries.SOURCE_REAUTH]
