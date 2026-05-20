#!/usr/bin/env python3
"""
Instagram carousel image scraper — AUTHENTICATED via Firefox cookies.

Loads Instagram cookies from a Netscape file into a Playwright Chromium
context, navigates to the post, and extracts carousel images by:
- Filtering DOM img elements where alt starts with "Photo by " or "Video by "
- Requiring width >= 600 (post images on IG are 1080+ wide; profile pics are 150x150)
- Clicking the "Next" carousel arrow up to N times to load every slide

Usage: ig_carousel_scraper.py <URL> <cookies-netscape.txt>
Output: JSON with success, post_id, images (largest URL per slide), count, details.
"""

import sys
import json
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def load_netscape_cookies(path):
    cookies = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 7:
                continue
            domain, _, path_, secure, expiry, name, value = parts[:7]
            try:
                exp_int = int(expiry)
            except ValueError:
                exp_int = -1
            ck = {
                'name': name, 'value': value, 'domain': domain, 'path': path_,
                'secure': secure.upper() == 'TRUE', 'httpOnly': False, 'sameSite': 'Lax',
            }
            if exp_int > 0:
                ck['expires'] = exp_int
            cookies.append(ck)
    return [c for c in cookies if 'instagram' in c.get('domain', '')]


def is_post_image(img):
    alt = (img.get('alt') or '')
    w = img.get('w') or 0
    h = img.get('h') or 0
    src = img.get('src') or ''
    if not src.startswith('http'):
        return False
    if 'profile' in alt.lower() or 'profile' in src.lower():
        return False
    # IG post images: alt starts with "Photo by " or "Video by "; size >= 600
    if not (alt.startswith('Photo by ') or alt.startswith('Video by ')):
        return False
    if w < 600 and h < 600:
        return False
    return True


def scrape(url, cookies_path):
    post_id_m = re.search(r'/(?:p|reel)/([^/?]+)', url)
    post_id = post_id_m.group(1) if post_id_m else 'unknown'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 1024},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            )
            try:
                context.add_cookies(load_netscape_cookies(cookies_path))
            except Exception as ce:
                browser.close()
                return {'success': False, 'post_id': post_id, 'error': f'cookie-load: {ce}', 'images': []}

            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3500)

            collected = {}  # key=src -> dict with details (newest wins)
            uploader_handle = None

            def harvest():
                nonlocal uploader_handle
                imgs = page.eval_on_selector_all(
                    'img',
                    """elements => elements.map(el => ({
                        src: el.src,
                        alt: el.alt || '',
                        w: el.naturalWidth || 0,
                        h: el.naturalHeight || 0,
                    }))""",
                )
                for img in imgs:
                    if is_post_image(img):
                        if uploader_handle is None:
                            m = re.match(r'^(?:Photo|Video) by ([^\s.…]+)', img['alt'])
                            if m:
                                uploader_handle = m.group(1)
                        collected[img['src']] = img

            harvest()
            # Walk the carousel: click Next up to 14 times, harvesting after each click
            clicks = 0
            for _ in range(14):
                try:
                    nxt = page.locator('button[aria-label="Next"]').first
                    if not nxt.is_visible(timeout=1500):
                        break
                    nxt.click(timeout=2500)
                    clicks += 1
                    page.wait_for_timeout(900)
                    harvest()
                except Exception:
                    break

            # If no Next button, try also dragging the carousel via keyboard right-arrow
            if clicks == 0 and len(collected) < 2:
                for _ in range(14):
                    try:
                        page.keyboard.press('ArrowRight')
                        page.wait_for_timeout(700)
                        harvest()
                    except Exception:
                        break

            browser.close()

            images = list(collected.values())
            if not images:
                return {'success': False, 'post_id': post_id, 'uploader_handle': uploader_handle,
                        'error': 'No post images extracted (alt-filter empty after carousel walk)', 'images': []}

            return {
                'success': True,
                'post_id': post_id,
                'uploader_handle': uploader_handle,
                'images': [img['src'] for img in images],
                'count': len(images),
                'clicks': clicks,
                'details': [{'src': i['src'], 'w': i['w'], 'h': i['h'], 'alt': i['alt'][:120]} for i in images],
            }

    except PlaywrightTimeout:
        return {'success': False, 'post_id': post_id, 'error': 'Playwright timeout', 'images': []}
    except Exception as e:
        return {'success': False, 'post_id': post_id, 'error': str(e), 'images': []}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({'success': False, 'error': 'Usage: ig_carousel_scraper.py <URL> <cookies-netscape.txt>', 'images': []}))
        sys.exit(1)
    url = sys.argv[1]
    cookies_path = sys.argv[2]
    print(json.dumps(scrape(url, cookies_path), indent=2))
