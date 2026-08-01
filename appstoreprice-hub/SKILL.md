---
name: appstoreprice-hub
description: >-
  A skill for querying App Store app prices across regions worldwide, using data from appstoreprice.org.
  It uses the Minis built-in browser (minis-browser-use CLI) to call the website's native signing function directly in the page context,
  with no API key and no need to implement the signing algorithm yourself. It supports searching for apps by name, querying prices for one app across all regions,
  retrieving rankings of the cheapest regions, and browsing app lists with pagination.
  This skill must be triggered when the user mentions "App Store prices," "which region is cheapest," "Turkey region price," "appstoreprice,"
  "app price comparison," "low-price App Store regions," "which subscription region is the best value," or any scenario that requires cross-region price comparisons for iOS/macOS apps.
---

# appstoreprice-hub

Query App Store global pricing data from [appstoreprice.org](https://appstoreprice.org).

> **Data source**: [appstoreprice.org](https://appstoreprice.org), an unofficial price comparison website maintained by [@qingnianxiaozhe](https://x.com/qingnianxiaozhe). It scrapes and compares App Store prices across regions worldwide in real time. This is not official Apple data. Prices are updated daily.

## How It Works

The website uses the Next.js App Router and accesses data in two ways:

1. **REST API** (search/list): requires the FNV-1a signature headers `X-Timestamp` + `X-Signature`
2. **RSC page stream** (price details): directly parse `fetch(url, { headers: { RSC: '1' } })`

The signing function is embedded in the page's webpack module (currently `22463`). Reuse it directly in the website page context instead of implementing it yourself. The module ID may change when the website is deployed or updated. See Troubleshooting.

## Execution Method: minis-browser-use CLI

**Always use the `minis-browser-use` CLI + shell script**. Do not use the `browser_use` tool call.

Benefit: JS code is read from a file and passed directly to the process, so it does not occupy the agent context.

### Standard Template

**All steps must be completed in the same `shell_execute` call** to prevent tab state from becoming invalid across calls.
Write business logic to a temporary file with `file_write` and then concatenate it. Do not use a heredoc, because BusyBox ash can easily parse braces or quotes incorrectly.

```bash
# Prerequisite: use file_write to write the business logic to /tmp/asp_logic.js, then:

minis-browser-use navigate --url "https://appstoreprice.org/zh/apps" \
  && minis-browser-use wait_for_dom_stable --timeout 8 \
  && minis-browser-use execute_js --script "$(cat /var/minis/skills/appstoreprice-hub/scripts/api.js /tmp/asp_logic.js)"
```

> **Why combine everything into one `shell_execute`?** The `minis-browser-use` browser tab may become invalid between two `shell_execute` calls (the tab may be recycled), and the second call may report `webpackChunk_N_E not found`. Serial execution in the same process keeps the tab state stable.

## API Quick Reference

`AppStorePriceAPI()` returns `{ search, list, prices, prices_all }`:

| Method | Parameters | Return |
|---|---|---|
| `search(query, page=1, limit=20)` | Keyword | `{ apps, hasMore, total }` |
| `list(page=1, limit=20)` | Page number/items per page | `{ apps, hasMore, total }` |
| `prices(appStoreId, locale='zh')` | App Store ID | Price array for the **first** tier, sorted by `priceUsd` in ascending order |
| `prices_all(appStoreId, locale='zh')` | App Store ID | List of price arrays for **all** tiers (required for multi-tier subscriptions, such as Claude Pro/Max) |

Each `prices` / `prices_all` item: `{ region, regionName, currency, price, priceUsd, priceCny }`

> ⚠️ **Multi-tier subscriptions** (such as ChatGPT Plus/Pro, Claude Pro/Max, etc.) must use `prices_all()`. `prices()` returns only the first subscription tier.

Common region codes: `US` United States, `TR` Turkey, `NG` Nigeria, `PK` Pakistan, `EG` Egypt, `AR` Argentina, `VN` Vietnam, `JP` Japan, `KR` South Korea, `CN` China, `HK` Hong Kong

## Typical Business Logic

### Multi-tier Subscriptions

```js
const asp = AppStorePriceAPI();
const sr = await asp.search('Claude');
const app = sr.apps.find(a => a.developer?.includes('Anthropic'));
const tierNames = ['Claude Pro (monthly)', 'Claude Max 5x (monthly)', 'Claude Max 20x (monthly)', 'Claude Pro (annual)'];
const allTiers = await asp.prices_all(app.appStoreId);
return allTiers.map((prices, i) => {
  const sorted = [...prices].sort((a, b) => a.priceUsd - b.priceUsd);
  const usPrice = prices.find(p => p.region === 'US')?.priceUsd;
  return {
    tier: tierNames[i] || `Tier ${i+1}`,
    usPriceUsd: usPrice,
    cheapestTop5: sorted.slice(0, 5).map(p => ({
      ...p, saveVsUS: usPrice ? Math.round((1 - p.priceUsd / usPrice) * 100) + '%' : 'N/A'
    }))
  };
});
```

### Cheapest Top N

```js
const asp = AppStorePriceAPI();
const sr = await asp.search('ChatGPT');
const app = sr.apps[0];
const all = await asp.prices(app.appStoreId);
const topN = all.sort((a, b) => a.priceUsd - b.priceUsd).slice(0, 10);
const usPrice = all.find(p => p.region === 'US')?.priceUsd;
return { appName: app.name, topN: topN.map(p => ({
  ...p, saveVsUS: usPrice ? Math.round((1 - p.priceUsd / usPrice) * 100) + '%' : 'N/A'
}))};
```

### Price in a Specific Region

```js
const asp = AppStorePriceAPI();
const sr = await asp.search('Notion');
const all = await asp.prices(sr.apps[0].appStoreId);
return all.find(p => p.region === 'TR'); // Replace the region code as needed.
```

## Result Display Guidelines

Use a Markdown table that includes: region (country flag emoji + name), currency, original price, USD equivalent, and CNY equivalent.
In comparison scenarios, indicate the discount versus the U.S. region: `savings = (1 - priceUsd / usPrice) * 100`.

## Troubleshooting

**Signature function not loaded**: Make sure you have navigated to an appstoreprice.org page and called `wait_for_dom_stable`.
`api.js` dynamically scans all webpack modules and locates the signing function by checking whether the function body contains the strings `X-Timestamp`/`X-Signature`. There is no need to hardcode the module ID.

**Signature function not found (major website redesign)**: If you receive "Signature function not found," the signature header key names may have changed.
Run the following command to check for new indicators:
```bash
minis-browser-use execute_js --script "
const define=(t,d)=>{for(const k in d) Object.defineProperty(t,k,{get:d[k],enumerable:true})};
const hits=[];
for(const [,m] of self.webpackChunk_N_E){
  if(!m) continue;
  for(const k of Object.keys(m)){
    try{
      const e={};m[k]({exports:e},e,{d:define});
      for(const fn of Object.values(e)){
        if(typeof fn!=='function') continue;
        const s=fn.toString();
        if(s.includes('X-') && s.length<800) hits.push({module:k,src:s.slice(0,200)});
      }
    }catch(e){}
  }
}
return hits.slice(0,5);
"
```
Based on the output, update the characteristic string detection conditions in `_getSignFn` in `api.js`.
