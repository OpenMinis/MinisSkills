---
name: xianyu-hub
description: >
  Xianyu (Goofish) secondhand item search and lookup skill. Supports searching for items, checking price trends,
  filtering by city, price range, and sort order, viewing item details, managing favorites, and checking orders and listed items.
  Supports outputting web links and fleamarket:// direct links to the app.
  Built-in "Keyword Enhancement": When search results are empty or very limited, the skill automatically adds alternative keywords from the same category and retries the search,
  significantly improving the search hit rate.
  This skill must be triggered whenever a user mentions "Xianyu," "Xianyu," "secondhand," "goofish," "search how much xx costs," "find xx items,"
  "can't find it," or in any scenario where they need to check Xianyu item prices or search for secondhand items.
---

# Xianyu Search Skill (xianyu-hub)

## Core Principle

In a browser tab where the user is already logged in to Xianyu, call Xianyu's internal API through `minis-browser-use execute_js`.
The user must first log in to Xianyu in the built-in browser.

## Startup Process (run before each use)

All scripts **automatically call `ensure_tab.sh`** to complete the following steps, so there is **no need to manually pass `--tab-id`**.

### ensure_tab.sh Automatic Processing Logic

1. **Scan all tabs** - Parse the `list_tabs` text and look for a tab containing `goofish.com`
2. **Check login state** - Execute JS to determine whether the current page is logged in
3. **Logged in** -> Directly output `tab_id`, and the script continues
4. **Not logged in** -> Automatically execute:
   - `navigate` to the Xianyu home page
   - `minis-open` to open the built-in browser for the user to log in
   - **Poll the login state every 5 seconds, for up to 120 seconds**; after login succeeds, automatically continue

> To manually specify a tab, pass `--tab-id <id>`; the script will still verify the login state.

## Script Overview

All scripts are located in `/var/minis/skills/xianyu-hub/scripts/` and are run with `sh`.

### 1. Search Items - search.sh

```sh
sh scripts/search.sh -k <keyword> [options]

# Options:
#   -k <term>        Keyword (required)
#   -n <number>      Number per page (default 20, maximum 30)
#   -p <page>        Page number (default 1)
#   -s <sort>        default | price_asc | price_desc | time | reduce
#   --min-price <yuan>  Minimum price
#   --max-price <yuan>  Maximum price
#   --city <city>       City filter
#   --personal-only     Personal idle items only
#   -j              Output JSON

# Examples
sh scripts/search.sh -k "MacBook Air" -s price_asc --min-price 2000 -n 10
sh scripts/search.sh -k "iPhone15" --city Shanghai -s time
```

### 2. Item Details - detail.sh

```sh
sh scripts/detail.sh <itemID>

# Returns: title, price, description, views/wants/favorites count, seller information (positive feedback rate, response rate, number sold)
```

### 3. Favorites Management - favorites.sh

```sh
sh scripts/favorites.sh list [-n quantity] [-p page]   # View favorites list
sh scripts/favorites.sh add <itemID>                   # Add item to favorites
sh scripts/favorites.sh remove <itemID>                # Remove item from favorites
```

### 4. Order Lookup - orders.sh

```sh
sh scripts/orders.sh [-n quantity] [-p page] [-t type]

# Type: all | wait_pay | wait_send | wait_receive | refund
```

### 5. My Listed Items - my_items.sh

```sh
sh scripts/my_items.sh [-n quantity] [-p page]
```

---

## 🔎 Keyword Enhancement Module

> When direct search results are empty or very few (< 3 results), **automatically enable keyword enhancement**; do not give up right away.

### Core Mechanism

Some items on the platform are described with different terms, and sellers often use common industry abbreviations, alternative names, or shortened forms.
This module uses the open API from [SearchSharp.com](https://search-sharp.com)
to automatically retrieve a list of commonly used aliases for the item across all platforms (crowdsourced by the user community and sorted by popularity),
then retries the search with each one to improve the hit rate.

### 6. Smart Keyword Search - smart_search.sh ⭐ Recommended

**Preferred when results are insufficient. Automatically completes: direct search -> add aliases -> retry**

```sh
sh scripts/smart_search.sh -k <keyword> [other search.sh parameters]

# Examples
sh scripts/smart_search.sh -k "GTA"
sh scripts/smart_search.sh -k "Netflix membership" --max-price 50
sh scripts/smart_search.sh -k "gpt plus"
```

**Execution flow:**
1. Search Xianyu once with the original keyword
2. If there are fewer than 3 results, call the SearchSharp API to look up common aliases for the term
3. Sort by community popularity and retry the search with each alias one by one (up to 3)
4. Output all results

### 7. Alias Lookup - alt_keywords.sh

**Only queries keyword aliases and does not search Xianyu. Used to understand common names for a specific item**

```sh
# Look up common aliases for a term
sh scripts/alt_keywords.sh -q <keyword>

# List popular item alias summaries (about 20 entries)
sh scripts/alt_keywords.sh --list

# Look up all aliases for an item (using an ID found in the --list results)
sh scripts/alt_keywords.sh --id <itemID>

# JSON output
sh scripts/alt_keywords.sh -q "gpt" -j
```

### Usage Rules

| Situation | Action |
|------|------|
| 3 or more search results | Display directly; no enhancement required |
| Fewer than 3 search results | Automatically run `smart_search.sh` to add aliases and retry |

### SearchSharp API

| Endpoint | Description |
|------|------|
| `GET /api/products` | Popular item list |
| `GET /api/products?q=<term>` | Look up items and aliases by keyword |
| `GET /api/products/<id>` | Complete alias list for a single item |

- No authentication required; call directly with `curl`
- The `keywords` array is sorted by net community votes; the higher the popularity, the higher the ranking

---

## Open Item

```sh
apple-open "fleamarket://item?id=<itemID>"    # Open in the Xianyu app
```

Use this Markdown link in conversations: `[Open in the Xianyu app](fleamarket://item?id=xxx)`

## URL Rules

| Purpose | Format |
|---|---|
| Web page | `https://www.goofish.com/item?id=<id>` |
| APP | `fleamarket://item?id=<id>` |
| Order | `fleamarket://order_detail?id=<orderId>` |

## Notes

- The `price_asc` sort may return low-quality low-price data from the server; use it together with `--min-price` filtering
- City and price range filters are applied on the client side
- `--personal-only` is determined by review count (>10 reviews is treated as a store), so it is not perfectly accurate
- It is normal for searches to return empty results when sensitive terms are blocked by the platform
- `ensure_tab.sh` depends on the text format returned by `list_tabs` (`Tab N: Title — URL`); if the format changes, the parsing logic must be updated accordingly
- When not logged in, `ensure_tab.sh` automatically polls and waits; **no manual login confirmation is required**. The script blocks during the wait (up to 120 seconds)
