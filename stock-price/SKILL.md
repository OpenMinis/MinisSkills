---
name: stock-price
description: >
  Check real-time quotes for A-shares, Hong Kong stocks, ETFs, and indices (latest price, percentage change, trading volume, etc.).
  Uses the Tencent Quotes API (qt.gtimg.cn); no login or API key required.
  Triggers when a user says "check stock prices," "real-time quotes," "ETF prices," "stock quotes," or "what is the market index?"
version: 1.0.0
---

# Real-Time Stock, ETF, and Index Quotes

## Data Sources (by Priority)

| Priority | Data Source | Features |
|--------|--------|------|
| Preferred | Tencent Quotes API (qt.gtimg.cn) | Fastest; get all data with a single `curl` command, no login required |
| Alternative | Sina Finance (gu.sina.cn) | Homepage displays market indices and the top 6 popular industries |
| Alternative | East Money (data.eastmoney.com/bkzj/hy.html) | Sector capital flows; desktop user agent required |

## Tencent Quotes API (Preferred)

### Request Format

curl -s "qt.gtimg.cn/q=<list of codes, comma-separated>"

### Stock Code Format

| Market | Format | Example |
|------|------|------|
| Shanghai A-shares | sh + 6-digit code | sh600519 (Kweichow Moutai) |
| Shenzhen A-shares | sz + 6-digit code | sz000001 (Ping An Bank) |
| Hong Kong stocks | hk + 5-digit code | hk00700 (Tencent Holdings) |
| SSE Composite Index | sh000001 | SSE Composite Index |
| ChiNext Index | sz399006 | ChiNext Index |

### Return Format

Returned text is separated by `~`:
v_<code>="1~<name>~<code>~<latest price>~<previous close>~<open>~..."

Key field indexes (separated by `~`, starting from 0):
- 1: Name
- 3: Latest price
- 32: Percentage change (%)
- 6: Trading volume (lots)
- 7: Trading value (yuan)

### Example

curl -s "qt.gtimg.cn/q=sh000001,sz399006,sh588170,hk00700"

Python parsing example:
fields = line.split('="')[1].rstrip('";').split('~')
name = fields[1]
price = fields[3]
change_pct = fields[32]

## Sina Finance (Alternative)

navigate: https://gu.sina.cn
get_readable: Extract market indices, popular industries, and the number of stocks up and down

## Reporting Format

SSE Composite Index: 4068.57 (-0.73%)
ChiNext Index: 2140.32 (+0.85%)

## Notes

- Updates in real time during trading hours; after hours, the closing price is displayed
- The free version for Hong Kong stocks has a 15-minute delay
- A single query should include no more than 20 codes
- The returned encoding is GBK
