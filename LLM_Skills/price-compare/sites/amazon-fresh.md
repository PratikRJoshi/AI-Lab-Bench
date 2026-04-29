# Amazon Fresh — playbook

## Home URL
`https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo`

If that redirects to the generic homepage, Fresh is not enabled for the current ZIP — abort this source with a clear error ("Amazon Fresh not available for ZIP <zip>").

## Search URL pattern
`https://www.amazon.com/s?k=<QUERY>&i=amazonfresh`

## Login check
Same as amazon.com — the user must be signed in. If not, pause and direct them to sign in via the main amazon.com flow; the cookie carries across.

## ZIP / store handling
Fresh prices only render once a delivery address inside a Fresh coverage area is set on the account.

1. On first visit in a session, open the location widget:
   - a11y query: `button: Deliver to` or `link: Update location`.
2. Click, then enter the ZIP from config via `browser_type`.
3. Click "Apply". Wait for page reload.
4. Verify the Fresh storefront now renders (search for `text: Amazon Fresh` in the masthead).

If the location picker rejects the ZIP ("Sorry, this item can't be shipped to your selected location"), Fresh is not available for that ZIP — abort.

## Search flow
1. Navigate to search URL with `i=amazonfresh` filter.
2. Wait for results.
3. Read a11y tree with `query: "\\$[0-9]+\\.[0-9]{2}"`, `limit: 200`.

## Result parsing
Fresh results are simpler than main Amazon:
- **Title:** link text.
- **Price:** `$X.XX` — usually exactly one per card.
- **Unit price:** text like `"$0.29/oz"` right under the price.
- **Ratings:** often absent on Fresh; treat as `null` and do not filter.
- **URL:** title link href.

## Heuristic
1. No sponsored filter needed (Fresh has minimal sponsored content).
2. Apply the median-band price filter (0.2×–5×).
3. Pick the first remaining result (Fresh's own ranking is already relevance-tuned).

## Gotchas
- Some items show "Add to cart — price at checkout" with no visible price. Skip these; log as `—` for this source.
- "Prime-exclusive" pricing applies on Fresh; don't try to distinguish.
- Fresh has a minimum order for free delivery; this is irrelevant to per-item price comparison.
