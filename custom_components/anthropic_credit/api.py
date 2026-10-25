"""Calls to the Anthropic Admin API (cost report)."""

from __future__ import annotations

from datetime import date

import aiohttp

COST_REPORT_URL = "https://api.anthropic.com/v1/organizations/cost_report"
API_VERSION = "2023-06-01"
MAX_PAGES = 40  # 31 days a page, so a bit over 3 years


class AnthropicError(Exception):
    """The Admin API said no, or could not be reached."""


class AnthropicAuthError(AnthropicError):
    """The admin key is wrong, revoked, or not an admin key."""


class AnthropicCostClient:
    """Reads daily spend from the Admin API cost report."""

    def __init__(self, session: aiohttp.ClientSession, admin_key: str) -> None:
        self._session = session
        self._headers = {"x-api-key": admin_key, "anthropic-version": API_VERSION}

    async def daily_costs(self, start: date) -> dict[date, float]:
        """Return dollars spent per UTC day, from `start` up to today."""
        params = {
            "starting_at": f"{start.isoformat()}T00:00:00Z",
            "bucket_width": "1d",
            "limit": "31",
        }
        days: dict[date, float] = {}
        for _ in range(MAX_PAGES):
            page = await self._get(params)
            for bucket in page.get("data", []):
                day = date.fromisoformat(bucket["starting_at"][:10])
                # Amounts are decimal strings in cents.
                cents = sum(float(r.get("amount") or 0) for r in bucket.get("results", []))
                days[day] = days.get(day, 0.0) + cents / 100
            if not page.get("has_more") or not page.get("next_page"):
                break
            params["page"] = page["next_page"]
        return days

    async def _get(self, params: dict[str, str]) -> dict:
        try:
            async with self._session.get(
                COST_REPORT_URL,
                headers=self._headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise AnthropicAuthError(f"HTTP {resp.status}")
                body = await resp.json(content_type=None)
                if resp.status >= 400:
                    message = (body or {}).get("error", {}).get("message", "")
                    raise AnthropicError(f"HTTP {resp.status} {message}".strip())
                return body
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise AnthropicError(str(err) or type(err).__name__) from err
