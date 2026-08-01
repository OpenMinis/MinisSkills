---
name: us-stock
description: Real-time U.S. stock market quotes. The three major indices (Dow/S&P 500/Nasdaq) + the Magnificent 7 (NVDA/AAPL/MSFT/GOOGL/AMZN/META/TSLA) + the VIX fear index + 0DTE Gamma status analysis. Triggered when users say "U.S. stocks," "check U.S. stocks," "U.S. stock market," "Magnificent 7," "VIX," "fear index," "S&P," "Nasdaq," or "Dow."
version: 1.0.0
---

# U.S. Stock Market Quote Lookup

## Data Source
Google Finance (`browser_use navigate` + `get_text`): no API or login required; returns structured data.

## Query Process

### Step 0: Set the Desktop Viewport
```
browser_use set_viewport viewport_width: 1280 viewport_height: 800
```
Google Finance distinguishes between desktop and mobile versions mainly by viewport width. Setting a wide enough viewport is sufficient to retrieve the full data. This method is compatible across Android and iOS and is not affected by differences in UA enumeration values.

### Step 1: The Three Major Indices (in parallel, with up to 3 tabs open at once)
First, open the S&P 500 in the default tab 0:
```
browser_use navigate https://www.google.com/finance/quote/.INX:INDEXSP?hl=en
browser_use get_text
```
Then create two new tabs and open the Dow and Nasdaq:
```
browser_use new_tab
browser_use navigate https://www.google.com/finance/quote/.DJI:INDEXDJX?hl=en
browser_use get_text

browser_use new_tab
browser_use navigate https://www.google.com/finance/quote/.IXIC:INDEXNASDAQ?hl=en
browser_use get_text
```
Use `get_text` to extract data from each tab. Extract the key fields: current price, point change, percentage change, open/high/low, and previous close.

### Step 2: VIX Fear Index (navigate in an existing tab; do not open a new tab)
```
browser_use navigate https://www.google.com/finance/quote/VIX:INDEXCBOE?hl=en
browser_use get_text
```
Key fields: current price, percentage change, previous close, 52-week high/low.

**VIX alert thresholds**: <15 complacency / 15-20 normal / 20-25 caution / 25+ panic.

Core assessment: VIX absolute level + the day's direction of change. Distinguish a mild VIX rise caused by an individual-stock event such as Broadcom from a VIX spike caused by systemic panic.

### Step 3: Magnificent 7 (rotate through the existing 3 tabs; do not open new tabs)
**There is no dedicated 4th tab for VIX**. First navigate the default/latest tab to NVDA, extract with `get_text`, then navigate that same tab to the next stock.

Reading order: NVDA → AAPL → MSFT → GOOGL → AMZN → META → TSLA

After each stock is read, `navigate` to the next stock's URL and use `get_text` each time.

If AVGO or other popular stocks need to be checked, put them after TSLA. For each stock, extract: price, percentage change, point change, previous close, intraday high/low, and market capitalization.

### Step 4: 0DTE Gamma Status (optional; check when the user requests it or when broad market volatility is abnormal)
**First close one tab you have already finished reading to free up space** (for example, close the VIX tab or the earliest index tab), then open a new tab:
```
browser_use close_tab
browser_use new_tab
browser_use navigate https://www.google.com/search?q=SPX+gamma+exposure+today+dealer+position&hl=en
browser_use get_text
```
Extract the Gamma status summary from the AI Overview, focusing on:
- **Gamma Flip level**: the S&P level where Gamma shifts from positive to negative
- **Gap between the current SPX level and the Flip** (for example, current price 7,583, Flip at 7,550, gap 33 points = 0.4%)
- **Dealer positioning**: positive gamma (stable) or negative gamma (amplifies volatility)

**GEX risk assessment criteria:**

| Status | Description | Risk |
|:---|:---|:---:|
| Positive Gamma | Market makers move with the trend, buying dips and selling rallies | Market is stable and volatility is suppressed |
| Near Flip (0-1%) | Golden dividing line, critical zone | One unexpected event can trigger a Gamma squeeze |
| Negative Gamma | Market makers chase rallies and sell sell-offs | Volatility self-amplifies, and pullbacks can easily turn into crashes |

### Step 5: Synthesize the Output
Output structure (concise tables + text interpretation):

## 📊 Real-Time U.S. Stock Market Quotes

**Time**: YYYY-MM-DD HH:MM ET

### Three Major Indices
| Index | Price | Change | Previous Close | Intraday |
|:---|:---:|:---:|:---:|:---:|
| Dow | xxx | +x.xx% | xxx | H:xxx L:xxx |
| S&P | xxx | +x.xx% | xxx | H:xxx L:xxx |
| Nasdaq | xxx | +x.xx% | xxx | H:xxx L:xxx |

### Fear Index
VIX: xx.xx (change x.xx%) - status assessment (complacency/normal/caution/panic)

### Magnificent 7
| Stock | Price | Change | Notes |
|:---|---:|:---:|:---|
| NVDA | xxx | +x.xx% | Key driver |
| ... | ... | ... | ... |

### Gamma Status (if queried)
Current SPX price xxx, Gamma Flip at xxx (gap x.xx%), currently Positive/Near Flip/Negative Gamma.

### Interpretation
In 2-4 sentences, explain today's main market theme (rotation/crash/range-bound trading), key drivers, and noteworthy risk signals.

### Step 6: Write to Log
Use `memory_write` to record a summary of today's U.S. stock market quotes (the three major indices + VIX + Magnificent 7 + interpretation).

## Important Notes
- U.S. stock market trading hours: 9:30-16:00 ET (daylight saving time = Beijing time 21:30-04:00 the next day; standard time = 22:30-05:00)
- Mark the timestamps for pre-market/post-market data, and note the comparison with A-share trading hours
- Google Finance displays Eastern Time, UTC-4 (daylight saving time) or UTC-5 (standard time)
- Fund/ETF NAVs lag by one day. When querying them, label them as "previous trading day's NAV"
- VIX futures backwardation is the strongest early warning signal of systemic risk. When it appears, push this signal to memory and alert the user.
