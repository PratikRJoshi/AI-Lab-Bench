#!/usr/bin/env python3
"""channel_enumerator.py

Detect channel/profile entries and enumerate their top-N most-recent permalinks
for the url-truth-analyzer skill. JSON-only output so SKILL.md can consume it
deterministically.

Implemented:
  - Phase 1: directive parsing, platform detection, channel-vs-single detection,
    validation failures.
  - Phase 2: YouTube channel enumeration (videos/shorts/streams tabs) via yt-dlp.

Pending (return structured error_code "not_implemented"):
  - Instagram profile enumeration  (Phase 3 -> delegates to instagram_scraper.py)
  - Generic site enumeration        (Phase 4 -> RSS/Atom, yt-dlp generic, sitemap)

CLI:
  python3 channel_enumerator.py '<ENTRY>' [--top N] [--platform P]
          [--include videos,shorts] [--no-cookies] [--strict-order] --json
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_N = 5
MAX_N = 25
YOUTUBE_TABS = ("videos", "shorts", "streams")
DEFAULT_IG_COOKIES = "/tmp/url-analyzer/ig-cookies.txt"  # Netscape cookies exported by SKILL.md Phase 1 prerequisite

# Item directives that may be propagated to each enumerated permalink.
PROPAGATABLE_DIRECTIVES = {"transcript-only", "audio-only", "browser-mode", "display-only"}
# Directives consumed by expansion (never propagated to per-item processing).
CHANNEL_ONLY_DIRECTIVE_PREFIXES = ("channel", "top:", "platform:", "include:")
TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?-\d{1,2}:\d{2}(:\d{2})?$")

# Instagram reserved first-path segments that are NOT profiles.
IG_RESERVED = {"p", "reel", "reels", "tv", "explore", "stories", "accounts",
               "directory", "about", "developer", "legal", "directory"}


# --------------------------------------------------------------------------- #
# Phase 1: parsing + detection
# --------------------------------------------------------------------------- #
def parse_directives(directive_str):
    """Parse the inside of a [...] directive block into structured flags.

    Returns dict with: channel_mode, n (or None), top_n (or None), platform,
    include (list), inherited (list of propagatable item directives),
    errors (list of strings).
    """
    out = {
        "channel_mode": False,
        "n": None,
        "top_n": None,
        "platform": None,
        "include": [],
        "inherited": [],
        "errors": [],
    }
    if not directive_str:
        return out

    for tok in directive_str.split():
        low = tok.lower()
        if low == "channel":
            out["channel_mode"] = True
        elif low.startswith("channel:"):
            out["channel_mode"] = True
            out["n"] = _parse_int(tok.split(":", 1)[1], out, "channel")
        elif low.startswith("top:"):
            out["top_n"] = _parse_int(tok.split(":", 1)[1], out, "top")
        elif low.startswith("platform:"):
            out["platform"] = tok.split(":", 1)[1].lower()
        elif low.startswith("include:"):
            out["include"] = [t for t in tok.split(":", 1)[1].lower().split(",") if t]
        elif low in PROPAGATABLE_DIRECTIVES:
            out["inherited"].append(low)
        elif TIMESTAMP_RE.match(tok):
            out["inherited"].append(tok)  # timestamp range (video/audio only)
        elif low.startswith("title:"):
            pass  # not propagated for channel mode; each item gets its own title
        else:
            out["errors"].append("unknown directive token: %s" % tok)
    return out


def _parse_int(raw, out, name):
    try:
        return int(raw)
    except ValueError:
        out["errors"].append("%s count is not an integer: %r" % (name, raw))
        return None


def split_entry(raw_line):
    """Split a raw watch-urls.md line into (clean_target, directive_str)."""
    line = raw_line.strip()
    m = re.search(r"\[(.*)\]\s*$", line)
    if m:
        directive_str = m.group(1)
        clean = line[: m.start()].strip()
        return clean, directive_str
    return line, ""


def infer_platform(target):
    """Infer platform from a URL or bare handle. Returns youtube|instagram|generic|unknown."""
    if target.startswith("@"):
        return "unknown"  # bare handle: needs a platform hint
    host = (urlparse(target).hostname or "").lower()
    if not host:
        return "unknown"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    return "generic"


def _yt_is_channel_path(path):
    segs = [s for s in path.split("/") if s]
    if not segs:
        return False
    head = segs[0]
    if head.startswith("@"):
        return True
    if head in ("c", "user", "channel") and len(segs) >= 2:
        return True
    return False


def _yt_is_single(target):
    host = (urlparse(target).hostname or "").lower()
    path = urlparse(target).path
    if "youtu.be" in host:
        return True
    segs = [s for s in path.split("/") if s]
    if segs and segs[0] in ("watch", "shorts", "live", "playlist", "embed"):
        return True
    if "watch" in urlparse(target).path or "v=" in (urlparse(target).query or ""):
        return True
    return False


def _ig_is_profile(target):
    segs = [s for s in urlparse(target).path.split("/") if s]
    return len(segs) == 1 and segs[0].lower() not in IG_RESERVED


def detect_entry(clean_target, directives):
    """Classify entry into single-url | local-folder | channel and resolve platform.

    Returns dict: entry_kind, platform, channel_shaped (bool), errors (list).
    """
    res = {"entry_kind": "single-url", "platform": None, "channel_shaped": False,
           "errors": list(directives.get("errors", []))}

    if clean_target.startswith("/") and not clean_target.startswith("//") \
            and not clean_target.lower().startswith("http"):
        res["entry_kind"] = "local-folder"
        return res

    platform = directives.get("platform") or infer_platform(clean_target)
    res["platform"] = platform

    channel_directive = directives.get("channel_mode") or directives.get("top_n") is not None

    # Bare handle requires a platform hint.
    if clean_target.startswith("@"):
        if not directives.get("platform"):
            res["errors"].append(
                "bare handle requires platform hint: platform:youtube or platform:instagram")
        res["entry_kind"] = "channel"
        res["channel_shaped"] = True
        res["platform"] = directives.get("platform") or "unknown"
        return res

    if platform == "youtube":
        if _yt_is_single(clean_target):
            res["entry_kind"] = "channel" if channel_directive else "single-url"
            res["channel_shaped"] = False
            if channel_directive:
                res["errors"].append(
                    "channel directive on a single-video YouTube URL; expected a channel URL")
            return res
        if _yt_is_channel_path(urlparse(clean_target).path) or channel_directive:
            res["entry_kind"] = "channel"
            res["channel_shaped"] = True
            return res

    if platform == "instagram":
        if _ig_is_profile(clean_target):
            res["entry_kind"] = "channel"
            res["channel_shaped"] = True
            return res
        # /p/, /reel/, /tv/ -> single post
        res["entry_kind"] = "channel" if channel_directive else "single-url"
        res["channel_shaped"] = False
        if channel_directive:
            res["errors"].append(
                "channel directive on a single Instagram post URL; expected a profile URL")
        return res

    if platform == "generic":
        # Generic only treated as channel when a channel directive is present.
        if channel_directive:
            res["entry_kind"] = "channel"
            res["channel_shaped"] = True
        return res

    return res


def resolve_n(directives, cli_top):
    """Resolve effective N and validate channel:N vs top:N conflict.

    Returns (n, errors_list).
    """
    errors = []
    d_channel_n = directives.get("n")
    d_top_n = directives.get("top_n")
    if d_channel_n is not None and d_top_n is not None and d_channel_n != d_top_n:
        errors.append("conflicting channel counts: channel:%s and top:%s"
                      % (d_channel_n, d_top_n))
        return None, errors
    n = cli_top if cli_top is not None else (
        d_channel_n if d_channel_n is not None else (
            d_top_n if d_top_n is not None else DEFAULT_N))
    if n < 1:
        errors.append("N must be >= 1")
        return None, errors
    if n > MAX_N:
        n = MAX_N  # soft cap (warning emitted by caller)
    return n, errors


def parse_entry(raw_line, cli_top=None, cli_platform=None):
    """Full parse of a watch-urls.md entry line into structured metadata."""
    clean, directive_str = split_entry(raw_line)
    directives = parse_directives(directive_str)
    if cli_platform:
        directives["platform"] = cli_platform.lower()
    det = detect_entry(clean, directives)
    n, n_errors = resolve_n(directives, cli_top)
    warnings = []
    requested_capped = (directives.get("n") or directives.get("top_n") or cli_top)
    if requested_capped is not None and requested_capped and requested_capped > MAX_N:
        warnings.append("requested N=%s exceeds hard cap; using %s" % (requested_capped, MAX_N))
    return {
        "original": raw_line.strip(),
        "clean_target": clean,
        "entry_kind": det["entry_kind"],
        "platform": det["platform"],
        "channel_shaped": det["channel_shaped"],
        "n": n,
        "include": directives.get("include") or [],
        "inherited_directives": directives.get("inherited") or [],
        "display_only": "display-only" in (directives.get("inherited") or []),
        "errors": det["errors"] + n_errors,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# Phase 2: YouTube enumeration
# --------------------------------------------------------------------------- #
def canonicalize_youtube(target, platform_hint=None):
    """Return the channel base URL (no tab suffix)."""
    if target.startswith("@"):
        return "https://www.youtube.com/%s" % target
    p = urlparse(target)
    segs = [s for s in p.path.split("/") if s]
    # Strip a trailing tab if present.
    if segs and segs[-1] in ("videos", "shorts", "streams", "featured", "playlists",
                             "community", "about"):
        segs = segs[:-1]
    base_path = "/".join(segs)
    return "https://www.youtube.com/%s" % base_path


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def _ytdlp_flat(tab_url, n, use_cookies):
    """Return list of dicts {id, live_status, url, title} for a tab, newest-first."""
    fmt = "%(id)s\t%(live_status)s\t%(webpage_url)s\t%(title)s"
    base = ["yt-dlp", "--flat-playlist", "--playlist-end", str(n),
            "--print", fmt, tab_url]
    if use_cookies:
        base = base[:1] + ["--cookies-from-browser", "firefox"] + base[1:]
    r = _run(base)
    if r.returncode != 0:
        return None, r.stderr.strip()
    items = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        vid, live, url, title = parts[0], parts[1], parts[2], "\t".join(parts[3:])
        items.append({"id": vid, "live_status": live, "url": url, "title": title})
    return items, None


def _normalize_yt_permalink(item, tab):
    vid = item["id"]
    if tab == "shorts":
        return "https://www.youtube.com/shorts/%s" % vid, "short"
    return "https://www.youtube.com/watch?v=%s" % vid, "video"


def enumerate_youtube(clean_target, n, include_tabs, use_cookies=True, strict_order=False):
    base = canonicalize_youtube(clean_target)
    tabs = include_tabs or ["videos"]
    tabs = [t for t in tabs if t in YOUTUBE_TABS] or ["videos"]

    collected = []
    seen = set()
    warnings = []
    first_err = None
    for tab in tabs:
        tab_url = "%s/%s" % (base.rstrip("/"), tab)
        items, err = _ytdlp_flat(tab_url, n if len(tabs) == 1 else n, use_cookies)
        if items is None:
            first_err = first_err or err
            if use_cookies:
                # retry without cookies once
                items, err2 = _ytdlp_flat(tab_url, n, use_cookies=False)
                if items is None:
                    continue
                warnings.append("cookies unavailable for tab %s; retried without cookies" % tab)
            else:
                continue
        for it in items:
            if it["live_status"] in ("is_upcoming", "is_live"):
                continue  # filter premieres / live-upcoming (unplayable)
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            url, typ = _normalize_yt_permalink(it, tab)
            collected.append({"url": url, "type": typ, "title": it["title"], "tab": tab})

    ordering = "tab-order-newest-first"
    if len(tabs) > 1 and not strict_order:
        warnings.append("multi-tab output is tab-grouped (videos, then shorts, then streams); "
                        "pass --strict-order for upload_date interleave")
        ordering = "tab-grouped"

    # RSS fallback if nothing collected.
    if not collected:
        rss_items, rss_warn = _youtube_rss_fallback(base, n, use_cookies)
        if rss_warn:
            warnings.append(rss_warn)
        if rss_items:
            collected = rss_items
            ordering = "rss-newest-first"
        else:
            return _fail("youtube", clean_target, n,
                         "enumeration_failed",
                         "yt-dlp returned no entries and RSS fallback failed: %s"
                         % (first_err or "unknown"), warnings)

    collected = collected[:n]
    items_out = [{"position": i + 1, "url": c["url"], "type": c["type"], "title": c["title"]}
                 for i, c in enumerate(collected)]
    found = len(items_out)
    shortfall = None
    if found < n:
        shortfall = "requested %d, found %d" % (n, found)
    return {
        "success": True,
        "entry_type": "channel",
        "platform": "youtube",
        "channel_url": base,
        "handle": _yt_handle(base),
        "requested_n": n,
        "found_n": found,
        "ordering": ordering,
        "shortfall": shortfall,
        "items": items_out,
        "warnings": warnings,
    }


def _yt_handle(base):
    segs = [s for s in urlparse(base).path.split("/") if s]
    return segs[-1] if segs else None


def _youtube_rss_fallback(base, n, use_cookies):
    cmd = ["yt-dlp", "--skip-download", "--playlist-end", "1", "--print", "%(channel_id)s", base]
    if use_cookies:
        cmd = cmd[:1] + ["--cookies-from-browser", "firefox"] + cmd[1:]
    r = _run(cmd)
    cid = (r.stdout.strip().splitlines() or [""])[0].strip()
    if not cid.startswith("UC"):
        return None, "RSS fallback: could not resolve channel_id"
    feed = "https://www.youtube.com/feeds/videos.xml?channel_id=%s" % cid
    try:
        with urllib.request.urlopen(feed, timeout=20) as resp:
            data = resp.read()
    except Exception as e:  # noqa: BLE001
        return None, "RSS fallback: feed fetch failed (%s)" % e
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(data)
    out = []
    for entry in root.findall("a:entry", ns)[:n]:
        vid_el = entry.find("yt:videoId", ns)
        title_el = entry.find("a:title", ns)
        if vid_el is None:
            continue
        out.append({"url": "https://www.youtube.com/watch?v=%s" % vid_el.text,
                    "type": "video", "title": title_el.text if title_el is not None else "",
                    "tab": "rss"})
    note = "RSS fallback used (feed caps at ~15 items)" if out else "RSS fallback: feed empty"
    return out, note


def _fail(platform, target, n, code, msg, warnings=None):
    return {
        "success": False,
        "entry_type": "channel",
        "platform": platform,
        "channel_url": target,
        "requested_n": n,
        "found_n": 0,
        "error_code": code,
        "error": msg,
        "warnings": warnings or [],
    }


# --------------------------------------------------------------------------- #
# Phase 3: Instagram (delegate to instagram_scraper.py list-profile)
# --------------------------------------------------------------------------- #
def enumerate_instagram(clean_target, n, ig_cookies=DEFAULT_IG_COOKIES):
    scraper = Path(__file__).resolve().parent / "ig_carousel_scraper.py"
    if not scraper.exists():
        return _fail("instagram", clean_target, n, "scraper_missing",
                     "ig_carousel_scraper.py not found next to channel_enumerator.py")
    if not Path(ig_cookies).exists():
        return _fail("instagram", clean_target, n, "cookies_missing",
                     "Netscape cookies file not found at %s; export Firefox cookies first "
                     "(see SKILL.md 'Phase 1 prerequisite — export Firefox cookies')." % ig_cookies)
    cmd = [sys.executable, str(scraper), "list-profile", clean_target, ig_cookies,
           "--top", str(n)]
    r = _run(cmd)
    try:
        data = json.loads(r.stdout)
    except (ValueError, json.JSONDecodeError):
        return _fail("instagram", clean_target, n, "scraper_error",
                     "ig_carousel_scraper.py produced no JSON: %s" % (r.stderr.strip()[:300]))
    if not data.get("success"):
        return _fail("instagram", clean_target, n,
                     data.get("error_code", "enumeration_failed"),
                     data.get("error", "unknown"), data.get("warnings"))
    return {
        "success": True,
        "entry_type": "channel",
        "platform": "instagram",
        "channel_url": data.get("channel_url", clean_target),
        "handle": data.get("handle"),
        "requested_n": n,
        "found_n": data.get("found_n", len(data.get("items", []))),
        "ordering": data.get("ordering", "profile-grid-dom-order-newest-first"),
        "shortfall": ("requested %d, found %d" % (n, data.get("found_n", 0))
                      if data.get("found_n", 0) < n else None),
        "items": data.get("items", []),
        "warnings": data.get("warnings", []),
    }


# --------------------------------------------------------------------------- #
# Phase 4: Generic website (RSS/Atom -> yt-dlp generic -> sitemap)
# --------------------------------------------------------------------------- #
ASSET_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".css", ".js", ".pdf",
             ".svg", ".ico", ".xml", ".woff", ".woff2", ".mp4", ".mp3")
CONTENT_HINTS = ("/post/", "/posts/", "/blog/", "/news/", "/video/", "/videos/",
                 "/watch/", "/reel/", "/article/", "/articles/", "/story/", "/p/")
COMMON_FEED_PATHS = ("/feed", "/feed.xml", "/rss", "/rss.xml", "/atom.xml", "/feed/")


def _http_get(url, timeout=20, head=False):
    req = urllib.request.Request(url, method="HEAD" if head else "GET",
                                 headers={"User-Agent": "Mozilla/5.0 (url-truth-analyzer)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            body = b"" if head else resp.read()
            return resp.status, ctype, body
    except Exception:  # noqa: BLE001
        return None, None, None


def _discover_feed(root_url):
    """Find a feed URL: <link rel=alternate> first, then probe common paths (stop at first)."""
    status, ctype, body = _http_get(root_url)
    if body:
        html = body.decode("utf-8", "ignore")
        for m in re.finditer(r'<link[^>]+rel=["\']alternate["\'][^>]*>', html, re.I):
            tag = m.group(0)
            if re.search(r'application/(rss|atom)\+xml', tag, re.I):
                href = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
                if href:
                    return urllib.parse.urljoin(root_url, href.group(1))
    base = "%s://%s" % (urlparse(root_url).scheme, urlparse(root_url).netloc)
    for path in COMMON_FEED_PATHS:
        status, ctype, _ = _http_get(base + path, timeout=10, head=True)
        if status and status < 400 and ("xml" in (ctype or "") or path.endswith((".xml", "/feed", "/rss"))):
            return base + path
    return None


def _parse_feed(feed_url, n):
    status, ctype, body = _http_get(feed_url)
    if not body:
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items = []
    # RSS: channel/item/link ; Atom: entry/link[@href]
    for item in root.iter():
        tag = item.tag.lower().split("}")[-1]
        if tag == "item":  # RSS
            link = item.find("link")
            if link is not None and link.text:
                items.append(link.text.strip())
        elif tag == "entry":  # Atom
            link = item.find("{http://www.w3.org/2005/Atom}link")
            if link is not None and link.get("href"):
                items.append(link.get("href").strip())
        if len(items) >= n:
            break
    return items[:n]


def _try_sitemap(root_url, n):
    base = "%s://%s" % (urlparse(root_url).scheme, urlparse(root_url).netloc)
    for path in ("/sitemap.xml", "/sitemap_index.xml"):
        status, ctype, body = _http_get(base + path)
        if not body:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            continue
        entries = []
        for url_el in root.iter():
            tag = url_el.tag.lower().split("}")[-1]
            if tag == "url":
                loc = next((c for c in url_el if c.tag.lower().endswith("loc")), None)
                lastmod = next((c for c in url_el if c.tag.lower().endswith("lastmod")), None)
                if loc is not None and loc.text:
                    u = loc.text.strip()
                    if u.lower().endswith(ASSET_EXT):
                        continue
                    entries.append((u, lastmod.text.strip() if lastmod is not None and lastmod.text else ""))
        if entries:
            entries.sort(key=lambda x: x[1], reverse=True)
            preferred = [u for u, _ in entries if any(h in u for h in CONTENT_HINTS)]
            chosen = (preferred or [u for u, _ in entries])[:n]
            return chosen
    return []


def enumerate_generic(clean_target, n):
    warnings = []
    # Path A: RSS/Atom
    feed = _discover_feed(clean_target)
    if feed:
        links = _parse_feed(feed, n)
        if links:
            return _generic_ok(clean_target, n, links, "rss-newest-first",
                               ["feed: %s" % feed], "article")
        warnings.append("feed found (%s) but no entries parsed" % feed)
    # Path B: yt-dlp generic flat-playlist
    cmd = ["yt-dlp", "--flat-playlist", "--playlist-end", str(n),
           "--print", "%(webpage_url)s", clean_target]
    r = _run(cmd)
    if r.returncode == 0 and r.stdout.strip():
        links = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()][:n]
        if links:
            return _generic_ok(clean_target, n, links, "yt-dlp-generic", warnings, "video")
    else:
        warnings.append("yt-dlp generic returned nothing")
    # Path C: sitemap
    links = _try_sitemap(clean_target, n)
    if links:
        warnings.append("sitemap ordering is best-effort (lastmod)")
        return _generic_ok(clean_target, n, links, "sitemap-lastmod", warnings, "article")
    return _fail("generic", clean_target, n, "enumeration_failed",
                 "no RSS/Atom feed, yt-dlp playlist, or sitemap entries found; "
                 "add individual permalinks manually", warnings)


def _generic_ok(target, n, links, ordering, warnings, typ):
    items = [{"position": i + 1, "url": u, "type": typ, "title": ""}
             for i, u in enumerate(links[:n])]
    return {
        "success": True, "entry_type": "channel", "platform": "generic",
        "channel_url": target, "handle": urlparse(target).netloc,
        "requested_n": n, "found_n": len(items), "ordering": ordering,
        "shortfall": ("requested %d, found %d" % (n, len(items)) if len(items) < n else None),
        "items": items, "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def enumerate_entry(parsed, use_cookies=True, strict_order=False, ig_cookies=DEFAULT_IG_COOKIES):
    if parsed["errors"]:
        return _fail(parsed["platform"], parsed["clean_target"], parsed["n"] or 0,
                     "parse_error", "; ".join(parsed["errors"]))
    if parsed["entry_kind"] != "channel":
        return _fail(parsed["platform"], parsed["clean_target"], parsed["n"] or 0,
                     "not_a_channel",
                     "entry classified as %s, not a channel" % parsed["entry_kind"])
    platform = parsed["platform"]
    n = parsed["n"]
    if platform == "youtube":
        return enumerate_youtube(parsed["clean_target"], n, parsed["include"],
                                 use_cookies=use_cookies, strict_order=strict_order)
    if platform == "instagram":
        return enumerate_instagram(parsed["clean_target"], n, ig_cookies=ig_cookies)
    if platform == "generic":
        return enumerate_generic(parsed["clean_target"], n)
    return _fail(platform or "unknown", parsed["clean_target"], n, "unknown_platform",
                 "could not resolve platform; add platform: hint")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Enumerate channel/profile entries into permalinks.")
    ap.add_argument("entry", help="channel URL / handle, optionally with [channel:N ...] directives")
    ap.add_argument("--top", type=int, default=None, help="top N (overrides directive)")
    ap.add_argument("--platform", default=None, help="youtube|instagram|generic (for bare handles)")
    ap.add_argument("--include", default=None, help="comma tabs for youtube: videos,shorts,streams")
    ap.add_argument("--no-cookies", action="store_true", help="do not pass --cookies-from-browser (YouTube)")
    ap.add_argument("--strict-order", action="store_true", help="multi-tab upload_date interleave")
    ap.add_argument("--ig-cookies", default=DEFAULT_IG_COOKIES,
                    help="Netscape cookies file for Instagram profile enumeration")
    ap.add_argument("--json", action="store_true", help="emit JSON (default)")
    args = ap.parse_args(argv)

    parsed = parse_entry(args.entry, cli_top=args.top, cli_platform=args.platform)
    if args.include:
        parsed["include"] = [t for t in args.include.lower().split(",") if t]
    result = enumerate_entry(parsed, use_cookies=not args.no_cookies,
                             strict_order=args.strict_order, ig_cookies=args.ig_cookies)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
