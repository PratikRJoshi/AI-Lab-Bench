# Channel Enumeration

Give the analyzer a **channel / profile** instead of a single link, and it pulls the **top-N
most-recent** posts/videos/reels/carousels and analyzes each through the normal single-URL
pipeline. Implemented by `channel_enumerator.py` (+ `ig_carousel_scraper.py list-profile` for
Instagram) and a pre-triage **Phase 0 Step 0 — Channel Expansion** in `SKILL.md`.

> Naming note: this skill already uses "Phase -1" for Housekeeping, so channel expansion runs as
> **Phase 0 Step 0** (the first thing Phase 0 does, before Check A), expanding channel entries into
> individual permalinks that then flow through the normal Phase 0 → 1 → 2 pipeline unchanged.

## watch-urls.md examples

```text
## Pending
https://www.youtube.com/@veritasium [channel:5]
https://www.youtube.com/channel/UCxxxx [channel:3 include:videos,shorts]
https://www.instagram.com/nasa/ [channel:5]
https://blog.python.org/ [channel:5]
@hubermanlab [channel:5 platform:youtube]
```

## Directives

| Directive | Meaning |
|---|---|
| `[channel]` / `[channel:N]` | Mark as channel; N = top-N (default 5, hard cap 25) |
| `[top:N]` | Alias for the count |
| `platform:youtube\|instagram\|generic` | Required for bare `@handle`; optional otherwise |
| `include:videos,shorts,streams` | YouTube tabs (default `videos`) |
| propagated: `transcript-only`, `audio-only`, `display-only`, timestamp ranges | applied to each enumerated item |

Conflicting `[channel:5 top:10]` fails the entry. Channel-only directives are consumed (not propagated).

## Running directly

```bash
python3 channel_enumerator.py 'https://www.youtube.com/@veritasium [channel:5]' --json
python3 channel_enumerator.py 'https://www.instagram.com/nasa/' --top 5 --ig-cookies /tmp/url-analyzer/ig-cookies.txt --json
python3 channel_enumerator.py 'https://blog.python.org/' --top 3 --json
```

JSON out (success): `{success, platform, channel_url, handle, requested_n, found_n, ordering, shortfall, items:[{position,url,type,title}], warnings}`. Failure adds `error_code, error`.

## Per-platform behavior

- **YouTube** — `yt-dlp --flat-playlist` on the `/videos` (or `/shorts`,`/streams`) tab, newest-first
  by tab order (`--flat-playlist` omits `upload_date`; multi-tab is tab-grouped unless `--strict-order`).
  Premieres/live-upcoming filtered. RSS fallback via `feeds/videos.xml?channel_id=UC...` (≤15 items).
- **Instagram** — `ig_carousel_scraper.py list-profile <profile> <cookies-netscape.txt> --top N`, which
  scrolls the profile grid and collects `/p/`,`/reel/`,`/tv/` permalinks newest-first. **Requires the
  same Netscape cookies file the skill already exports** in the "Phase 1 prerequisite — export Firefox
  cookies" block (default `/tmp/url-analyzer/ig-cookies.txt`). Pinned posts may break strict order.
- **Generic site** — RSS/Atom discovery (bounded HEAD probes, stop at first hit) → `yt-dlp` generic →
  `/sitemap.xml` (sorted by `lastmod`). Fails clearly if none work.

## Dedup, rate-limits, bookkeeping

- Enumerated permalinks flow through Phase 0 Check A (YouTube video IDs / Instagram post IDs already
  dedup by stable ID; generic falls to Check B).
- Each enumeration call counts as one inter-request delay unit; generic feed-probing is a bounded
  HEAD burst (named exception). Per-item downloads keep the standard 45–75s / caption / cooldown rules.
- Channel reputation (Step 4c) is computed once per channel and reused across its items in the batch.
- The batch Step 7 records a nested channel summary plus one flat per-item line each.

## Failure modes

| `error_code` | Cause | Action |
|---|---|---|
| `parse_error` | conflicting counts / bare handle w/o platform | fix the directive |
| `cookies_missing` | no Netscape cookies file | run the Firefox cookies export prerequisite |
| `login_required` | IG login wall despite cookies | refresh the cookies export |
| `enumeration_failed` | YouTube/generic returned nothing | add individual permalinks manually |
| `not_a_channel` | single-post URL given channel mode | use the channel/profile URL |
