# Walmart.com — playbook

Used for general Walmart marketplace search (not groceries).

## Home URL
`https://www.walmart.com/`

## Search URL pattern
`https://www.walmart.com/search?q=<URL_ENCODED_QUERY>`

## Login check
- a11y query: `button: Sign In` (logged out) vs. `button: Account` (logged in).
- Not strictly required for list prices on walmart.com, but signed-in session is needed so that the Walmart Groceries playbook (same domain, different storefront) works afterward.

## ZIP handling
Walmart shows different prices and different marketplace sellers per ZIP for some items, though the headline product price is usually constant. For consistency with the grocery playbook, set the ZIP via the store selector if not already set:

1. a11y query: `button: How do you want your items` or the "store" chip in the header.
2. Click → "Deliver to ZIP" → type the config ZIP → confirm.
3. Wait for reload.

## Search flow
1. Navigate to the search URL.
2. Wait for `main` to populate.
3. Read a11y tree with `query: "\\$[0-9]+\\.[0-9]{2}"`, `limit: 300`.

## Result parsing
Walmart result cards are simpler than Amazon:
- **Title:** link in the result heading.
- **Price:** the `text` right under the title; usually exactly one `$X.XX`.
- **Unit price:** text like `"7.4 ¢/oz"` — Walmart uses ¢/oz notation for cheap-per-unit items and `$X.XX/lb` for produce.
- **Sponsored flag:** look for `text: Sponsored`. Skip.
- **Rating:** `text: <N> out of 5 Stars, (<count> reviews)`. Optional.
- **URL:** title link href.
- **"Shipping, arrives in X days" vs. "Pickup today":** informational only; don't filter on it.

## Heuristic
1. Drop sponsored.
2. Drop results outside [0.2× median, 5× median].
3. Prefer "Sold & shipped by Walmart" over third-party marketplace sellers if that distinction is visible; otherwise pick the first remaining.

## Gotchas
- Walmart's search sometimes surfaces pickup-only items with no delivery price shown. Treat that as a normal price match; pickup vs. delivery is out of scope.
- Third-party sellers on Walmart can have inflated prices for in-demand items. The median-band filter catches the worst; confirmation step covers the rest.
- "Was $X.XX" strikethroughs are common — always use the current price.
