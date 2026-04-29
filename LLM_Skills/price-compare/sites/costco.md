# Costco — playbook

Covers **costco.com**, the signed-in member online store. Not Costco Business Delivery, not Costco Same-Day via Instacart, and not in-warehouse pricing (which isn't available online).

## Home URL
`https://www.costco.com/`

## Search URL pattern
`https://www.costco.com/CatalogSearch?keyword=<URL_ENCODED_QUERY>`

## Login check — critical
Costco hides prices behind a membership paywall. Many search result cards show just a "Sign In For Price" button instead of a number. **The login check is mandatory**, not a nice-to-have, and must pass before trusting any prices on the results page.

- a11y query: `link: Sign In` (logged out) vs. `link: Hi, <Name>` or `link: Account` (logged in).
- Additionally, scan the first 3 result cards for `text: Sign In For Price`. If that appears even when `Hi, <Name>` is present, the session is a "browse-only" visitor session — ask the user to explicitly sign in via the account menu.
- If login cannot be established, **skip Costco for this run and mark all its rows `—`**. Do not guess at prices.

## ZIP handling
Costco.com online prices are generally constant across ZIPs (unlike in-warehouse prices, which vary). However, some items are "not available in your area" if the member's primary shipping address doesn't support them.

1. The member's shipping ZIP is stored on the account; there's no per-session ZIP picker on costco.com.
2. If the config ZIP differs from the member's account ZIP, do **not** try to change the account ZIP — just proceed and accept that a handful of items may show as "not available in your area". Log those as `—`.
3. No ZIP setup step is needed at the start of the Costco phase.

## Search flow
1. Navigate to the search URL.
2. Wait for the `main` region. Costco's results take 2–4 seconds to render — use `browser_wait` generously.
3. Read a11y tree with `query: "\\$[0-9]+\\.[0-9]{2}"`, `limit: 250`.

## Result parsing
Costco result cards:
- **Title:** the product-link text.
- **Price:** main `$X.XX`. Costco often shows a "Your Price: $X.XX" — use that.
- **"Less $X.XX Instant Savings" / "-$X.XX":** Costco frequently has a promotional deduction. The final price shown already reflects this; don't subtract again, but **capture the promo in the matched_product field** (e.g., `"Kirkland Organic Bananas (after $2 Instant Savings)"`) so the confirmation step can see the caveat.
- **Unit price:** text like `"$0.45/oz"` — often absent; capture when present.
- **Shipping cost badge** ("+$X shipping"): Costco charges shipping on many items. Record the base item price; do NOT fold shipping into the price, since other sources don't either.
- **"Sign In For Price":** this row means login state is broken; abort (see login check above).
- **"Out of stock online":** skip; log as `—`.
- **URL:** product-link href.

## Heuristic
1. Drop any row whose price is "Sign In For Price" (should be none if login worked; defensive).
2. Drop rows outside [0.2× median, 5× median] of visible prices.
3. Costco items are often sold **only** in warehouse-pack sizes (24-pack of granola bars, 2-lb bag of spinach). These ARE the real Costco offering — don't try to filter them out as "pack outliers". The median-band filter should keep them because most Costco results on a given search are similarly bulk-sized.
4. Pick the first remaining result in Costco's native ranking.

## Gotchas
- **Pack-size dominance:** Costco prices look inflated next to Amazon/Walmart because the unit is bulk. Flag in matched_product (e.g., `"Kirkland Almond Milk, 6-pack × 32 fl oz"`) so the user can judge the per-unit math themselves. This is a feature of Costco's business model, not a scraping bug.
- **Kirkland-brand bias:** Kirkland is Costco's private label and is usually cheapest within Costco. If the first post-filter result is Kirkland, that's expected — don't try to "balance" by picking a name brand instead.
- **Member-tier differences:** Executive Member 2% rewards aren't reflected in list price; we ignore them for comparison purposes (same as Amazon Prime).
- **Search relevance is noisy** on costco.com — searching "milk" can return dairy-free products, chocolate milk, and shelf-stable milk in the same page. The confirmation step is especially important for Costco; don't use `--fast` alone for Costco-heavy runs without spot-checking.
- **"Delivery not available to your address":** a full-page takeover after clicking a product. If the skill needs the product page (it shouldn't — all info should be on the search page), bail out of that product.
