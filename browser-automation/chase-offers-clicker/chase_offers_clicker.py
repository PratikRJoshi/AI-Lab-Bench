#!/usr/bin/env python3
"""
Chase Offers Auto-Clicker
=========================
Automatically activates all unclicked Chase Offers using Playwright + Firefox.

Setup (one-time):
    pip install playwright
    playwright install firefox

Usage:
    python3 chase_offers_clicker.py
"""

import random
import sys
import time

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright is not installed.")
    print("Run: pip install playwright && playwright install firefox")
    sys.exit(1)

BACK_HOST_SEL  = "mds-navigation-bar"
BACK_INNER_SEL = "#back-button"

WAIT_FOR_BTN_MS = 8_000
DELAY_MIN       = 1.5
DELAY_MAX       = 3.0

# JS that walks the entire shadow-DOM tree and returns all matching elements
_SHADOW_FIND_ALL_JS = """
(selector) => {
    function findAll(root, selector) {
        const found = [];
        root.querySelectorAll(selector).forEach(el => found.push(el));
        root.querySelectorAll('*').forEach(el => {
            if (el.shadowRoot) {
                findAll(el.shadowRoot, selector).forEach(el2 => found.push(el2));
            }
        });
        return found;
    }
    return findAll(document, selector);
}
"""

# Candidates in priority order — we pick the first one that finds elements
SELECTOR_CANDIDATES = [
    'mds-icon[type="ico_add_circle"]',   # validated in Selenium gist
    '.r9jbijb',                           # timkpaine's JS gist fallback
    '[aria-label="Add to card"]',
    'button[data-testid*="add"]',
]


def human_pause():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def probe_and_pick_selector(page):
    """
    Try each candidate selector using both Playwright's locator (which pierces
    one shadow root level) and a recursive JS shadow-DOM walker.
    Returns (selector, count, use_js_click) for the first hit, or (None, 0, False).
    """
    print("  Trying selectors:")
    for sel in SELECTOR_CANDIDATES:
        # Playwright locator — pierces shadow DOM automatically
        pw_count = page.locator(sel).count()
        # Recursive JS walker — handles unlimited nesting
        js_count = len(page.evaluate(_SHADOW_FIND_ALL_JS, sel))
        print(f"    '{sel}'  =>  locator: {pw_count},  shadow-walk: {js_count}")
        if pw_count > 0:
            return sel, pw_count, False   # prefer locator click
        if js_count > 0:
            return sel, js_count, True    # fall back to JS click
    return None, 0, False


def js_click_first(page, selector):
    """Click the first match found via recursive shadow-DOM walk."""
    return page.evaluate(
        """
        (selector) => {
            function findFirst(root, selector) {
                const direct = root.querySelector(selector);
                if (direct) return direct;
                for (const el of root.querySelectorAll('*')) {
                    if (el.shadowRoot) {
                        const found = findFirst(el.shadowRoot, selector);
                        if (found) return found;
                    }
                }
                return null;
            }
            const el = findFirst(document, selector);
            if (!el) return false;
            el.scrollIntoView({block: 'center'});
            el.click();
            return true;
        }
        """,
        selector,
    )


def click_back(page):
    """Click the Back button inside mds-navigation-bar's shadow DOM."""
    return page.evaluate(
        f"""() => {{
            const host = document.querySelector('{BACK_HOST_SEL}');
            if (!host || !host.shadowRoot) return false;
            const btn = host.shadowRoot.querySelector('{BACK_INNER_SEL}');
            if (!btn) return false;
            btn.click();
            return true;
        }}"""
    )


STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete window.__playwright;
    delete window.__pw_manual;
    delete window.playwright;
"""


def main():
    with sync_playwright() as p:
        print("Launching Firefox (stealth mode)...")
        browser = p.firefox.launch(
            headless=False,
            firefox_user_prefs={
                "dom.webdriver.enabled": False,
                "useAutomationExtension": False,
            },
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) "
                "Gecko/20100101 Firefox/137.0"
            ),
        )
        context.add_init_script(STEALTH_SCRIPT)
        page = context.new_page()

        print("\nNavigating to Chase login page...")
        page.goto("https://secure.chase.com", timeout=30_000)

        print("\n" + "=" * 60)
        print("ACTION REQUIRED:")
        print("  1. Log in to your Chase account in the browser window.")
        print("  2. Navigate to the Chase Offers page (Credit Card > Offers).")
        print("  3. Make sure the 'Not added' filter is active.")
        print("=" * 60)
        input("\nPress Enter here once you're on the Chase Offers page... ")

        print(f"\nCurrent page URL: {page.url}")

        print("Waiting for page to settle...")
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeout:
            pass

        # Scroll through the page to trigger lazy-loaded cards
        page.keyboard.press("End")
        time.sleep(1.5)
        page.keyboard.press("Home")
        time.sleep(1.0)

        print("\nProbing for add buttons...")
        active_sel, count, use_js = probe_and_pick_selector(page)

        if active_sel is None:
            print(
                "\nNo add buttons found with any known selector.\n"
                "TROUBLESHOOTING:\n"
                "  • Make sure you're on the Offers page in the Playwright browser window\n"
                "    (not your normal Firefox — they are separate windows)\n"
                "  • The 'Not added' filter must be active (149 results)\n"
                "  • Try scrolling down in the Playwright browser to load offer cards\n"
                "  • Then re-run the script\n"
            )
            input("Press Enter to close... ")
            browser.close()
            return

        click_mode = "JS shadow-walk" if use_js else "Playwright locator"
        print(f"\nUsing selector '{active_sel}' ({click_mode}) — {count} button(s) found.")
        print("Starting activation loop...\n")
        time.sleep(1)

        activated = 0
        errors    = 0
        iteration = 0

        while True:
            iteration += 1

            # Check whether any add button is present (signals we're on the list view)
            if use_js:
                present = len(page.evaluate(_SHADOW_FIND_ALL_JS, active_sel)) > 0
                if not present:
                    # Wait up to WAIT_FOR_BTN_MS polling every 500ms
                    deadline = time.time() + WAIT_FOR_BTN_MS / 1000
                    while time.time() < deadline:
                        time.sleep(0.5)
                        if len(page.evaluate(_SHADOW_FIND_ALL_JS, active_sel)) > 0:
                            present = True
                            break
                if not present:
                    print(f"\nNo more add buttons found after {WAIT_FOR_BTN_MS / 1000:.0f}s.")
                    break
            else:
                try:
                    page.locator(active_sel).first.wait_for(
                        timeout=WAIT_FOR_BTN_MS, state="visible"
                    )
                except PlaywrightTimeout:
                    print(f"\nNo more add buttons found after {WAIT_FOR_BTN_MS / 1000:.0f}s.")
                    break

            try:
                if use_js:
                    clicked = js_click_first(page, active_sel)
                    if not clicked:
                        raise RuntimeError("js_click_first returned False")
                else:
                    btn = page.locator(active_sel).first
                    btn.dispatch_event('click')

                human_pause()

                # Click Back to return to the offers list
                back_ok = click_back(page)
                if not back_ok:
                    time.sleep(1.0)
                    back_ok = click_back(page)
                if not back_ok:
                    print(f"  [offer {iteration}] WARNING: Back button not found — using browser back...")
                    page.go_back()

                activated += 1
                print(f"  Activated offer #{activated}", flush=True)
                human_pause()

            except Exception as exc:
                errors += 1
                print(f"  [offer {iteration}] Error: {exc} — skipping...")
                try:
                    page.go_back(timeout=5_000)
                    time.sleep(1.5)
                except Exception:
                    pass

        print("\n" + "=" * 60)
        print(f"Done!  Activated {activated} offer(s).  Errors skipped: {errors}.")
        print("=" * 60)

        input("\nPress Enter to close the browser... ")
        browser.close()


if __name__ == "__main__":
    main()
