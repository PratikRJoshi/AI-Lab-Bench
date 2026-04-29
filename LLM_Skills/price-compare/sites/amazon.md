# Amazon.com — playbook

Used for general Amazon marketplace search (not Fresh or Whole Foods).

## Home URL
`https://www.amazon.com/`

## Search URL pattern
`https://www.amazon.com/s?k=<URL_ENCODED_QUERY>`

## Login check
- a11y query: `link: Hello, Sign in` (logged out) vs. `link: Hello, <Name>` or `button: Account & Lists` (logged in).
- Amazon.com search works without login, but staying logged in is required so that subsequent navigation to Fresh/WF in the same session carries the delivery address.

## ZIP handling
Not needed for amazon.com list prices. ZIP only changes tax / shipping estimate, not the sticker price on the search results page.

## Search flow
1. Navigate to search URL with the query.
2. Wait for `main` region to populate (`browser_wait` on `role: main`).
3. Read a11y tree with:
   - `preset: content`
   - `query: "\\$[0-9]+\\.[0-9]{2}"`
   - `limit: 300`

## Result parsing
Each organic result is a listitem in `main`. For each listitem:
- **Sponsored flag:** presence of `text: Sponsored` as a descendant — skip.
- **Title:** the `link` inside the heading.
- **Price:** first `text` matching `\\$\\d+\\.\\d{2}`. If a "List:" price is also present, prefer the current/sale price (the bolder, un-struck one).
- **Unit price:** a `text` node like `"($0.24/Ounce)"` — capture the parenthesized portion.
- **Rating:** text like `"4.5 out of 5 stars"`. If missing, treat as `null` (do NOT filter out — many grocery items on amazon.com lack ratings).
- **URL:** the href of the title link.

## Heuristic
1. Drop sponsored.
2. Drop results whose price is outside [0.2× median, 5× median] of the page's prices (kills pack outliers).
3. Of the remaining, pick the one with the highest rating ≥ 4.0; if none rated, pick the first remaining.

## Gotchas
- "Overall Pick" / "Amazon's Choice" badges are fine — don't filter on them.
- Subscribe & Save prices appear in smaller text next to the main price. Use the larger price (list / current), not the S&S price.
- Pack sizes in titles ("Pack of 6", "12-count") inflate price. The median-band filter catches most of these; if you still get an obvious pack match, note it and let the confirmation step correct it.
