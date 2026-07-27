---
name: stock-fund-flow
description: >
  Query capital flows for A-share industry sectors and concept sectors, including rankings of main-force net inflows/outflows.
  Use the East Money Data Center to directly retrieve complete JSON data from the page data component.
  Trigger this skill when the user says "sector funds," "fund flows," "main-force net inflow," or "sector rankings."
version: 1.0.0
---

# A-Share Sector Fund Flow Query

## Data Sources

| Type | Page |
|------|------|
| Industry sectors | https://data.eastmoney.com/bkzj/hy.html |
| Concept sectors | https://data.eastmoney.com/bkzj/gn.html |

## Required Steps

### 1. Switch to the desktop UA

browser_use set_user_agent desktop_chrome

The mobile version only shows the top 20 entries and has no search function, so the desktop UA must be used.

### 2. Navigate to the page

navigate: https://data.eastmoney.com/bkzj/hy.html
wait_for_dom_stable

### 3. Retrieve the complete data from the dataview component

Use `execute_js` to retrieve data from the jQuery dataview component:

const dv = jQuery('#dataview').data('dataview');
const rows = dv.data;

### 4. Data Fields

f14: Sector name
f2: Latest sector price
f3: Price change (%)
f62: Main-force net inflow (CNY)
f66: Extra-large order net inflow (CNY)
f78: Large order net inflow (CNY)

### 5. Sorting and Filtering

Sort by price change: rows.sort((a, b) => b.f3 - a.f3)
Filter for inflows: rows.filter(r => r.f62 > 0)
Filter for outflows: rows.filter(r => r.f62 < 0)

### 6. Data Interpretation

Main-force net inflow > 0: Large funds are buying, and the sector may strengthen
Sharp decline + main-force net inflow: Shakeout (there is buying support)
Sharp decline + main-force net outflow: Distribution, so be cautious

## Reporting Format

### Industry Sector Fund Inflow TOP 5

| Sector | Price Change | Main-Force Net Inflow |
|------|--------|-----------|
| Electric Power | +2.46% | +5.56 billion |

### Industry Sector Fund Outflow TOP 5

| Sector | Price Change | Main-Force Net Inflow |
|------|--------|-----------|

## Notes

- Do not use the mobile UA or `get_readable` to read the table.
- Main-force net inflow = extra-large orders + large orders.
- There are approximately 128 industry sectors, with 50 entries per page.
