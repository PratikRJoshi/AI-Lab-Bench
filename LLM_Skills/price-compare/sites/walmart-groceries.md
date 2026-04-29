# Walmart Groceries — playbook

Walmart groceries live under `walmart.com/grocery` and require a store selection (one specific Walmart Supercenter's inventory).

## Home URL
`https://www.walmart.com/grocery`

## Search URL pattern
`https://www.walmart.com/search?q=<QUERY>&typeahead=<QUERY>&affinityOverride=store_led`

The `affinityOverride=store_led` parameter scopes the search to the selected store's grocery inventory.

## Login check
Same as walmart.com.

## Store selection
This is the critical difference from walmart.com. Grocery prices vary by store, and the search won't return grocery results without a store chosen.

1. Open the store/delivery chip in the header: `button: How do you want your items` or `button: Pickup or delivery`.
2. Choose **Pickup** (most reliable — delivery coverage is narrower and sometimes shows a different item subset).
3. Enter ZIP → select nearest Walmart Supercenter.
4. Confirm: the chip should now show "Pickup from <store name>".

If no grocery-capable store is found for the ZIP (some rural areas have only neighborhood markets with no pickup), abort with "Walmart Groceries not available for ZIP <zip>".

## Search flow
1. Navigate to search URL.
2. Wait for results. Grocery results have a distinct card layout with a small store badge.
3. Read a11y tree with `query: "\\$[0-9]+\\.[0-9]{2}"`, `limit: 200`.

## Result parsing
- **Title:** result link.
- **Price:** card's main `$X.XX`.
- **Unit price:** `"¢/oz"` or `"$/lb"` text under price.
- **"Sold by weight" items:** (produce, meat) show a price-per-lb; the skill should record both the `$/lb` and, if the typical unit is listed ("about 1 lb"), derive an approximate item price.
- **"Out of stock" badge:** skip; log as `—`.
- **URL:** title link href.

## Heuristic
1. Median-band filter [0.2×, 5×].
2. Prefer "Great Value" (Walmart store brand) only if the user's query mentioned it; otherwise pick the first remaining.

## Gotchas
- Walmart sometimes returns non-grocery results inside a grocery search (e.g., searching "knife" gives kitchen knives). Filter these out by checking for the grocery store badge on the card. If the card lacks a store badge or shows "Ships from warehouse", it's not the grocery channel — skip.
- Pickup vs. Delivery can swap prices for a handful of items. Staying on Pickup throughout the run keeps comparisons consistent.
- Walmart Groceries occasionally shows a "was $X, now $Y" — always use the current (Y).
