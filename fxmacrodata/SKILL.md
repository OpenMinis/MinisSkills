---
name: fxmacrodata
description: Official macroeconomic data from FXMacroData for 22 currencies - central bank policy rates, CPI, GDP, payrolls, unemployment, PMIs, bond yields and other releases with their exact publication times, the upcoming release calendar, and daily FX rates. Use this skill when the user asks about an economic release or central bank decision ("what was the last US CPI", "when is the next Fed decision", "show RBA rate history", "what's on the US calendar this week", "EUR/USD rate history"), wants macro context for a currency pair, or needs release timestamps for a backtest, even if they don't mention FXMacroData.
compatibility: Python 3.8+, standard library only
---

# FXMacroData

Fetch official macro releases, release calendars and FX rates from the FXMacroData REST API with `scripts/fxmd.py`. Every value comes from the publishing central bank or statistics office, and each release row carries its source URL and publication time.

## What works without a key
- USD release history for the most recent 90 days, delayed by 15 minutes
- The USD release calendar
- The indicator catalogue for every currency

Other currencies, FX rates, full history and real-time releases need an API key in `FXMACRODATA_API_KEY`. If the user asks for one of those and the key is missing, answer the USD equivalent first if it helps, then ask them to [Set FXMACRODATA_API_KEY](minis://settings/environments?create_key=FXMACRODATA_API_KEY&create_value=). Keys come from https://fxmacrodata.com/subscribe.

## Workflow
1. If you are not sure of the indicator slug, run `catalogue` for the currency first. Slugs look like `policy_rate`, `inflation`, `core_inflation`, `non_farm_payrolls`, `unemployment`, `gdp`. Guessing a slug wastes a call on a 404.
2. For "latest" or "history" questions, run `history`. Rows are newest first.
3. For "when is the next..." questions, run `calendar`, optionally with `--indicator`.
4. Read `notices` in every result. Keyless results say when data is delayed or limited to 90 days; repeat that to the user instead of presenting the value as the most recent possible one.

## Commands
```bash
# Indicators available for a currency (compact list, works for every currency without a key)
python3 /var/minis/skills/fxmacrodata/scripts/fxmd.py catalogue usd

# Latest releases for one indicator (first page, 20 rows by default)
python3 /var/minis/skills/fxmacrodata/scripts/fxmd.py history usd inflation --limit 3

# A full date range, following pagination
python3 /var/minis/skills/fxmacrodata/scripts/fxmd.py history usd policy_rate --start 2026-01-01 --end 2026-09-30 --all

# Upcoming releases, optionally for one indicator
python3 /var/minis/skills/fxmacrodata/scripts/fxmd.py calendar usd --indicator non_farm_payrolls

# Daily FX rates (needs a key)
python3 /var/minis/skills/fxmacrodata/scripts/fxmd.py fx eur usd --start 2026-09-01 --end 2026-09-30
```

Every command prints one JSON object. On success it has `"ok": true`, `data` and `notices` (`history` and `fx` also report `has_more`). On failure it has `"ok": false` and an `error` message, and the script exits with status 1. A 401 error means the request needs an API key.

## Reading the data
- `val` is the released value. `previous_value` and `change_from_previous` are included on history rows.
- In history and calendar rows, `date` is the reference period the number describes (for example `2026-08-31` for August CPI), not the day it was published. Use `announcement_datetime` (Unix seconds, UTC) or `announcement_datetime_local` for the publication time. This matters for backtests: a value is only known from its announcement time onward.
- Calendar rows have no consensus forecasts. `event_importance` and `market_tier` show how market-moving a release usually is.
- Cite the `source_url` of a row when you quote a figure.

## Notes
- Dates must be real calendar dates in `YYYY-MM-DD` form, and `--start` must not be after `--end`. Currency codes are 3 letters. The script checks these before calling the API.
- `--limit` accepts 1-100 rows per page.
- The key is sent only in the `X-API-Key` header to `api.fxmacrodata.com`; redirects are refused so it is never sent anywhere else, and it is removed from any output or error text.
- Hosted MCP server, for clients that support remote MCP: `https://mcp.fxmacrodata.com`.
- API reference: https://fxmacrodata.com/documentation
