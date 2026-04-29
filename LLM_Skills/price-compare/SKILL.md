---
name: price-compare
description: Compare prices for a list of grocery or household items across Amazon.com, Walmart.com, Amazon Fresh, Whole Foods, Walmart Groceries, Costco, and Safeway, returning each item's prices sorted cheapest-to-most-expensive plus a total-basket summary per source. Use whenever the user wants to compare, shop around, or find the cheapest place to buy a list of items — even when they don't say "compare prices" explicitly (e.g., "where's the best place to buy this list", "price check these", "run my shopping list against the usual stores"). Takes a plain-text file of items (one per line). Requires the browser MCP; uses logged-in Amazon, Walmart, and Costco sessions and a configured delivery ZIP.
---

# price-compare

Compare prices for items in a plain-text file across 7 sources: Amazon.com, Amazon Fresh, Whole Foods, Walmart.com, Walmart Groceries, Costco, and Safeway. Output: markdown tables per item sorted ascending by price, plus a basket-total summary.

---

## Invocation

Explicit:
```
/price-compare <path-to-items.txt> [--fast] [--zip 94105] [--sources amazon,walmart,fresh,wf,walmart-grocery,costco,safeway]
```

Natural language equivalents also trigger the skill: "compare prices for the list in ~/shopping.txt", "price check these items", "where's the cheapest place to buy this list".

**Flags**
- `--fast` — skip the per-item confirmation step; use the skill's heuristic pick without asking.
- `--zip <5-digit>` — override the config default ZIP for this run only.
- `--sources <csv>` — limit to a subset. Accepted tokens: `amazon`, `amazon-fresh` (or `fresh`), `whole-foods` (or `wf`), `walmart`, `walmart-groceries` (or `walmart-grocery`), `costco`, `safeway`.

---

## Phase 0 — Preflight

1. **Read config.** Load `~/.claude/skills/price-compare/config.json`. If it doesn't exist, follow `first-run-setup.md` end-to-end, then continue. Do not proceed with price comparison until config is written — the skill cannot function without a ZIP and login state.
2. **Parse input file.** Read the file the user pointed at. Strip blank lines and any line starting with `#`. Each remaining line is one query string. Preserve order (the output groups by input order).
3. **Resolve ZIP.** CLI `--zip` overrides `default_zip` from config.
4. **Resolve source list.** CLI `--sources` overrides `sources_enabled` from config. Intersect with config's enabled list — never query a source the user disabled during setup.
5. **Sanity report.** Briefly tell the user: "Comparing N items across M sources using ZIP <zip>. This takes roughly 20–40 seconds per item in total (sequential across sources)."

## Phase 1 — Per-site search

Process sources **one at a time** in this order: `amazon`, `amazon-fresh`, `whole-foods`, `walmart`, `walmart-groceries`, `costco`, `safeway`. This order matters because login cookies and ZIP state cascade: setting up Amazon session once covers Fresh and WF; setting up Walmart once covers Walmart Groceries. Costco and Safeway are independent sessions and run last, so their setup cost doesn't block the Amazon/Walmart families if the user has partial login state.

For each source in the resolved list:

1. **Load the playbook** from `sites/<source>.md`. Each playbook is the authoritative reference for that site's URLs, login checks, ZIP flow, search flow, and result-parsing rules. Read it fully before starting that source.

2. **Check login state.** Use the login-check described in the playbook. If logged out, pause and ask the user to sign in (they'll do it in the MCP browser, tell you "done"), then re-verify. If the user can't or won't log in, skip that source and note it in the output.

3. **Set ZIP / store** per the playbook (grocery channels need this; main sites don't for list prices).

4. **Search each item in the input list.** For each query:
   - Navigate to the playbook's search URL with the query URL-encoded.
   - Read a11y tree focused on the results region, with `query: "\\$[0-9]+\\.[0-9]{2}"` and a high `limit` (200–300).
   - Apply the playbook's result-parsing rules to extract candidates: title, price, unit price (if present), rating (if present), URL.
   - Apply the **heuristic** (see below) to pick one match. Record: source, matched_product, price, unit_price, url. If no match is found (no results, all filtered out, or out-of-stock), record `null` for that (item, source).

5. **Pace the run.** Sleep ~1s between item searches on the same site (`browser_wait`). This both respects rate limits and makes the whole run legible if the user is watching.

## Heuristic — picking one match per (item, source)

The goal is an apples-to-apples price. The common failure mode is grabbing a multi-pack when the user wanted a single unit, or a sponsored result with inflated pricing. Apply these in order:

1. **Drop sponsored results** (per playbook — each site marks them differently).
2. **Compute the median price** of all visible non-sponsored results on the search results page.
3. **Drop results outside [0.2× median, 5× median].** This band catches pack/bulk outliers and single-serving outliers. The exact band is in config (`heuristic.price_outlier_band`).
4. **Rating filter** (optional, site-dependent): drop results rated below `min_rating` (default 4.0), BUT only if a rating is present. Many grocery items have no rating — don't filter them out for being unrated.
5. From what remains, **pick the first one in result order.** The site's own ranking is usually fine once we've excluded outliers and sponsored content.

If the filter drops everything, fall back to the first non-sponsored result. Record this case so the confirmation step can catch it.

## Phase 2 — Confirmation (skipped with `--fast`)

Show the user a compact preview of matches — one table per item with the chosen product and price per source. Ask via AskUserQuestion: *"Anything look off? I can re-run specific (item, source) pairs."*

If the user flags a mismatch, re-search that pair with either (a) a refined query they provide or (b) the user's pick from the top-5 candidates on that site's results page. Update the stored match.

## Phase 3 — Output

For each input item, in input order, emit a level-3 heading and a markdown table **sorted ascending by price**:

```markdown
### <original input line>
| Source            | Matched product              | Price  | Unit price |
|-------------------|------------------------------|--------|------------|
| <cheapest source> | <full product name>          | $X.XX  | $X.XX/unit |
| ...               | ...                          | ...    | ...        |
```

Rows where no match was found show `—` in price and matched product, and the source is still listed so missing coverage is visible. Put unmatched rows at the bottom of the per-item table.

After all per-item tables, emit a **basket summary**:

```markdown
## Basket totals
For each source, summing the matched price per item (unmatched items skipped):

| Source            | Items matched | Basket total |
|-------------------|---------------|--------------|
| <source>          | N / total     | $X.XX        |
| ...               | ...           | ...          |
```

Then a one-line verdict:
> **Cheapest basket: <source> at $X.XX (N of M items matched).** Best per-item picks are in the tables above.

## Output format notes

- Prices always formatted as `$X.XX` (two decimals).
- Unit prices preserve the source's native unit (`$/oz`, `¢/oz`, `$/lb`) rather than normalizing, because normalization introduces errors (e.g., per-fluid-oz vs. per-weight-oz for liquids). If the user wants normalized unit prices, they can ask in a follow-up.
- Product names are truncated at 60 chars with an ellipsis only if they break table rendering.
- All product URLs are captured internally (for follow-up questions) but **not** included in the output table by default — they bloat the table and most rows don't need them. If the user asks "where can I click through?", emit URLs on demand.

---

## Error handling

- **Allowlist missing a domain:** the first `browser_navigate` will fail. Report the exact error and direct the user to add the domain to the browser MCP allowlist. Don't try to auto-fix.
- **Session expired mid-run:** if the login-check fails after having passed Phase 0, pause, ask the user to re-log in, and resume from the item the skill was on (don't start over).
- **ZIP not served:** if a grocery channel rejects the ZIP, disable that channel for this run and note it in the output summary (`<source> — not available for ZIP <zip>`). Don't propagate this to config unless the user asks.
- **No results for an item:** record `null` for that (item, source) and continue. Don't retry with a different query unless the user asks.
- **Site layout changed (a11y tree has no price nodes in results region):** take a `browser_screenshot`, save to `/tmp/price-compare-<source>-<timestamp>.png`, report the path, and skip remaining items for that source. This is the most likely cause of a silent run producing garbage, so fail loud.

---

## Files and where to look

- `sites/amazon.md`, `sites/amazon-fresh.md`, `sites/whole-foods.md`, `sites/walmart.md`, `sites/walmart-groceries.md`, `sites/costco.md`, `sites/safeway.md` — per-site playbooks. Read the relevant one at the start of its source's phase.
- `first-run-setup.md` — runs once, when `config.json` is missing.
- `config.json` — user config. Created by first-run setup; safe to hand-edit after.
- `examples/items.txt` — sample input; 3 staples for smoke testing.

---

## Out of scope

The skill deliberately does not: track price history, set price-drop alerts, build carts, handle coupons / Subscribe-and-Save / Prime-member prices (list prices only), normalize unit prices across dissimilar units, or support non-US locales. Ask the user to clarify if their request implies any of these.
