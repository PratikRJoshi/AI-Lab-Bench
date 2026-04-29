# price-compare — First-run setup

Run these steps the first time the skill is invoked (detected by the absence of `~/.claude/skills/price-compare/config.json`).

## Why this exists

The browser MCP runs its own Chrome profile — not the user's everyday browser — so it has no cookies for Amazon / Walmart / Costco. Several sources won't show prices without a logged-in, ZIP-coded session:
- **Amazon Fresh, Whole Foods, Walmart Groceries, Safeway** need a delivery ZIP / store selection to show real prices.
- **Costco** hides all prices behind a membership login wall ("Sign In For Price").

One-time setup establishes:

1. Browser MCP allowlist permission to visit amazon.com / walmart.com / costco.com / safeway.com.
2. Logged-in sessions at amazon.com, walmart.com, and costco.com. (Safeway login is optional.)
3. A delivery ZIP on file that has coverage for Fresh / Whole Foods / Walmart Groceries / Safeway.

Once `config.json` exists, none of this runs again unless the user forces re-setup or a session expires.

---

## Step 1 — Browser MCP allowlist

The browser MCP blocks navigation to domains not in its allowlist. Ask the user to verify that these three entries are in their allowlist config (the file the browser MCP documents in its own setup — typically `allowed-urls.json` in the browser plugin's data directory):

```
amazon.com
walmart.com
wholefoodsmarket.com
costco.com
safeway.com
```

If unsure where the allowlist lives, run:

```bash
mcp__plugin_browser_browser__browser_navigate url=https://www.amazon.com/
```

If it errors with an allowlist message, the user needs to add the domains. Provide the exact error text so they can act on it. Do not try to auto-edit allowlist files — the browser MCP manages this itself.

## Step 2 — Log in to Amazon

1. Navigate: `mcp__plugin_browser_browser__browser_navigate url=https://www.amazon.com/`
2. Read a11y tree, `query: "Sign in"`. If `link: Hello, Sign in` appears, the user is logged out.
3. Tell the user: *"I've opened amazon.com in the MCP browser. Please sign in there, then tell me 'done'."*
4. After they confirm, re-read the a11y tree and verify `link: Hello, <name>` or `button: Account & Lists` appears. If still signed out, loop.

## Step 3 — Log in to Walmart

Same pattern:
1. Navigate to `https://www.walmart.com/`.
2. Query for `button: Sign In`. If present, ask the user to sign in.
3. Verify by querying for `button: Account`.

## Step 4 — Log in to Costco (required for Costco prices)

Costco hides prices behind a member login. Without it, every result shows "Sign In For Price".

1. Navigate to `https://www.costco.com/`.
2. Query for `link: Sign In`. If present, ask the user to sign in with their membership account.
3. Verify by querying for `link: Hi, <name>` or `link: Account`.
4. Also do a smoke check: navigate to `https://www.costco.com/CatalogSearch?keyword=milk` and scan the first result card for `text: Sign In For Price`. If that text appears, the session didn't fully authenticate — ask the user to try again.
5. If the user does not have a Costco membership or declines to sign in, record `"costco"` as **disabled** in `sources_enabled` (step 6) and move on. Do not pretend Costco works without login.

## Step 5 — Collect default ZIP

Use AskUserQuestion:
- "What ZIP code should I use for delivery / pickup? This determines which Fresh, Whole Foods, and Walmart store inventories are visible."

Record the answer.

## Step 6 — Verify grocery coverage

For each location-gated channel, do a probe navigation:

- **Amazon Fresh:** navigate to the Fresh storefront URL. Set the delivery address to the user's ZIP using the location widget (see `sites/amazon-fresh.md`). If the storefront renders, Fresh is available. If not, note it.
- **Whole Foods:** same pattern, WF storefront.
- **Walmart Groceries:** navigate to `walmart.com/grocery`, open the Pickup/Delivery chip, enter ZIP, select a Supercenter. Capture the store number. If no eligible store is found, note it.
- **Safeway:** navigate to `https://www.safeway.com/`, open the store/delivery chip, enter ZIP, select nearest Safeway. Capture the store name/number. If no Safeway serves the ZIP, note it — a sibling Albertsons banner (Vons, Jewel-Osco, Acme, etc.) may serve the area but is out of scope for this skill.

Tell the user the coverage result, e.g.:
> "Setup check: Amazon Fresh ✅, Whole Foods ✅, Walmart Groceries ✅ (Walmart Supercenter #2031), Safeway ✅ (Safeway on Market St). Amazon.com, Walmart.com, and Costco always work (Costco needs login, confirmed in step 4)."

If a channel has no coverage, the skill will skip it on every run and the user can add it to `sources_enabled` later if they move.

## Step 7 — Write config.json

Write `~/.claude/skills/price-compare/config.json`:

```json
{
  "default_zip": "<ZIP the user gave>",
  "sources_enabled": ["amazon", "amazon-fresh", "whole-foods", "walmart", "walmart-groceries", "costco", "safeway"],
  "walmart_store_id": "<store number detected in step 6, or null>",
  "safeway_store_id": "<store name/number detected in step 6, or null>",
  "heuristic": {
    "skip_sponsored": true,
    "min_rating": 4.0,
    "price_outlier_band": [0.2, 5.0]
  },
  "setup_completed_at": "<ISO-8601 timestamp>"
}
```

Omit any channel from `sources_enabled` that failed login (Costco) or the coverage check (Fresh / WF / Walmart Groceries / Safeway).

## Step 8 — Confirm and continue

Tell the user setup is done and that the skill is now running the actual price comparison they requested. Proceed with the normal workflow in SKILL.md.

---

## Re-running setup

The user can force re-setup by deleting `config.json` or asking the skill to "reset price-compare setup". The skill should also detect session expiry (login check fails mid-run) and trigger a partial re-login without a full re-setup.
