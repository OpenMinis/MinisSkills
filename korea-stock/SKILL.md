---
name: korea-stock
description: >
  Check South Korean stock market quotes, including the KOSPI and KOSDAQ indices and their constituent stocks.
  Use the mobile version of Naver Finance (finance.naver.com); no login is required.
  Triggered when users say "Korean stocks," "South Korean stock market," "KOSPI," "KOSDAQ," "Samsung Electronics," or "SK Hynix."
version: 1.0.0
---

# South Korean Stock Market Quote Lookup

## Data Source

Naver Finance mobile site, `finance.naver.com`
- Use `browser_use` with `get_readable` to retrieve the complete data
- No account is required; Chinese IP addresses can access it directly

## Query the KOSPI Index

navigate: https://finance.naver.com/sise/sise_index.naver?code=KOSPI
wait_for_dom_stable
get_readable: Extract the full page text

The data includes:
- Current KOSPI index level, point change, and percentage change
- Trading volume (thousands of shares) and trading value (millions of KRW)
- Intraday high/low and 52-week high/low
- Number of advancing and declining stocks
- Net buying/selling amounts by individual, foreign, and institutional investors
- Real-time prices of popular constituent stocks

## Query the KOSDAQ Index

navigate: https://finance.naver.com/sise/sise_index.naver?code=KOSDAQ
get_text: Extract data

## Query Individual Stock Quotes

| Stock | Naver Code |
|------|-----------|
| Samsung Electronics | 005930 |
| SK Hynix | 000660 |

## Report Format

KOSPI: 8,476.15 (+3.55%)
  High: 8,476.15 | Low: 8,273.74

## Notes

- Naver uses Korean; key data is numeric and is not affected by the language
- South Korean stock market trading hours: 08:00-14:30 Beijing Time
- Data is delayed by approximately 15-20 minutes
- Chinese IP addresses can access the site directly without a VPN
