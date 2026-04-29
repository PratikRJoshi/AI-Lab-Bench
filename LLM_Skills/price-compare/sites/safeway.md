# Safeway — playbook

Safeway is an Albertsons-family banner. Prices are heavily **loyalty-card-tiered** — most items show two numbers: a "For U member" / loyalty price and a regular price. We capture the **regular price** for comparison parity (Amazon Prime price and Whole Foods Prime price are excluded too). If the user is signed in with a For U account, optionally also capture the member price in a note.

## Home URL
`https://www.safeway.com/`

## Search URL pattern
`https://www.safeway.com/shop/search-results.html?q=<URL_ENCODED_QUERY>`

## Login / account
- Login is **optional** for browsing prices. A For U loyalty account will show lower member prices; without it, only regular prices are visible (which is what we want anyway).
- a11y query: `button: Sign In` (logged out) vs. `button: Account` / `text: Hi, <name>` (logged in).
- Don't force a sign-in during setup. Note the state for transparency only.

## ZIP / store handling
Safeway prices vary by store. A store selection is **required** before the site returns meaningful prices — without one, you'll see placeholder pricing or "not available" states.

1. Open the store/delivery chip in the header: `button: Your store` or the ZIP chip.
2. Enter the config ZIP → select the nearest Safeway.
3. Choose **Delivery** (or Pickup — both work; delivery has slightly broader price transparency). Be consistent across runs; prefer Delivery.
4. Verify the header shows the selected store name, e.g., "Safeway on <street>".

If no Safeway serves the ZIP, abort with "Safeway not available for ZIP <zip>".

## Search flow
1. Navigate to search URL.
2. Wait for results. Safeway's results are slow — give `browser_wait` 3–5s.
3. Read a11y tree with `query: "\\$[0-9]+\\.[0-9]{2}"`, `limit: 300`.

## Result parsing
Safeway cards have a characteristic dual-price layout:

- **Title:** product link text.
- **Regular price:** the larger, un-struck price — use this.
- **Member price:** often shown as "$X.XX with For U" or as a tag above the regular price. Record in a `notes` field but do not use as the primary price.
- **"Was $X.XX" / strikethrough:** a separate sale indicator, distinct from For U. If present, the displayed current price is already the sale price; use it as-is.
- **Unit price:** text like `"$0.19/oz"` or `"$2.99/lb"`.
- **"Sold by weight"** (produce, meat): same handling as Walmart Groceries — record `$/lb` as the unit price, note that the item is weight-based.
- **"Not Available" / "Unavailable"** badge: skip; log as `—`.
- **URL:** product-link href.

## Heuristic
1. No sponsored filter needed (Safeway's sponsored density is low).
2. Median-band filter [0.2×, 5×] on regular prices.
3. Pick the first remaining result.

## Gotchas
- **For U discount depth can be large** (30–50% off the regular price on rotating items). This makes Safeway look expensive compared to everyone else when using regular prices. The `notes` field with the member price lets the user see that, e.g., "Safeway regular $6.99, For U $3.99" — inform without skewing the primary comparison.
- **Delivery fee / basket minimum:** irrelevant to per-item price comparison.
- **Signature Select / O Organics** are Safeway's store brands — usually cheapest within Safeway, no special handling needed.
- **Same-site merging:** `safeway.com`, `albertsons.com`, `vons.com`, `jewelosco.com`, `acme-markets.com`, `randalls.com`, `tomthumb.com`, `pavilions.com`, `starmarket.com`, and `shaws.com` share the same Albertsons backend. If Safeway isn't available in your area but another banner is, that's a potential future extension — not in scope today.
- **Captcha:** Safeway occasionally throws a Cloudflare challenge. If `browser_a11y_tree` returns a nearly empty page with a "Just a moment..." text node, wait longer and retry once; if it persists, screenshot and abort.
