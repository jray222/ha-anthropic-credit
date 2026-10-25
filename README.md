# Anthropic Credit for Home Assistant

<p align="center"><img src="https://raw.githubusercontent.com/jray222/ha-anthropic-credit/main/images/logo.png" alt="Anthropic Credit" width="420"></p>

Shows roughly how much Anthropic API credit you have left, as Home Assistant sensors.

Anthropic has no API that returns your prepaid credit balance. What it does have is the
**Admin API cost report**, which says how much you spent each day. So this integration
takes the balance you type in after a top-up and subtracts what Anthropic reports you
have spent since that day.

## Sensors

All in US dollars, on one device called **Anthropic API credit**.

| Sensor | What it shows |
|---|---|
| Credit remaining | Balance you entered minus spend since the top-up date |
| Spent since top-up | Spend from the top-up date until now |
| Spent today | Today's spend so far (UTC day) |
| Spent yesterday | Yesterday's spend (UTC day) |
| Spent this month | Spend since the 1st of this month (UTC) |

## Install

1. In HACS, open the menu, choose **Custom repositories**, add
   `https://github.com/jray222/ha-anthropic-credit` as an **Integration**.
2. Install **Anthropic Credit** and restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration > Anthropic Credit**.

## Setup

You need an **Admin API key** (it starts with `sk-ant-admin`). Create one in the
[Claude Console](https://platform.claude.com/) under **Settings > Admin keys**.
Only organization admins can create one. A normal API key will not work.

The setup screen asks for:

- **Admin API key**. Stored in Home Assistant like any other integration secret.
- **Credit balance right after your last top-up**. Read it off
  **Settings > Billing** in the Claude Console.
- **Date of that top-up.**

## After you add credit

Go to **Settings > Devices & services > Anthropic Credit > Configure**, enter the new
balance and today's date, and press Submit. The sensors update right away.

Tip: if you set the date to today and type in the balance the Console shows right now,
the estimate starts fresh from that moment, which is the most accurate.

## Accuracy

- Days are UTC days, as Anthropic reports them. Spend earlier on the top-up day counts
  against the new balance, so the estimate errs on the low side.
- Spend shows up in the report about 5 minutes after a request.
- Priority Tier costs are not in the cost report.
- Anthropic can also add credit you did not buy (promotions, refunds); those are not seen.
  Re-enter the balance from the Console now and then to stay exact.

## Example: low credit alert

Use the automation editor: trigger **Numeric state** on
`sensor.anthropic_api_credit_credit_remaining`, **Below** `5`, then any notify action.

## Options

Under **Configure**: balance, top-up date, and how often to check (default 30 minutes).
If the key is revoked, Home Assistant asks for a new one (reauthentication).

## Icon

The icon and logo are original artwork made for this integration (not Anthropic's or Home
Assistant's logos). Home Assistant 2026.3 and later shows them on the Integrations page from
`custom_components/anthropic_credit/brand/`. The SVG sources are in `images/`.

HACS itself does not read these yet, so the HACS list may still say "Icon not available"
until HACS adds support (hacs/integration#5388). The home-assistant/brands repository no
longer takes custom integrations, so there is nothing else to submit.
