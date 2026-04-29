---
name: price-compare-fetch
description: Best-effort price comparison for a list of items across Amazon.com and Walmart.com using WebFetch (no browser MCP needed). Use when the user wants quick price-shopping but the richer price-compare skill is unavailable because the browser MCP can't reach retail domains (sandboxed/allowlisted environments). Takes a plain-text file of items (one per line). Results are advisory — Amazon and Walmart actively block headless fetches and often serve CAPTCHA/bot-check pages instead of prices, so some items will come back as "blocked". This skill is a fallback; prefer price-compare when browser MCP access to retail domains is available.
---

# price-compare-fetch

Best-effort price comparison across **Amazon.com** and **Walmart.com** using only `WebFetch`. Covers the two public-search sources that sometimes return usable HTML to headless requests; deliberately does NOT cover Amazon Fresh, Whole Foods, Walmart Groceries, Costco, or Safeway — those require a logged-in session that WebFetch cannot provide.

This skill exists as a fallback when the full `price-compare` skill can't run (e.g., the browser MCP's allowlist doesn't include retail domains). If browser MCP access is available, use `price-compare` instead — it covers 7 sources with reliable prices.

---

## When to use this vs. `price-compare`

| Situation | Use |
|---|---|
| Browser MCP can reach `amazon.com` / `walmart.com` / etc. | `price-compare` (7 sources, reliable) |
| Browser MCP exists but retail domains are blocked by allowlist | `price-compare-fetch` (this skill, 2 sources, best-effort) |
| No browser MCP at all; only WebFetch available | `price-compare-fetch` (this skill) |

If the user explicitly says "use price-compare-fetch" or "use the fetch skill", use this one regardless.

---

## Invocation

```
/price-compare-fetch <path-to-items.txt> [--sources amazon,walmart]
```

Natural language equivalents: "do a best-effort price check on this list using WebFetch", "fetch-compare prices for ~/shopping.txt".

**Flags:**
- `--sources <csv>` — limit the run. Accepted tokens: `amazon`, `walmart`. Default: both.

No ZIP, no login, no config file. There's nothing to set up — just run it.

---

## Honest expectations (lead with this in the output)

State this to the user at the **start** of the run, before any fetches:

> Best-effort price check — Amazon and Walmart both actively block headless HTTP requests, so some items will likely come back as "blocked" (I'll mark them). Prices that do come through are current but unverified — they may be sponsored placements, odd pack sizes, or third-party sellers. Treat this as a rough signal, not an apples-to-apples comparison. For reliable prices, use the full `price-compare` skill in an environment where the browser MCP can reach retail domains.

Don't bury this at the bottom of the run. The user should know going in that a 10-item list might return 6 prices and 14 "blocked" cells, and that's the skill working correctly.

---

## Phase 0 — Parse input

1. Read the input file. Strip blank lines and lines starting with `#`. Each remaining line is one query.
2. Resolve `--sources` flag (default `amazon,walmart`).
3. Announce what you're about to do: "Price-checking N items against <sources> via WebFetch. Expect some to be blocked."

## Phase 1 — Per-item fetch

Process items **one at a time, in input order**. For each item, for each enabled source:

### Amazon

- URL: `https://www.amazon.com/s?k=<URL_ENCODED_QUERY>`
- WebFetch prompt (pass exactly):
  > Extract up to 5 non-sponsored product listings from this Amazon search results page. For each, return the product name, price (in $X.XX format), and unit price if shown (e.g., "$0.24/oz"). Skip any result marked "Sponsored". If the page is a CAPTCHA, "Robot Check", "Enter the characters you see below", or otherwise does not contain product listings, respond exactly with: BLOCKED. Return nothing else in that case. Otherwise return a short markdown list, one line per product: `- Product Name — $X.XX (unit price)`.

### Walmart

- URL: `https://www.walmart.com/search?q=<URL_ENCODED_QUERY>`
- WebFetch prompt (pass exactly):
  > Extract up to 5 product listings from this Walmart search results page. For each, return the product name, price (in $X.XX format), and unit price if shown (e.g., "7.4 ¢/oz" or "$3.99/lb"). Skip results marked "Sponsored". If the page is a "Robot or human?" challenge, press-and-hold CAPTCHA, blocked page, or otherwise does not contain product listings, respond exactly with: BLOCKED. Return nothing else in that case. Otherwise return a short markdown list, one line per product: `- Product Name — $X.XX (unit price)`.

### Detecting "blocked"

If the WebFetch response:
- Is exactly `BLOCKED` (our agreed signal), OR
- Contains phrases like "Sorry!", "Robot Check", "enable cookies", "press and hold", "verify you are human", "to discuss automated access", OR
- Has zero recognizable `$X.XX` patterns in a substantive response,

…then treat this (item, source) as **blocked**. Record `"status": "blocked"` for that cell and move on. Do NOT retry automatically — the block is persistent per-IP for many minutes and retrying wastes the user's time.

### Picking one match per (item, source)

If the WebFetch response has product listings:
1. Take the list as-returned (the inner model already skipped sponsored per the prompt).
2. Apply a light outlier filter — drop any price more than 5× the median of the returned prices (kills obvious pack outliers).
3. Pick the first remaining entry. This is the match.
4. Record: product name, price, unit price (if present), status `"fetched"`.

If the response is ambiguous (e.g., empty list, garbled), record status `"no-results"` with the raw first 200 chars of the response in a `notes` field for debugging.

## Phase 2 — Output

Emit one markdown table per input item, sorted ascending by price. Rows with `blocked` or `no-results` show `—` in price columns and a status badge. Example:

```markdown
### Greek Yogurt Plain
| Source   | Matched product                           | Price  | Unit price    | Status    |
|----------|-------------------------------------------|--------|---------------|-----------|
| Walmart  | Great Value Plain Nonfat Greek Yogurt 32oz | $3.64 | 11.4 ¢/oz     | fetched   |
| Amazon   | —                                          | —     | —             | blocked   |
```

**Do NOT drop blocked rows** — showing them is the point. The user needs to know which cells are missing data vs. which are real prices.

After all per-item tables, emit a **run summary**:

```markdown
## Run summary
- Items processed: <N>
- Sources attempted: <list>
- Cells fetched: <count> / <total>
- Cells blocked: <count>
- Cells with no results: <count>

**Note:** Prices are WebFetch snapshots and may differ from what you see in a browser. For high-fidelity prices across 7 sources, use the `price-compare` skill in an environment with browser MCP access to retail domains.
```

---

## Failure modes and their handling

- **WebFetch returns a redirect notice** ("URL redirected to X"): follow it once — many retail sites redirect homepages to country-specific or cookie-consent pages. If the redirect target still doesn't return products, mark blocked.
- **WebFetch times out or errors**: mark as `blocked` with the error text in notes. Don't retry.
- **All items blocked on a given source**: in the run summary, say so explicitly ("Walmart blocked every request in this run — likely an IP-level block; try again later or use `price-compare`").
- **Response is suspiciously short (<100 chars of content)**: treat as `no-results` rather than guessing. Don't fabricate a price from thin content.

## Pacing

WebFetch has a 15-minute per-URL cache, so identical back-to-back fetches are fast but also identical — don't retry the same URL expecting different results. Between *distinct* fetches, no explicit sleep is needed; WebFetch's server adds its own latency.

## Out of scope

- Any source that requires login: Amazon Fresh, Whole Foods, Walmart Groceries, Costco, Safeway. If the user asks for these, redirect them to `price-compare` and explain why they can't work via WebFetch.
- Historical prices, alerts, coupons, Prime/member pricing, ZIP-scoped pricing.
- Mitigating bot-detection (proxies, header spoofing, sleeping-and-retrying) — that arms-race is out of scope and doesn't belong in a fallback skill.
