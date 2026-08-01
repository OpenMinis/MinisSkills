---
name: deepseek-usage
description: >
  Check DeepSeek API usage (balance, this month's spending, token breakdown by model, daily breakdown, and cache hit rate).
  Access the DeepSeek Open Platform through browser_use, automatically log in, and export monthly data.
  Users must configure their DeepSeek account in local environment variables.
  Triggered when the user says "check usage," "view token consumption," "check spending," "how much balance is left," or "how much was used today."
version: 1.1.0
compatibility: Requires python3. DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD env vars.
---

# DeepSeek API Usage Query

> ⚠️ **Security Notice**
> This skill requires DeepSeek login credentials to work.
> Credentials are stored only in local environment variables. **Minis does not upload them to any server**.
> If you do not trust this method, delete this skill or do not set any credentials.

## Prerequisite Configuration (first use only)

### 1. Set Environment Variables

Add the following two variables in Minis Settings → Environment Variables:

| Variable Name | Description | Example Value |
|--------|------|--------|
| `DEEPSEEK_EMAIL` | Your DeepSeek platform login email address | `user@example.com` |
| `DEEPSEEK_PASSWORD` | Your DeepSeek platform login password | `your_password_here` |

🔗 [Click here to open the environment variable settings](minis://settings/environments)

> If your account uses a third-party login such as Google or WeChat, you cannot use this skill.

### 2. Verify the Configuration

```bash
[ -n "$DEEPSEEK_EMAIL" ] && [ -n "$DEEPSEEK_PASSWORD" ] && echo "Configured" || echo "Not configured"
```

## Query Process (requires only 2 tool calls)

### Step 1: Navigate and Ensure Login (1 tool call)

```yaml
Action:
  - set_user_agent: desktop_chrome
  - navigate: https://platform.deepseek.com/usage
  - If not logged in, fill DEEPSEEK_EMAIL / DEEPSEEK_PASSWORD from environment variables and submit the login form
  - wait_for_dom_stable
```

### Step 2: Run the complete JS script in one step (1 `execute_js`)

The following JS script completes all logic: **get token → download ZIP → unzip → parse CSV → output**.

Run the entire JS script as the argument to `execute_js --script` in a single execution.

```js
(async () => {
  // === Get summary text ===
  // Extract with get_readable (done outside execute_js)

  // === Get Token ===
  const token = JSON.parse(localStorage.getItem('userToken')).value;
  if (!token) return JSON.stringify({ error: 'no_token' });

  // === Download zip ===
  const resp = await fetch('https://platform.deepseek.com/api/v0/usage/export?month=5&year=2026', {
    headers: { 'Authorization': 'Bearer ' + token }
  });
  const blob = await resp.blob();

  // === Load JSZip ===
  const script = document.createElement('script');
  script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
  await new Promise(r => { script.onload = r; document.head.appendChild(script); });

  // === Unzip ===
  const zip = await JSZip.loadAsync(blob);
  const costText = await zip.file('cost-2026-5.csv').async('text');
  const amountText = await zip.file('amount-2026-5.csv').async('text');

  // === Parse cost (fees) ===
  // ⚠️ Header: user_id, utc_date, model, wallet_type, cost, currency
  const costLines = costText.trim().split('\n').slice(1);
  const modelCost = {};
  let totalCost = 0;
  for (const line of costLines) {
    const p = line.split(',');
    const model = p[2], cost = parseFloat(p[4]) || 0;
    modelCost[model] = (modelCost[model] || 0) + cost;
    totalCost += cost;
  }

  // === Parse amount (usage, filter by date as needed) ===
  // ⚠️ Header: user_id, utc_date, model, api_key_name, api_key(sensitive!), type, price, amount
  // ⚠️ Security warning: Column 5 is the plaintext api_key. Do not print entire lines! You must use index references.
  const allLines = amountText.trim().split('\n').slice(1);

  // Filtering rule: if the user asks about today's usage, filter to today; if the user asks about this month's usage, use the full month
  // Default is today. For today's usage, uncomment the following line:
  // const targetDate = 'current date in YYYY-MM-DD format';
  // const filteredLines = targetDate ? allLines.filter(l => l.split(',')[1] === targetDate) : allLines;
  const filteredLines = allLines; // Default: full month

  const models = {};
  for (const line of filteredLines) {
    const p = line.split(',');
    const model = p[2], type = p[5], amount = parseInt(p[7]) || 0;
    if (!models[model]) models[model] = { requests: 0, cache_hit: 0, cache_miss: 0, output: 0 };
    if (type === 'request_count') models[model].requests += amount;
    else if (type === 'input_cache_hit_tokens') models[model].cache_hit += amount;
    else if (type === 'input_cache_miss_tokens') models[model].cache_miss += amount;
    else if (type === 'output_tokens') models[model].output += amount;
  }

  // === Summary output ===
  let result = '';
  let gr = 0, go = 0, gh = 0, gm = 0;

  for (const [m, d] of Object.entries(models)) {
    const ti = d.cache_hit + d.cache_miss;
    const hr = ti > 0 ? (d.cache_hit / ti * 100).toFixed(1) : '0.0';
    const co = modelCost[m] || 0;
    result += `${m}|${d.requests}|${d.output}|${d.cache_hit}|${d.cache_miss}|${ti}|${hr}|${co.toFixed(2)}\n`;
    gr += d.requests; go += d.output; gh += d.cache_hit; gm += d.cache_miss;
  }

  const ti = gh + gm;
  const hr = ti > 0 ? (gh / ti * 100).toFixed(1) : '0.0';
  result += `TOTAL|${gr}|${go}|${gh}|${gm}|${ti}|${hr}|${totalCost.toFixed(2)}`;

  return result;
})();
```

> ⚠️ Note: `execute_js` returns text wrapped in JSON. The AI needs to parse `data.text` to get the actual result.

### Step 3: Screenshot (1 tool call, optional)

```yaml
screenshot: current page
```

### Step 4: Report (memory_write is decided by the user)

Whether to write the results to the daily log is **decided by the user**. Write only when the user explicitly asks.

### Output Format

**Balance:** ¥X.XX | **Spent This Month:** ¥X.XX

![Usage Screenshot](minis://browser/screenshot_xxx.jpg)

| Model | Requests | Output Tokens | Cache Hits | Cache Misses | Total Input Tokens | Cache Hit Rate | Cost |
|------|---------|------------|---------|-----------|-------------|-----------|------|
| deepseek-v4-pro | X | X | X | X | X | X% | ¥X.XX |
| deepseek-v4-flash | X | X | X | X | X | X% | ¥X.XX |
| **Total** | **X** | **X** | **X** | **X** | **X** | **X%** | **¥X.XX** |

## ⚠️ Security Precautions (must be followed)

### API Key Leakage Risk
Column 5 (index 4) of the amount CSV is the `api_key` field and contains the user's DeepSeek API Key in **plaintext**.

**Requirements:**
- When parsing CSV, use column index references such as `p[2]`, `p[5]`, and `p[7]`; do not reference the entire line
- **Do not** directly or indirectly display `api_key` content in any reply, log, or screenshot
- If you need to inspect CSV content during debugging, print only the header (row 1), not the data rows

### Credential Security
- Email and password are stored in Minis local environment variables and are not uploaded
- The localStorage token is valid only for the current browser session
- We recommend changing your password regularly

## Troubleshooting Notes

| Issue | Cause | Solution |
|------|------|---------|
| Export button click has no effect | The export button is a `<div>`, not a `<button>` | Use `querySelector` to match the text "Export", then call `.click()` |
| browser_use fetch returns Missing Token | fetch does not include page cookies | Use `execute_js` instead to run fetch in the page context |
| JSZip fails to load | The `import()` method is not supported | Use `document.createElement('script')` to dynamically load the CDN |
| CSV parses to 0 records | Incorrect field indexes were guessed | First confirm the headers (8 columns for amount, 6 columns for cost), then reference by index |
| amount.csv contains plaintext API Key | Column 5 is `api_key` | Use column indexes during parsing; do not print the entire row |
| minis-browser-use CLI loses state across calls | Each call is a separate process | Put all JS logic in a single `execute_js` execution; do not pass state across `navigate` and `execute_js` |
