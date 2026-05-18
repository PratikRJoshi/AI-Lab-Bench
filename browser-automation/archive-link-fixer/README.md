# Archive.ph Link Fixer

Tampermonkey userscript that restores original URLs on archived pages. Without this, clicking any hyperlink inside an archive.ph article opens `archive.ph/o/<id>/<url>` — which triggers an infinite reCAPTCHA loop. This script rewrites those links back to their original destinations.

## Problem

When reading an archived article on `archive.ph`, all hyperlinks are proxied through archive.ph:

```
https://archive.ph/o/abc123/https://example.com/article
```

Clicking these opens a new tab that gets stuck in a reCAPTCHA loop because archive.ph tries to archive the linked page on the fly.

## Solution

The userscript runs on every archive.ph page and rewrites all proxied `<a>` tags back to their original URLs. Links open in a new tab pointing directly at the original domain.

## Setup (New Laptop)

### 1. Install Tampermonkey

Firefox: [Tampermonkey for Firefox](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)

Chrome: [Tampermonkey for Chrome](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)

### 2. Install the userscript

**Option A — From file:**
1. Open Tampermonkey → Dashboard → Utilities tab
2. Under "Import from file", select `archive-link-fixer.user.js` from this folder
3. Click Install

**Option B — Manual paste:**
1. Click the Tampermonkey icon → "Create a new script"
2. Delete the template content
3. Paste the contents of `archive-link-fixer.user.js`
4. Press `Ctrl+S` / `Cmd+S` to save

### 3. Verify

1. Open any archived page, e.g. `https://archive.ph/newest/https://www.nytimes.com`
2. Hover over a hyperlink inside the archived article
3. The browser status bar (bottom-left) should show the **original domain**, not `archive.ph/o/...`
4. Click — it should open the original site in a new tab without reCAPTCHA

## Supported Domains

The script runs on all known archive.ph mirror domains:
- `archive.ph`
- `archive.is`
- `archive.today`
- `archive.li`
- `archive.vn`
- `archive.md`
