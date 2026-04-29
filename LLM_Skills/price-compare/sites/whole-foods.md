# Whole Foods Market — playbook

Whole Foods prices on amazon.com are shown through the "Whole Foods Market" storefront, scoped to a delivery address with WF coverage.

## Home URL
`https://www.amazon.com/alm/storefront?almBrandId=VUZHIFdob2xlIEZvb2Rz`

If that redirects to the generic homepage, Whole Foods delivery/pickup is not enabled for the current ZIP — abort this source.

## Search URL pattern
`https://www.amazon.com/s?k=<QUERY>&i=wholefoods`

## Login check
Same as amazon.com; user must be signed in.

## ZIP / store handling
Whole Foods prices only render with a delivery address inside a WF coverage area set on the account.

1. On first visit in a session, open the location widget: `button: Deliver to` or `link: Update location`.
2. Enter ZIP from config; select "Whole Foods Market" as the pickup/delivery store if prompted.
3. Verify WF storefront renders — `text: Whole Foods Market` in the masthead.

If the ZIP has no WF store, abort with "Whole Foods not available for ZIP <zip>".

## Search flow
Same mechanics as Fresh — `i=wholefoods` filter on the Amazon search.

## Result parsing
- **Title:** result link text.
- **Price:** `$X.XX`. Some WF items are sold by weight ("$3.99/lb") — capture that as the unit price and estimate the per-unit price accordingly.
- **Sale / Prime member price:** WF often shows two prices side-by-side, e.g., "Prime member: $3.99, Regular: $4.49". Record the **regular** price, not the Prime price, for apples-to-apples comparison across sources. (Optional future: show both.)
- **Unit price:** e.g., "$0.31/oz".
- **URL:** title link href.

## Heuristic
Same as Fresh:
1. Median-band filter.
2. Pick the first remaining result.

## Gotchas
- WF produce is often priced per pound with no fixed quantity — the "price" you extract is `$/lb` not a unit price. Flag in the matched product name so the confirmation step is honest.
- WF 365-brand items are usually cheapest within the WF storefront — don't bias toward them unless the user's query mentioned "365".
- Some WF items have "In-store only" badges (no delivery). Skip these; log as `—`.
