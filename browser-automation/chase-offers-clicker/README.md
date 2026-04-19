# Chase Offers Auto-Clicker

Automatically activates all unclicked Chase Offers on your account using Playwright + Firefox. Run it once before each statement period to claim every available cash-back offer without manually clicking through hundreds of cards.

## How it works

1. Launches a real Firefox browser window (not headless) with automation-detection disabled
2. Pauses and waits for you to log in manually and navigate to the Chase Offers page
3. Probes the page for "add" buttons using multiple CSS selectors, with a recursive shadow-DOM walker as fallback (Chase's offer cards are built with deeply nested Web Components)
4. Clicks each unactivated offer using `dispatch_event('click')` — works even when the browser window is minimized or behind other windows
5. Handles back-navigation via the `mds-navigation-bar` shadow-DOM back button, with `page.go_back()` as fallback
6. Prints a running count and a final summary

## Setup

**One-time setup:**

```bash
python3 -m venv chase-offers-env
source chase-offers-env/bin/activate
pip install playwright
playwright install firefox
```

## Usage

```bash
source chase-offers-env/bin/activate
python3 chase_offers_clicker.py
```

Then in the Firefox window that opens:

1. Log in to your Chase account
2. Go to **Credit Cards → Offers**
3. Enable the **Not added** filter (so only unactivated offers are shown)
4. Switch back to the terminal and press **Enter**

The script runs through all visible offers automatically. You can minimize the browser window — clicks are event-dispatched and do not require focus.

## Configuration

At the top of `chase_offers_clicker.py`:

| Constant | Default | Description |
|---|---|---|
| `WAIT_FOR_BTN_MS` | `8000` | How long to wait for a button before declaring done |
| `DELAY_MIN` / `DELAY_MAX` | `1.5` / `3.0` | Random human-like pause between offers (seconds) |

## How selectors are chosen

Chase renders offer cards as Web Components with deeply nested shadow DOM. The script tries four selector candidates in order and picks the first that finds elements:

| Selector | Notes |
|---|---|
| `mds-icon[type="ico_add_circle"]` | Ideal — directly targets the add icon |
| `.r9jbijb` | CSS-module class used on add buttons as of early 2026 |
| `[aria-label="Add to card"]` | Aria-label fallback |
| `button[data-testid*="add"]` | data-testid fallback |

Both Playwright's built-in locator (pierces one shadow-root level) and a recursive JS shadow-DOM walker are tried for each candidate.

## Notes

- The script does **not** store credentials. Login is always done manually in the browser.
- Chase's obfuscated CSS class names (e.g., `.r9jbijb`) can change with site updates. If the script suddenly finds 0 buttons, inspect the "+" icon in browser DevTools and update `SELECTOR_CANDIDATES` accordingly.
- Tested on macOS with Python 3.11+ and Playwright 1.44+.
