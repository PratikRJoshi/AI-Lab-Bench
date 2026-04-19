# Chase Offers Auto-Clicker

Automatically activates all unclicked Chase Offers on your account using Playwright + Firefox. Run it once before each statement period to claim every available cash-back offer without manually clicking through hundreds of cards.

## How it works

1. Launches Firefox Nightly using a dedicated `chase-automation` profile (so Chase doesn't flag the browser as a bot)
2. Pauses and waits for you to log in manually and navigate to the Chase Offers page
3. Probes the page for "add" buttons using multiple CSS selectors, with a recursive shadow-DOM walker as fallback (Chase's offer cards are built with deeply nested Web Components)
4. Clicks each unactivated offer using `dispatch_event('click')` — works even when the browser window is minimized or behind other windows
5. Handles back-navigation via the `mds-navigation-bar` shadow-DOM back button, with `page.go_back()` as fallback
6. Prints a running count and a final summary

## Setup (one-time)

### 1. Python environment

```bash
cd browser-automation/chase-offers-clicker
python3 -m venv chase-offers-env
source chase-offers-env/bin/activate
pip install playwright
playwright install firefox
```

### 2. Dedicated Firefox profile

Create a profile directory that the script uses exclusively. This keeps your main Firefox untouched and lets both run at the same time:

```bash
mkdir -p ~/Library/Application\ Support/Firefox/Profiles/chase-automation
```

On the **first run**, log in to Chase manually in the Playwright window to seed the profile with your session cookies. Subsequent runs will reuse those cookies and may not require login at all.

## Usage

```bash
~/Documents/Learning/run_chase_offers.sh
```

Or, if running directly from the repo directory:

```bash
source chase-offers-env/bin/activate
python3 chase_offers_clicker.py
```

The `run_chase_offers.sh` wrapper handles activating and deactivating the virtual environment automatically.

### Steps after launch

1. In the Firefox Nightly window that opens, log in to Chase (if not already logged in from a previous run)
2. Go to **Credit Cards → Offers**
3. Enable the **Not added** filter
4. Switch back to the terminal and press **Enter**

The script runs through all visible offers. You can minimize the browser window — clicks are event-dispatched and do not require focus.

## Configuration

At the top of `chase_offers_clicker.py`:

| Constant | Default | Description |
|---|---|---|
| `FF_PROFILE` | `~/...Profiles/chase-automation` | Firefox profile directory used by the script |
| `WAIT_FOR_BTN_MS` | `8000` | How long to wait for a button before declaring done |
| `DELAY_MIN` / `DELAY_MAX` | `1.5` / `3.0` | Random human-like pause between offers (seconds) |

## How selectors are chosen

Chase renders offer cards as Web Components with deeply nested shadow DOM. The script tries several selector candidates in order and picks the first that finds elements:

| Selector | Notes |
|---|---|
| `mds-icon[type="ico_add_circle"]` | Targets the add icon by type attribute |
| `[aria-label="Add to card"]` | Stable aria-label fallback |
| `[aria-label*="Add offer"]` | Alternate aria-label variant |
| `[aria-label*="add"]` | Broad aria-label catch-all |
| `button[data-testid*="add"]` | data-testid fallback |
| `.r9jbijb` | CSS-module class (may rotate with Chase deployments) |

Both Playwright's built-in locator (pierces one shadow-root level) and a recursive JS shadow-DOM walker are tried for each candidate. If nothing matches, a DOM diagnostic runs automatically and prints the attributes of all candidate elements found — use that output to identify the current selector and add it to `SELECTOR_CANDIDATES`.

## Notes

- Chase uses obfuscated CSS class names (e.g., `.r9jbijb`) that can change with site deployments. Prefer the `aria-label`-based selectors when updating.
- The `chase-automation` profile accumulates cookies over time, reducing how often you need to log in.
- Tested on macOS with Python 3.11+ and Playwright 1.44+.
