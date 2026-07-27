---
name: reverse-dcf
description: Reverse DCF (reverse discounted cash flow) valuation tool. Uses the market price to back-solve the market's implied growth rate expectations, replacing the common forward DCF routine of "tweaking parameters to fit the conclusion." Suitable for mature companies with positive FCFF (A-shares, Hong Kong-listed stocks, and U.S.-listed stocks). Trigger when the user says "reverse DCF," "Reverse DCF," "implied growth rate," "market-implied expectations," "price in," "valuation back-solve," "reverse valuation," "run a DCF," or asks to "calculate what the market is betting on." Not suitable for companies with negative FCFF (in that case, use a PS-implied revenue back-solve instead).
version: 1.0.0
---
# Reverse DCF: Deriving Market-Implied Expectations

## Core Idea

Forward DCF: given assumptions, calculate a target price. The parameters can be adjusted arbitrarily and end up "serving the conclusion."

**Reverse DCF: given the market price, back-solve the implied growth rate and translate "expensive" or "cheap" into a verifiable proposition.**

The essential difference:

- Forward DCF outputs "fair value." It is abstract, and you can always be right, but your wallet will not get any thicker.
- Reverse DCF outputs "market expectations": specific, verifiable numbers that can be compared with reality.

## Applicability

**Necessary condition: base-year FCFF must be positive.**

Applying a standard two-stage DCF to companies with negative FCFF, such as early-stage high-growth companies or companies in an asset-heavy expansion phase, produces meaningless results.

Alternative: use **PS-implied revenue back-solving** (see "Handling Special Cases" below).

**Data requirements:**

- Latest complete annual report (income statement, balance sheet, and cash flow statement)
- Current stock price/market capitalization
- Details of interest-bearing debt (short-term borrowings, long-term borrowings, lease liabilities, etc.)
- Risk-free rate (10-year government bond yield)
- Industry β and ERP (Damodaran data recommended)

## Practical Steps

### Step 1: Determine Enterprise Value (EV)

```
EV = Market Capitalization + Net Debt
Net Debt = Interest-Bearing Debt - Cash and Cash Equivalents - Financial Assets Held for Trading
```

Notes:

- For companies like SK Hynix that are in a "net cash" position (cash > interest-bearing debt), EV will be lower than market capitalization.
- For A-share companies, check whether financial assets held for trading include wealth management products, which are treated as cash equivalents.
- STAR Market companies often have large amounts of IPO or financing proceeds sitting on the balance sheet, so EV may be far lower than market capitalization.

### Step 2: Calculate Base-Year FCFF (the core step and the easiest place to make mistakes)

**Recommended Method A: Back-solve from CFO (most reliable in practice)**

```
FCFF = CFO - Capex + After-Tax Interest Expense
```

- CFO = net cash flow from operating activities (audited real cash).
- Capex = cash paid to acquire and construct fixed assets and intangible assets.
- Net-cash companies: after-tax interest ≈ 0.

**Verification Method B: Bottom-up from NOPAT**

```
NOPAT = Operating Profit × (1 - Effective Tax Rate)
FCFF = NOPAT + D&A - Capex - ΔWC
```

- **Effective tax rate ≠ statutory tax rate** (for example, South Korea's statutory rate is 24%, while SK Hynix's effective rate is only 14.9%).
- D&A = depreciation and amortization.
- ΔWC = increase in working capital (changes in inventory + accounts receivable + prepayments - accounts payable - contract liabilities).
- Cross-check the two methods and take the average.

**Important: the base year determines everything**

- Using FCFF at the top of the cycle → implied CAGR is understated.
- Using cycle-median FCFF → implied CAGR is on the high side.
- This is a judgment, not a calculation.

### Step 3: Build the WACC

```
Re = Rf + β × ERP
WACC = Re × We + Rd×(1-t) × Wd
```

Suggested parameter sources:

| Parameter | Source |
|:---|---|
| Risk-free rate Rf | 10-year government bond yield in the company's home country |
| Equity risk premium ERP | Damodaran annual data (varies by country) |
| β | Damodaran industry unlevered β → re-lever based on D/E (more robust than a single-stock regression β) |
| Pre-tax cost of debt Rd | Average level of investment-grade corporate bonds in the company's home country |
| Effective tax rate | Company's actual effective tax rate (calculated from financial statements, not the statutory rate) |

### Step 4: Two-Stage DCF Model

```
EV = Σ [FCFF₀ × (1+g₁)ᵗ / (1+WACC)ᵗ] + [FCFF₁₀ × (1+g₂) / (WACC-g₂)] / (1+WACC)¹⁰
```

Where:

- g₁ = annualized FCFF growth rate during the explicit forecast period (10 years) ← **the target to back-solve**
- g₂ = perpetual growth rate (usually 2.5-3%, approximately nominal GDP growth)
- FCFF₁₀ = FCFF₀ × (1+g₁)¹⁰ × (1+g₂)

**Forward DCF: given g₁ and g₂, solve for EV.**

**Reverse DCF: given EV and g₂, solve for g₁.**

### Step 5: Build a Sensitivity Table

```
              Perpetual growth g₂
            1.5%  2.0%  2.5%  3.0%  3.5%
     18%     xxx   xxx   xxx   xxx   xxx
CAGR 20%     xxx   xxx   xxx   xxx   xxx
g₁   22%     xxx   xxx   xxx   xxx   xxx
     25%     xxx   xxx   xxx  [1189] xxx  ← Target EV
     28%     xxx   xxx   xxx   xxx   xxx
```

1. Each cell = the EV under the corresponding (CAGR, g₂) combination.
2. Find the cell closest to the **actual EV**.
3. The g₁ corresponding to that cell is the **market-implied explicit-period CAGR expectation**.

**Key observations:**

- Valuation sensitivity to explicit-period CAGR >> sensitivity to perpetual g.
- Valuation differences are not large within the same row (same CAGR), while valuations can differ by a factor of two within the same column (same perpetual g).
- Therefore, the key valuation question is whether the "10-year CAGR can be achieved," not whether "3% perpetual growth is too aggressive."

### Step 6: Translate CAGR into Plain English

After calculating the implied CAGR, make three translations:

**Translation 1: Company size in 10 years**

```
FCFF₁₀ = FCFF₀ × (1+g₁)¹⁰
Corresponding revenue ≈ FCFF₁₀ / (current FCFF/revenue conversion rate)
```

**Translation 2: What needs to happen at the industry level**

```
Current TAM → required revenue in 10 years → implied market share change
Or: how many times TAM must grow to support it
```

**Translation 3: Compare with history**

```
Company's actual CAGR over the past 10 years vs implied CAGR
Historical CAGR comparison with industry peers/global tech giants
(TSMC's CAGR over the past 20 years was approximately 18%, already an industry miracle)
```

### Step 7: Be Honest About Limitations

1. **Terminal value (TV) accounts for a high proportion of EV**: this is especially dangerous for cyclical stocks. TV accounting for >50% is a red flag.
   - Alternative: Exit Multiple method (use the industry median EV/EBITDA in year 10 for the exit).
2. **The choice of base-year FCFF determines everything**: the top and bottom of the cycle can differ by several times.
3. **D&A and Capex are estimates**: accuracy is limited by the granularity of public disclosures.
4. **Reverse DCF tells you what the market expects, not whether the market is right or wrong.**
   - A 25% CAGR may or may not be reasonable and requires independent judgment.
   - It is not a conclusion. It is the starting point for discussion.

## Handling Special Cases

### Companies with Negative FCFF (such as Cambricon)

A standard two-stage DCF cannot be used for the back-solve. Use **PS-implied revenue back-solving** instead:

1. Assume a reasonable terminal PE, such as 30x in the mature phase.
2. Back-solve the required net profit 10 years from now.
3. Then assume a reasonable net margin and back-solve the required revenue 10 years from now.
4. Calculate the implied revenue CAGR.

```
Implied Revenue₁₀ = Market Capitalization / Terminal PE / Net Profit Margin
Implied CAGR = (Implied Revenue₁₀ / Current Revenue)^(1/10) - 1
```

### Cyclical Stocks

Use **cycle-median FCFF** instead of a single year's FCFF as the base-year data.

You can also use the Exit Multiple method instead of the Gordon Growth Model to calculate terminal value.

## Recommended Data Sources

| Data | Recommended acquisition method |
|:---|---|
| Stock price/market capitalization | `browser_use navigate` to Sina Finance or Xueqiu individual stock pages, then use `get_text` to extract |
| Financial statement data | Use `browser_use navigate` to open `https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=<stock-code>`; the income statement, balance sheet, and cash flow statement tabs provide the complete data. |
| Details of interest-bearing debt | Same as above, balance sheet tab: short-term borrowings, long-term borrowings, lease liabilities, and bonds payable |
| CFO/Capex | Same as above, cash flow statement tab: net cash flow from operating activities and cash paid to acquire and construct fixed assets |
| Industry β/ERP | Damodaran Online (pages.stern.nyu.edu/~adamodar/) |
| 10-year government bond yield | TradingView or official central bank websites, retrieved with `browser_use navigate` |
| Historical revenue/CAGR | East Money PC_HSF10 income statement tab, pull 5-10 years of revenue data and calculate manually |

> Note: All data should be retrieved in real time through `browser_use`; do not rely on training data. A-share stock codes in emweb format are `SH600519` (Shanghai) or `SZ000651` (Shenzhen), and Hong Kong stocks use `HK00700`.

## Practical Case References

Series of articles (author: monokuro, Manager on the valuation team at a Big Four accounting firm in Tokyo):

1. **Core case**: "[What Expectations Is the Market Pricing In for SK Hynix? Reverse DCF Gives You a Startling Number](https://zhuanlan.zhihu.com/p/2036428331852228430)": uses Reverse DCF to calculate that SK Hynix's current stock price implies 25% annualized FCFF growth over the next 10 years. FCFF would need to reach 208 trillion won in 10 years, nine times 2025 revenue and twice the actual growth rate over the past 10 years (13%).
2. **Method correction**: "[Three Corrections to the Previous Reverse DCF for the Five AI Chip Giants](https://zhuanlan.zhihu.com/p/2038261840434701481)": points out practical pitfalls such as using Exit Multiple instead of GGM, replacing single-year FCFF with cycle-median FCFF, and correcting data sources. It can be used as supplemental reference for the limitations section of Reverse DCF.

The core methodological reference is Aswath Damodaran's valuation framework (*Investment Valuation* and the country risk premium data updated each year).
