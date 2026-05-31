#!/usr/bin/env python3
"""
Instagram scraper — AUTHENTICATED via Firefox cookies (Netscape file).

Two modes:
  1. post (default, back-compatible): extract carousel images from a single post/reel.
       ig_carousel_scraper.py <URL> <cookies-netscape.txt>
  2. list-profile: enumerate the top-N most-recent post/reel/tv permalinks from a
       profile grid (used by channel_enumerator.py for channel enumeration).
       ig_carousel_scraper.py list-profile <profile_url_or_handle> <cookies-netscape.txt> [--top N]

Both modes load Instagram cookies from a Netscape file into a Playwright Chromium
context (logged-in session needed to get past the profile/post login wall).

Output: JSON. post mode -> {success, post_id, images, count, details}.
        list-profile -> {success, handle, requested_n, found_n, items:[{position,url,type}], ...}.
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


IG_RESERVED = {"p", "reel", "reels", "tv", "explore", "stories", "accounts",
               "directory", "about", "developer", "legal", "api"}


def normalize_profile_url(value):
    """Normalize a handle/URL into a canonical profile URL. Raises ValueError if it is a post."""
    v = value.strip()
    if v.startswith('@'):
        v = v[1:]
    if v.startswith('http'):
        from urllib.parse import urlparse
        segs = [s for s in urlparse(v).path.split('/') if s]
        if not segs:
            raise ValueError('not a profile URL (no path segment)')
        if segs[0].lower() in IG_RESERVED:
            raise ValueError('not a profile URL (reserved segment %r)' % segs[0])
        if len(segs) != 1:
            raise ValueError('not a profile URL (multiple path segments)')
        return 'https://www.instagram.com/%s/' % segs[0]
    handle = v.strip('/').split('/')[0]
    return 'https://www.instagram.com/%s/' % handle


def _item_type(url):
    if '/reel/' in url:
        return 'reel'
    if '/tv/' in url:
        return 'tv'
    return 'post'


def list_profile(profile, cookies_path, top_n=5, max_scrolls=10):
    """Enumerate up to top_n recent /p//reel//tv permalinks from a profile grid (newest-first)."""
    try:
        profile_url = normalize_profile_url(profile)
    except ValueError as e:
        return {'success': False, 'error_code': 'not_a_profile', 'error': str(e),
                'found_n': 0, 'items': []}
    handle = [s for s in profile_url.rstrip('/').split('/') if s][-1]
    out = {'success': False, 'platform': 'instagram', 'channel_url': profile_url,
           'handle': handle, 'requested_n': top_n, 'found_n': 0,
           'ordering': 'profile-grid-dom-order-newest-first', 'items': [],
           'warnings': [], 'error_code': None, 'error': None}
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
                out['error_code'] = 'cookie_load'
                out['error'] = 'cookie-load: %s' % ce
                return out
            page = context.new_page()
            page.goto(profile_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3500)
            if '/accounts/login' in page.url:
                browser.close()
                out['error_code'] = 'login_required'
                out['error'] = 'Login wall hit despite cookies; refresh the Netscape cookies export.'
                return out
            seen, items = [], []
            for _ in range(max_scrolls):
                hrefs = page.eval_on_selector_all(
                    'a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]',
                    'els => els.map(e => e.getAttribute("href"))')
                for href in hrefs:
                    if not href:
                        continue
                    m = re.search(r'/(?:p|reel|tv)/([^/?]+)', href)
                    if not m or m.group(1) in seen:
                        continue
                    seen.append(m.group(1))
                    seg = 'reel' if '/reel/' in href else ('tv' if '/tv/' in href else 'p')
                    url = 'https://www.instagram.com/%s/%s/' % (seg, m.group(1))
                    items.append({'url': url, 'type': _item_type(url)})
                if len(items) >= top_n:
                    break
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(1500)
            browser.close()
            if not items:
                out['error_code'] = 'private_or_blocked'
                out['error'] = 'No permalinks found (private, empty, blocked, or layout changed).'
                return out
            items = items[:top_n]
            out['success'] = True
            out['found_n'] = len(items)
            out['items'] = [{'position': i + 1, **it} for i, it in enumerate(items)]
            out['warnings'].append('profile grid may include pinned posts not in strict chronological order')
            return out
    except PlaywrightTimeout:
        out['error_code'] = 'timeout'
        out['error'] = 'Playwright timeout'
        return out
    except Exception as e:
        out['error_code'] = 'error'
        out['error'] = str(e)
        return out


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == 'list-profile':
        rest = args[1:]
        top = 5
        if '--top' in rest:
            i = rest.index('--top')
            try:
                top = int(rest[i + 1])
            except (IndexError, ValueError):
                pass
            rest = rest[:i] + rest[i + 2:]
        if len(rest) < 2:
            print(json.dumps({'success': False,
                              'error': 'Usage: ig_carousel_scraper.py list-profile <profile> <cookies-netscape.txt> [--top N]',
                              'found_n': 0, 'items': []}))
            sys.exit(1)
        result = list_profile(rest[0], rest[1], top_n=top)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get('success') else 1)
    # Back-compatible post mode.
    if len(args) < 2:
        print(json.dumps({'success': False, 'error': 'Usage: ig_carousel_scraper.py <URL> <cookies-netscape.txt> | list-profile <profile> <cookies> [--top N]', 'images': []}))
        sys.exit(1)
    print(json.dumps(scrape(args[0], args[1]), indent=2))
