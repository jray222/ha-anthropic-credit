# AGENTS.md: handoff guide for coding agents

Read this first. Also read `AGENTS.local.md` if it exists (git-ignored, private owner context).

## What this is

Home Assistant custom integration **Anthropic Credit** (domain `anthropic_credit`), installed
through HACS. Anthropic has no credit-balance API, so it estimates what is left:
balance the user entered after a top-up, minus spend from the Admin API cost report since
that day.

## Hard rules

1. Never commit secrets (admin keys, the owner's email or hostnames). The repo is public.
2. The admin key is only entered in the HA UI and only sent in the `x-api-key` header.
3. Plain code, simple English UI text, nothing that needs Jinja in HA to use.
4. Every change goes through a PR with CI green and bumps `manifest.json` `version`.
5. `translations/en.json` must stay identical to `strings.json`.

## Files

- `api.py`: `AnthropicCostClient.daily_costs(start)` calls
  `GET https://api.anthropic.com/v1/organizations/cost_report` (`starting_at`, `bucket_width=1d`,
  `limit=31`, pages via `next_page`, max 40 pages). Amounts are decimal strings in **cents**.
  401/403 -> `AnthropicAuthError`.
- `coordinator.py`: polls every `scan_interval` minutes (default 30), fetches from the earliest of
  top-up date, 1st of month, yesterday; builds `CreditData`. Auth error -> reauth.
- `sensor.py`: five monetary USD sensors (`remaining`, `spent_since_top_up`, `spent_today`,
  `spent_yesterday`, `spent_this_month`) on one service device.
- `config_flow.py`: user step (admin key, balance, top-up date), reauth, options (balance,
  top-up date, scan interval). Settings are read options-first, then entry data.

## Tests and CI

```bash
pip install pytest-homeassistant-custom-component ruff
ruff check custom_components tests --select E,F,W,B --ignore E501
pytest -q
```

CI also runs hassfest and the HACS action. Tests mock the cost report with `AiohttpClientMocker`.
