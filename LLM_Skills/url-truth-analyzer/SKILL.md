---
name: url-truth-analyzer
description: Analyzes video/audio/image/article/plain-text content from URLs or local files and performs truth-claim validation. Supports YouTube, Facebook/Instagram (reels and image posts), Twitter/X, LinkedIn videos, news/blog articles (via `[article]` directive), and local plain-text files (via `[plain-text]` directive). For video/audio: transcribes with Whisper or captions. For images: downloads and extracts text via OCR, analyzes visual content. For articles: fetches and extracts the readable body. For plain text: reads the file directly. For medical content, applies EBM SORT analysis with peer-reviewed citations. For general science, validates claims and finds credible supporting or refuting content. Supports transcript-only mode (YouTube captions) and timestamp-range extraction. Use when the user mentions analyzing URLs, truth claims, transcribing videos, checking medical claims, analyzing social media images, analyzing articles, fact-checking a plain-text paragraph, or asks to process the watch-urls.md file.
---

# URL Truth Analyzer

---

## URL directive syntax

Each entry in `## Pending` is a URL, optionally followed by inline directives inside `[...]`. Directives modify *how* the URL is processed; they do not affect the URL itself.

```
# Default — captions-first for YouTube; falls back to audio + Whisper if no captions
https://youtu.be/VIDEO_ID

# Audio-only — skip caption attempt, force audio download + Whisper
https://youtu.be/VIDEO_ID [audio-only]

# Transcript-only — fetch YouTube captions; skip audio download and Whisper entirely
https://youtu.be/VIDEO_ID [transcript-only]

# Timestamp range — process only the specified segment (audio download, trimmed)
https://youtu.be/VIDEO_ID [00:05:00-00:15:00]

# Transcript-only + timestamp range — captions filtered to the specified segment
https://youtu.be/VIDEO_ID [transcript-only 00:05:00-00:15:00]

# Local folder — all images in folder treated as a single post
/Users/pratik.joshi/Downloads/my-carousel-screenshots

# Local folder with optional title (used for slug and analysis heading)
/Users/pratik.joshi/Downloads/my-carousel-screenshots [title: Sugar Myths Carousel]

# Display-only — output analysis in the conversation, skip all file saves and GitHub sync
https://youtu.be/VIDEO_ID [display-only]

# Display-only can combine with other directives
https://youtu.be/VIDEO_ID [display-only transcript-only]

# Article URL — fetch HTML, extract the readable body, skip yt-dlp entirely
https://www.nytimes.com/2026/05/01/health/some-article.html [article]

# Article URL with optional title override (used for slug and analysis heading)
https://example.com/post [article title: My Article Title]

# Plain-text file — read a local .txt file directly, no fetch, no transcription
/Users/pratik.joshi/Downloads/claims-paragraph.txt [plain-text]

# Plain-text file with optional title
/Users/pratik.joshi/Downloads/claims.txt [plain-text title: Sugar Claims Snippet]

# Podcast — Spotify episode (auto-detected by host)
https://open.spotify.com/episode/EPISODE_ID

# Podcast — Apple Podcasts episode (auto-detected by host; resolved via iTunes Lookup → publisher RSS)
https://podcasts.apple.com/us/podcast/SHOW/idDIGITS?i=EPISODE_ID

# Podcast — generic RSS feed; newest episode by default
https://example.com/feed.xml [podcast-rss]

# Podcast — Nth most recent episode from a feed (1 = newest)
https://example.com/feed.xml [podcast-rss episode: 3]

# Force podcast routing on a non-obvious source (e.g. long-form YouTube interview channel)
https://youtu.be/VIDEO_ID [podcast]

# High-stakes long podcast — override default Whisper "medium" with "large-v3"
https://open.spotify.com/episode/EPISODE_ID [whisper-model: large-v3]

# Local audio file — REQUIRES explicit [podcast] opt-in (no implicit routing)
/Users/me/Downloads/episode.mp3 [podcast]
/Users/me/Downloads/episode.m4a [podcast title: My Episode Title]
```

**Directive rules:**
- Directives are placed on the same line as the URL, separated by a space.
- The `[...]` block is stripped before any URL is passed to `yt-dlp` or used for video ID extraction.
- Timestamps use `HH:MM:SS` or `MM:SS` format, separated by a hyphen. Both the start and end must be specified.
- Directives are case-insensitive: `[Transcript-Only]` and `[transcript-only]` are equivalent.
- If no directive is present, YouTube URLs default to **captions-first**: attempt to fetch captions, then fall back to audio download + Whisper if no captions are available. Non-YouTube platforms always use audio download (no captions available).
- **`[audio-only]`**: Forces audio download + Whisper transcription, skipping the caption attempt entirely. Use when auto-generated captions are known to be poor quality or in the wrong language.
- **Local folder paths**: If the entry starts with `/` (absolute path) instead of `http`, it is treated as a local folder containing images. All supported image files (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`) are treated as a single post. The `[transcript-only]` and timestamp directives are ignored for folder entries. **Recursive scanning up to depth 5** (see `RECURSIVE_FOLDER_UPDATE.md` for details). Each image gets a `<slug>-paths.txt` mapping that preserves the original subfolder structure for analysis context.
- **`[display-only]`**: The sub-agent returns the analysis text instead of saving to a file; the parent displays it in the conversation. Skips Step 5 file save (analysis is returned in the sub-agent result instead), Step 6 cleanup still runs, Step 7 `watch-urls.md` update is skipped for this URL, and GitHub sync skips this URL. Useful for quick one-off checks or when the user provides a URL inline rather than via `watch-urls.md`. Can combine with other directives (e.g. `[display-only transcript-only]`). When a URL is provided directly in the user's message (not from `watch-urls.md`), `display-only` is implied automatically.
- **`[article]`**: Treats the URL as an HTML article/blog/news page rather than a video. The skill fetches the page with `curl` (or `WebFetch`) and extracts the readable body using `trafilatura` (preferred) or `pandoc -f html -t plain` (fallback). Skips yt-dlp, captions, audio download, and Whisper entirely. The extracted text becomes the transcript at `/tmp/url-analyzer/<slug>.txt`. The slug is derived from the article's `<title>` tag (or `[article title: ...]` if provided). Dedup uses Check B (slug match) only — Check A is skipped for article URLs. Inter-request delay still applies (the fetch is a server call). `[transcript-only]`, `[audio-only]`, and `[timestamp-range]` are silently ignored for articles.
- **`[plain-text]`**: Treats the entry as a path to a local `.txt` file containing the content to analyze. No network call. The file's contents are copied into `/tmp/url-analyzer/<slug>.txt` and the sub-agent runs Steps 3–6 directly. The slug is derived from the filename basename (without extension) or `[plain-text title: ...]` if provided. Both Check A and the `yt-dlp` part of Check B are skipped — dedup uses local slug match against `~/Documents/truth-analyses/` only. No inter-request delay, no batch cooldown, no retry logic (no server contacted). The path must end in `.txt` and the file must exist; otherwise the entry is marked failed. Other directives are ignored.
- **`[podcast]`**: Forces podcast routing on any URL or local audio path. Used for non-obvious sources (e.g. a long-form YouTube interview channel that the user wants treated as a podcast for long/short auto-routing). For YouTube URLs with `[podcast]`, the existing Mode A/B download still applies — but Step 1.5 (duration probe) and Step 2 Path D (chunked Whisper for long episodes) become active. Auto-detected for Spotify (`open.spotify.com/episode/`) and Apple Podcasts (`podcasts.apple.com/.../id<digits>?i=...`) hosts.
- **`[podcast-rss]`**: Treats the URL as a podcast RSS feed XML. Phase 1 Mode N parses the feed, picks the Nth most recent episode (1 = newest, default; controlled by `[episode: N]`), and downloads the audio enclosure. The slug is derived from the episode title. Check A is skipped; dedup uses (1) normalized feed URL + episode index pre-fetch, then (2) slug match post-resolution. `[transcript-only]`, `[audio-only]`, and `[timestamp-range]` are silently ignored.
- **`[episode: N]`**: Combine with `[podcast-rss]` to select the Nth most recent episode (N is 1-indexed; 1 = newest). Episodes are sorted by `pubDate` (RSS 2.0) or `published`/`updated` (Atom) descending, not by feed order. Default N=1 when omitted.
- **`[podcast title: ...]`**: Slug override for podcast entries, mirroring `[article title: ...]` and `[plain-text title: ...]`.
- **`[whisper-model: <model>]`**: Override the default Whisper model for the long-podcast path (Step 2 Path D). Valid values: `tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`. The default for long podcasts is `medium`; short podcasts always use `small`. When `large-v3` is selected, the chunked-Whisper concurrency cap is forced to 1 (3 GB model × 2 = 6 GB+, would OOM on 16 GB systems).
- **Local audio file paths** (`.mp3`, `.m4a`, `.wav`): REQUIRE explicit `[podcast]` opt-in, mirroring the `[plain-text]` pattern for `.txt` files. Without `[podcast]`, the entry fails Phase 0 triage with a `(failed YYYY-MM-DD — local audio file requires explicit [podcast] directive)` message. Routing priority: `[plain-text] > [article] > [podcast]/podcast-host > absolute-path local folder > URL processing`.
- **`[channel]` / `[channel:N]` / `[top:N]`**: Treat the entry as a **channel/profile** and enumerate its top-N most-recent posts/videos/reels/carousels, then analyze each through the normal pipeline. Handled by **Phase 0 Step 0 — Channel Expansion** (`channel_enumerator.py`). Default N=5, hard cap N=25; a conflicting `[channel:N top:M]` (N≠M) fails the entry. Bare `@handle` requires a `platform:youtube|instagram|generic` hint. `include:videos,shorts,streams` selects YouTube tabs (default `videos`). Per-item directives (`transcript-only`, `audio-only`, `display-only`, timestamp ranges) propagate to each enumerated item; channel-only directives do not. YouTube uses `yt-dlp --flat-playlist`; Instagram uses `ig_carousel_scraper.py list-profile` with the exported Netscape cookies; generic uses RSS/Atom → yt-dlp → sitemap. See `CHANNEL_ENUMERATION.md`.

**Directive parser (extension for `key: value` syntax)**: Existing directives are either bare keywords (`transcript-only`, `audio-only`, `display-only`) or implicit timestamp patterns (`00:05:00-00:15:00`). The new `key: value` form (`[episode: N]`, `[whisper-model: large-v3]`, `[podcast title: My Episode]`) requires **targeted regex captures**, not naive `:` splitting — naive splitting breaks `[podcast title: My Episode Title]` (multi-word value) and confuses with timestamp tokens. Use the following parse order inside the directive block:

```python
import re
def parse_directives(block):
    flags = {}
    # 1. Multi-word title captures.
    # Prefixed variants ([podcast|article|plain-text] title: ...) first.
    m = re.search(r'(?:podcast|article|plain-text)\s+title:\s*(.+?)(?=\s+(?:transcript-only|audio-only|display-only|podcast|article|plain-text|episode:|whisper-model:)|$)', block, re.I)
    if m:
        flags['title'] = m.group(1).strip()
    else:
        # Generic bare title: (local-folder back-compat)
        m = re.search(r'(?:^|\s)title:\s*(.+?)(?=\s+(?:transcript-only|audio-only|display-only|podcast|article|plain-text|episode:|whisper-model:)|$)', block, re.I)
        if m: flags['title'] = m.group(1).strip()
    # 2. episode: N (digits only)
    m = re.search(r'episode:\s*(\d+)', block, re.I)
    if m: flags['episode'] = int(m.group(1))
    # 3. whisper-model: <token> (no spaces)
    m = re.search(r'whisper-model:\s*([A-Za-z0-9._-]+)', block, re.I)
    if m: flags['whisper_model'] = m.group(1)
    # 4. Bare keyword flags
    for kw in ('podcast-rss', 'podcast', 'transcript-only', 'audio-only', 'display-only', 'article', 'plain-text'):
        if re.search(rf'\b{re.escape(kw)}\b', block, re.I):
            flags[kw.replace('-','_')] = True
    # 5. Timestamp range (last, since it would match digits)
    m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)-(\d{1,2}:\d{2}(?::\d{2})?)', block)
    if m: flags['range'] = (m.group(1), m.group(2))
    return flags
```

Validate `whisper-model` value against the whitelist above; on miss, warn and fall back to `medium`.

---

## Workflow overview

**Terminology:**
- **Mode** = routing variant in Phase 1 Step 1 (download/fetch strategy). Modes are lettered A, B, C, D, E, F, H, I, K, L, M, N, O (G was retired in commit `16a3050`).
- **Path** = extraction variant in Phase 1 Step 2 / Phase 2 (transcript-source-specific processing). Paths are A (captions VTT), B (Whisper), C (OCR + visual), D (chunked Whisper for long podcasts).
- **Phase** = a workflow stage (-1 Housekeeping, 0 Triage, 1 Download/Transcribe/Dispatch, 2 Analyze).

**Inline URL auto-detection**: When the user provides a URL directly in their message (not from `watch-urls.md`), treat it as `DISPLAY_ONLY=true` automatically. Skip Phase 0 dedup checks (no `watch-urls.md` to read), run Phase 1 + Phase 2 normally, display the analysis in the conversation, clean up temp files, and stop. No files are written, no `watch-urls.md` is updated, no GitHub sync runs.

**Inline plain-text auto-detection**: When the user pastes a block of plain text in their message (not a URL, not a path) and asks for truth analysis, treat it as `CONTENT_TYPE=plain-text` with `DISPLAY_ONLY=true` automatically. Write the pasted text to `/tmp/url-analyzer/inline-<timestamp>.txt`, dispatch a single sub-agent for Steps 3–6, display the analysis in the conversation, then clean up. No `watch-urls.md` entry is created. The slug for the temp file is `inline-<YYYYMMDD-HHMMSS>`. If the user provides an explicit title in their message, use that for the slug instead.

**Inline article URL auto-detection**: When an inline URL is clearly an article (e.g. domains like nytimes.com, medium.com, substack.com, wordpress.com, blog hosts) and not a known video/social platform, treat it as if `[article]` were specified. If ambiguous, ask the user once whether to treat it as an article or attempt video extraction.

Processing happens in **four phases** plus post-processing. Phase -1 (housekeeping) archives old data. Phase 0 is instant and local. Phase 1 pipelines server calls with local transcription **and dispatches sub-agents for analysis as each transcript becomes ready**. Phase 2 runs in parallel across sub-agents.

### Phase -1 — Housekeeping (automatic, runs before Phase 0)

Runs at the start of every `process watch-urls.md` invocation. Archives processed entries and analysis files older than 30 days. Skipped entirely for inline URL auto-detection (no `watch-urls.md` involved).

### Phase 0 — Batch triage (instant, local)

Before any server calls, run a single pass over ALL pending URLs:

0. **Channel expansion (Step 0)**: if any entry is a channel/profile (`[channel:N]` or a channel-shaped URL), enumerate its top-N most-recent permalinks via `channel_enumerator.py` and inject them into the pending list before triage. Channel entries themselves are never downloaded.
1. Parse directives for every entry
2. Run Check A (video ID match) for every URL entry that doesn't have the `[article]` or `[plain-text]` directive, against the `## Processed` list. For `[article]` entries, Check A is an exact URL string match against processed URLs. For `[plain-text]` entries, Check A is skipped entirely.
3. Partition into seven lists:
   - `DUPLICATES[]` — Check A matched; record for batch `watch-urls.md` update, no further processing
   - `NEEDS_PROCESSING[]` — video/audio/image URL entries requiring download + analysis
   - `LOCAL_FOLDERS[]` — local folder entries (skip Phase 1 downloads, dispatch sub-agents directly)
   - `ARTICLES[]` — entries with `[article]` directive (fetch HTML in Phase 1, then dispatch sub-agent)
   - `PLAIN_TEXT[]` — entries with `[plain-text]` directive (no fetch, dispatch sub-agent directly)
   - `PODCASTS[]` — entries with `[podcast]` / `[podcast-rss]` directive OR auto-detected podcast host (Spotify, Apple Podcasts) OR URL path ending in `.xml`/`.rss`/`/feed` (root-tag confirmed in Mode N). Phase 1 routes to Mode L (Spotify), Mode M (Apple), Mode N (RSS), or Mode O (local audio).
   - `MALFORMED[]` — entries that look like local audio (`.mp3`/`.m4a`/`.wav` absolute paths) but lack the required `[podcast]` directive. Mirrors the `[plain-text]` opt-in pattern. These are failed immediately with a clear message.

Phase 0 makes zero server calls. Duplicates are resolved instantly.

### Phase 1 — Download + transcribe + dispatch (rate-limited, pipelined)

For each URL in `NEEDS_PROCESSING`, **one at a time, in order**:

1. Step 0b: Check B title/slug match (server call — `yt-dlp --get-title`). **Skipped automatically** for URLs whose video ID was already extracted by Check A in Phase 0 (Instagram post IDs, Facebook reel IDs, YouTube video IDs, etc.) — Check B only runs when Check A could not produce a stable identifier (e.g. an unknown platform).
2. Step 1: Download content — captions-first for YouTube (lightweight), fall back to audio if no captions found. Other platforms use audio download directly.
3. Step 2 (pipelined): Immediately after download, start transcription:
   - If captions were fetched → convert VTT to plain text inline (instant, ~1s)
   - If audio was downloaded → spawn Whisper as a **background process** so it runs during the mandatory inter-request delay
4. **Sub-agent dispatch**: Once the transcript `.txt` is ready, immediately spawn a `generalPurpose` sub-agent for Phase 2 analysis (Steps 3–6). The parent does **not** wait for the sub-agent — it continues to the next download.
5. Inter-request delay (45–75s randomized) — Whisper runs concurrently during this wait; analysis sub-agents also run concurrently.

Phase 1 produces a transcript `.txt` file per URL and dispatches an analysis sub-agent per URL. No concurrency cap on sub-agents — all are spawned immediately.

**Local folder entries** skip Phase 1 downloads (no server calls). Their images are staged into `/tmp/url-analyzer/` and a sub-agent is dispatched immediately for OCR + analysis (Steps 2C, 3–6). Step 0b runs a local-only dedup variant (slug match against `~/Documents/truth-analyses/` filenames).

**Article entries** run Step 0b normally (slug from `<title>` tag), then Mode H in Phase 1 (HTML fetch + readable-body extraction → `/tmp/url-analyzer/<slug>.txt`). Inter-request delay applies. Sub-agent dispatched after extraction.

**Plain-text entries** skip Phase 1 entirely (no fetch). The file is copied to `/tmp/url-analyzer/<slug>.txt` via Mode K, and a sub-agent is dispatched immediately for Steps 3–6. Step 0b runs a local-only dedup variant (slug match against `~/Documents/truth-analyses/` filenames). No rate-limit counters consumed.

**Podcast entries** run Mode L (Spotify), Mode M (Apple Podcasts → iTunes Lookup → RSS), Mode N (generic RSS feed), or Mode O (local audio) in Phase 1. After download, **Step 1.4** (timestamp trim if `[timestamp-range]` is supplied) and **Step 1.5** (duration probe via `ffprobe`) run before Step 2. Episodes over 30 minutes route to **Step 2 Path D** (chunked Whisper with `medium` model by default, `large-v3` opt-in via `[whisper-model: large-v3]`, parallelism capped at 2 — or 1 for `large-v3` to avoid OOM). Episodes ≤30 minutes route to standard Path B with the existing `small` model. Mode L/M/N consume the standard inter-request delay budget; Mode O (local audio) does not.

### Phase 2 — Analyze + save (parallel via sub-agents)

Each sub-agent runs Steps 3–6 independently and concurrently:

1. Step 3: Classify content (Medical vs General Science)
2. Step 4: Analyze (EBM SORT or Claim Validation) + channel reputation
3. Step 5: Save analysis file — or return analysis text if `DISPLAY_ONLY=true`
4. Step 6: Cleanup temporary files for this URL only

Sub-agents do **not** run Step 7. Each sub-agent writes its own unique analysis file (no conflicts). On completion, each sub-agent returns a structured result to the parent.

### Result collection + batch update (parent, after all sub-agents complete)

After all Phase 1 downloads finish and all sub-agents return:

1. Collect results from all sub-agents (success/failure status, analysis file paths)
2. **Step 7 (batch)**: Update `watch-urls.md` once — remove all processed URLs from `## Pending`, append all entries to `## Processed` in a single edit. This avoids race conditions on the shared file.
3. For `DISPLAY_ONLY` sub-agents: display their returned analysis text in the conversation.

### Post-processing — after result collection

1. Sync to GitHub: commit and push new analysis files from `~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/` to the remote repository

---

**Progress reporting**: Output status messages at each phase transition:
```
📋 Phase 0: Triaging N URLs... (X duplicates, Y to download, Z local folders)
🔄 Phase 1 [1/Y]: Downloading + transcribing <URL> (captions-first)
   ⏳ Whisper running in background during inter-request delay...
   🚀 Sub-agent dispatched for analysis of <URL>
🔄 Phase 1 [2/Y]: Downloading + transcribing <URL>
   🚀 Sub-agent dispatched for analysis of <URL>
✓ Phase 1 complete: Y downloaded, Y sub-agents running
⏳ Awaiting N sub-agents... (M completed, K in progress)
📋 All sub-agents complete. Batch-updating watch-urls.md...
✅ All URLs processed. Syncing to GitHub...
```

Update progress after each major step within each phase.

---

## Phase -1: Housekeeping (automatic, before Phase 0)

**Progress indicator**: `🧹 Housekeeping: Archiving entries older than 30 days...`

Runs once at the start of every `process watch-urls.md` invocation. Skipped for inline URL auto-detection.

### Step 1: Archive old processed entries from watch-urls.md

1. Parse every entry under `## Processed` in `watch-urls.md`.
2. Extract the date from each entry (the `YYYY-MM-DD` in `analyzed YYYY-MM-DD` or `failed YYYY-MM-DD` or `duplicate of`).
   - For duplicate entries without an explicit date, use the date from the original analysis file path (e.g. `2026-03-10` from `truth-analyses/2026-03-10-*.md`).
3. Compare each date to today minus 30 days.
4. For each entry older than 30 days:
   a. Append it to `LLM_Skills/url-truth-analyzer/watch_urls_archive.md` under the appropriate `## YYYY-MM` month header.
   b. Remove it from `watch-urls.md`.
5. The archive file is append-only. If it does not exist, create it with:
   ```markdown
   # Watch URLs Archive
   
   Processed entries archived from watch-urls.md (older than 30 days).
   
   ---
   ```
6. Month headers (`## YYYY-MM`) are created in chronological order. New entries append under the matching header. If the header does not exist yet, create it at the correct chronological position.

### Step 2: Archive old analysis files

1. Scan `~/Documents/truth-analyses/` for files matching `YYYY-MM-DD-*.md` where the date is older than 30 days.
2. For each old file:
   a. Create `~/Documents/truth-analyses/archive/YYYY-MM/` if it does not exist.
   b. Move the file into the month subdirectory.
3. Repeat for `~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/`:
   a. Create `truth-analyses/archive/YYYY-MM/` if it does not exist.
   b. Use `git mv` to move files (preserves git history).

### Step 3: Commit housekeeping changes

If any files were moved or entries archived:
1. Stage all changes: `git add -A LLM_Skills/url-truth-analyzer/truth-analyses/ LLM_Skills/url-truth-analyzer/watch_urls_archive.md LLM_Skills/watch_urls.md`
2. Commit: `Housekeeping: archive analyses older than 30 days`
3. Do **not** push yet — the post-processing GitHub sync will push this commit along with any new analyses.

If nothing is older than 30 days, report `🧹 Housekeeping: Nothing to archive.` and skip to Phase 0.

### Reporting

```
🧹 Housekeeping complete:
   📦 Archived N processed entries from watch-urls.md
   📦 Moved M analysis files to archive/
   📦 Oldest archived: YYYY-MM-DD
```

---

## Phase 0: Batch triage (instant, local)

**Progress indicator**: `📋 Phase 0: Triaging N URLs...`

Before any server calls, run a single pass over ALL pending entries in `## Pending`:

### Phase 0 Step 0: Channel Expansion (runs first, only if channel entries exist)

**Progress indicator**: `📡 Phase 0 Step 0: Expanding C channel(s)...`

A **channel entry** is a `## Pending` line marked with `[channel]`/`[channel:N]`/`[top:N]`, or a
channel-shaped URL — YouTube `/@name`, `/c/name`, `/user/name`, `/channel/UC...`; Instagram
`instagram.com/<user>/` (a single profile segment); or a bare `@handle` with a `platform:` hint. A
single post/video URL (`watch?v=`, `youtu.be/`, `/shorts/ID`, `instagram.com/p|reel|tv/ID`) is NOT a
channel.

For each channel entry, enumerate its top-N most-recent permalinks (newest-first), then inject those
permalinks into the pending list so the rest of Phase 0 (Check A, partitioning) and Phase 1/2 process
them as ordinary single URLs. The channel entry itself is never downloaded.

> Instagram channels require the Netscape cookies file exported in the **"Phase 1 prerequisite — export
> Firefox cookies"** block. If any Instagram channel entry is present, run that export block now (before
> enumeration) so `/tmp/url-analyzer/ig-cookies.txt` exists.

```bash
python3 ~/.claude/skills/url-truth-analyzer/channel_enumerator.py '<ENTRY incl. directives>' \
  --ig-cookies /tmp/url-analyzer/ig-cookies.txt --json
# Overrides: --top N, --platform youtube|instagram|generic, --include videos,shorts, --strict-order
```

- Per platform: YouTube → `yt-dlp --flat-playlist`; Instagram → `ig_carousel_scraper.py list-profile`
  (cookies); generic → RSS/Atom → `yt-dlp` generic → sitemap.
- On `success: true`: take `items[].url` (newest-first, capped at N) and add each as a pending entry,
  carrying the inherited per-item directives and remembering the channel (`CHANNEL_URL`,
  `CHANNEL_PLATFORM`, `CHANNEL_HANDLE`) for Step 4c reuse and Step 7 bookkeeping. Expanded permalinks
  live only in the in-memory pending list — do NOT write them into `## Pending`. A re-run is safe
  because Check A dedups anything already analyzed.
- On `success: false`: record the channel entry as a failed expansion (see Step 7) and continue.
  Common `error_code`s: `parse_error` (conflicting counts / bare handle without `platform:`),
  `cookies_missing` / `login_required` (Instagram — export/refresh cookies), `enumeration_failed`
  (generic with no feed/sitemap). If `found_n < requested_n`, process all found and note the shortfall.
- Rate-limit: each enumeration call is ONE server interaction (see the channel-enumeration exception in
  "Inter-request delay"). Inline/`[display-only]` channel entries make every expanded item display-only.

Report: `📋 Phase 0 Step 0 complete: C channel(s) → M permalink(s) queued (S shortfall, F failed).`

See `CHANNEL_ENUMERATION.md` for full directive and platform details.

### Phase 0 Step 1: Parse all directives

For every pending entry, run Sub-step 0a (directive parsing — see below) to extract the clean URL and any mode flags.

### Phase 0 Step 2: Run Check A for all URLs

Extract the video ID from each pending URL using these rules:

| URL pattern | Video ID extraction |
|---|---|
| `youtube.com/watch?v=ID` | value of `v=` query parameter |
| `youtu.be/ID` | path segment after `youtu.be/` |
| `m.youtube.com/watch?v=ID` | value of `v=` query parameter |
| `youtube.com/shorts/ID` | path segment after `/shorts/` |
| `m.youtube.com/shorts/ID` | path segment after `/shorts/` |
| `dms.licdn.com/playlist/vid/dash/ID/...` | 4th path segment (e.g. `D4D05AQEnN8uEJr57uA`) |
| `facebook.com/reel/ID` | path segment after `/reel/` (e.g. `862786000111258`) |
| `facebook.com/watch/?v=ID` | value of `v=` query parameter |
| `fb.watch/ID` | path segment after `fb.watch/` |
| `open.spotify.com/episode/ID` | path segment after `/episode/` |
| `podcasts.apple.com/.../id<digits>?i=ID` | value of `i=` query parameter |
| RSS feed URLs (`.xml` / `.rss` / `/feed`) | no video ID — Check B by slug match only |
| Other platforms | no video ID — goes to `NEEDS_PROCESSING` for Check B |

**Note**: Local audio files (Mode O) skip Check A entirely; dedup uses Check B slug match only — same as Mode K (plain-text).

Then parse every processed entry in `## Processed` in `watch-urls.md` **and** in `LLM_Skills/url-truth-analyzer/watch_urls_archive.md` (if it exists) and extract the video ID from each processed URL using the same rules. This ensures dedup works even after old entries have been archived by Phase -1.

**Skip processed entries marked `failed`** when building the dedup index. A failed entry means the user is allowed (and likely intends) to retry the same URL on a subsequent run; treating it as a duplicate silently drops the retry. Only `analyzed YYYY-MM-DD` and `duplicate of` entries count for dedup.

For each pending URL whose video ID matches any non-failed processed URL's video ID (from either file) → add to `DUPLICATES[]` with the matching processed entry (URL + analysis file path).

### Phase 0 Step 3: Partition entries

Classify each pending entry into one of five lists:

- **`DUPLICATES[]`** — Check A matched a processed entry. These are done — write their Step 7 entries immediately (duplicate format).
- **`PLAIN_TEXT[]`** — Entry has `[plain-text]` directive. Skips Phase 1 fetching entirely; sub-agent dispatched after Mode K copy.
- **`ARTICLES[]`** — Entry has `[article]` directive. Skips yt-dlp; Phase 1 runs Mode H (HTML fetch + body extraction), then sub-agent.
- **`PODCASTS[]`** — Entry has `[podcast]` / `[podcast-rss]` directive OR matches a podcast host (Spotify, Apple Podcasts) OR has a URL path ending in `.xml`/`.rss`/`/feed`. Phase 1 routes to Mode L (Spotify), Mode M (Apple Podcasts), Mode N (RSS — root-tag confirmed during fetch), or Mode O (local audio). Step 1.5 (duration probe) then classifies the episode as short (≤30 min, Whisper `small`) or long (>30 min, chunked Whisper `medium`/`large-v3` via Path D).
- **`MALFORMED[]`** — Entry is an absolute path ending in `.mp3`/`.m4a`/`.wav` (case-insensitive) but lacks the required `[podcast]` directive. Failed immediately with `(failed YYYY-MM-DD — local audio file requires explicit [podcast] directive; without it the file would be treated as a plain folder and fail)`. Mirrors the `[plain-text]` opt-in pattern.
- **`LOCAL_FOLDERS[]`** — Entry starts with `/` and is not an `http` URL (and has no `[plain-text]` / `[podcast]` directive and no audio extension). These skip Phase 1 entirely.
- **`NEEDS_PROCESSING[]`** — Everything else (video/audio/image URLs). These enter Phase 1 for Check B + download + transcription.

**Routing priority** when multiple conditions could match: `[plain-text]` > `[article]` > `[podcast]` / podcast-host > absolute-path local folder > URL processing. A `.txt` file path without `[plain-text]` is treated as a (likely empty) folder and will fail validation; a `.mp3`/`.m4a`/`.wav` path without `[podcast]` is routed to `MALFORMED[]` for clear feedback — both behaviors are intentional, since the user opted not to auto-route.

### Sub-step — In-batch dedup (post-Step 3)

Two-stage dedup against already-processed entries (Step 2 above) AND against other entries in the current batch:

- **Stage A (pre-download, immediate)** — for each remaining entry, compute a "stable ID":
  - Spotify: episode ID (path segment after `/episode/`)
  - Apple: `i=` GUID query parameter value
  - Local audio (Mode O): canonicalized absolute file path (via `realpath`)
  - RSS: normalized feed URL + episode index (lower scheme/host, strip trailing slashes, drop tracking params)
  
  If two pending entries share the same stable ID, keep only the first occurrence; emit a `(duplicate of <first-sibling-URL> earlier in this batch)` Step 7 entry for the others.
- **Stage B (post-resolution, just before enclosure download)** — applied only to RSS entries: dedup on the resolved episode title slug. If Mode N resolves two distinct feed URLs to the same episode (rare but possible for cross-posted shows), the second is dropped before enclosure download.

### Phase 0 Step 4: Record duplicates for batch update

For each entry in `DUPLICATES[]`, add to the `RESULTS[]` collection with status `duplicate` and the matching processed entry details. These are written to `watch-urls.md` later in the parent's batch Step 7, not immediately.

Report:
```
📋 Phase 0 complete: N total entries triaged
   ⚠️  X duplicate(s) resolved instantly (Check A video ID match or in-batch dedup)
   📥 Y URL(s) queued for Phase 1 (download + transcribe + dispatch)
   📁 Z local folder(s) queued for sub-agent dispatch (OCR + analysis)
   📰 A article(s) queued for Phase 1 (HTML fetch + body extraction)
   📝 B plain-text file(s) queued for sub-agent dispatch (no fetch)
   🎙️  C podcast(s) queued for Phase 1 (Spotify/Apple/RSS/local audio + long/short auto-routing)
   ❌ D malformed entry(ies) (local audio without [podcast] directive — failed immediately)
```

---

## Step 0b: Parse directives + Check B title dedup (Phase 1 — per URL)

**Progress indicator**: `⏳ Step 0b: Parsing directives, checking title dedup...`

### Sub-step 0a: Parse URL directives

Before anything else, check whether the pending line contains a `[...]` directive block.

1. Split the line on the first ` [` — everything before it is the **clean URL**; everything inside `[...]` is the **directive string**.
2. Parse the directive string with the regex-based parser shown in the **Directive rules** section above (case-insensitive). Set mode flags accordingly:
   - `transcript-only` → `TRANSCRIPT_ONLY=true`
   - timestamp pattern `HH:MM:SS-HH:MM:SS` (or `MM:SS-MM:SS`) → extract `START`/`END`, set `TIMESTAMP_RANGE=true`
   - `audio-only` → `AUDIO_ONLY=true`
   - `display-only` → `DISPLAY_ONLY=true`
   - `podcast` → `PODCAST_FORCED=true` (force podcast routing on any URL/path)
   - `podcast-rss` → `PODCAST_RSS=true` (route to Mode N)
   - `episode: N` → `EPISODE_INDEX=N` (default 1 = newest)
   - `whisper-model: <model>` → `WHISPER_MODEL_FROM_DIRECTIVE=<model>` (validated against whitelist `tiny|base|small|medium|large|large-v2|large-v3`; on miss, warn + fall back to `medium`)
   - `podcast title: ...` / `article title: ...` / `plain-text title: ...` / bare `title: ...` → `TITLE_OVERRIDE`
   - Multiple directives can be present in the same block, e.g. `[transcript-only 00:05:00-00:15:00]` or `[podcast-rss episode: 3]`
3. Use the **clean URL** (without the directive block) for all subsequent processing.

Report the parsed mode at the start of the URL:
```
🔄 Processing URL N of N: <clean URL>
   Mode: [transcript-only] [00:05:00–00:15:00]   ← only shown when directives are present
```

### Sub-step 0a-article: Detect article entry

After parsing directives, if the entry has the `[article]` directive:

1. Set `CONTENT_TYPE=article` and `TRANSCRIPT_SOURCE=html`.
2. Skip Check A (no video ID).
3. Slug source: if `[article title: ...]` is in the directive block, slugify that. Otherwise, defer slug derivation to Phase 1 Mode H (which fetches the `<title>` tag from the HTML).
4. Run Check B (local slug match against `~/Documents/truth-analyses/`) only after the slug is known (in Phase 1, just before fetching the body).
5. Continue to Phase 1 Mode H — do NOT fall through to the local-folder check below.

Progress indicator: `⏳ Step 0b: Article URL detected, will fetch + extract body in Phase 1...`

### Sub-step 0a-plaintext: Detect plain-text file entry

After parsing directives, if the entry has the `[plain-text]` directive:

1. Set `CONTENT_TYPE=plain-text` and `TRANSCRIPT_SOURCE=plain-text`.
2. Validate the path:
   - If it does not start with `/` → mark as failed: `(failed YYYY-MM-DD — plain-text entry must be an absolute path)`.
   - If the path does not exist OR is not a regular file → mark as failed: `(failed YYYY-MM-DD — file does not exist or is not a regular file)`.
   - If the path does not end in `.txt` (case-insensitive) → mark as failed: `(failed YYYY-MM-DD — plain-text entry must be a .txt file)`.
   - If the file is empty (zero bytes) → mark as failed: `(failed YYYY-MM-DD — plain-text file is empty)`.
3. Extract slug:
   - If `[plain-text title: ...]` is present, slugify the title.
   - Otherwise, slugify the filename basename without extension (e.g., `/path/claims-paragraph.txt` → `claims-paragraph`).
4. Skip Check A entirely. Run Check B (local slug match against `~/Documents/truth-analyses/`).
5. Continue to Phase 1 Mode K — do NOT fall through to the local-folder check below.

Progress indicator: `⏳ Step 0b: Plain-text file detected, checking for duplicates...`

### Sub-step 0a-podcast: Detect podcast entry

After parsing directives, route to a podcast mode if any of the following holds:

1. **Auto-detection by host** (URL entries only):
   - `open.spotify.com/episode/<id>` → `CONTENT_TYPE=podcast`, `PODCAST_MODE=L` (Spotify). Set `PODCAST_ID=<id>` from the path segment. Skip Step 0b `--get-title` check (Mode L's combined probe+download produces the title; dedup runs post-download by slug).
   - `podcasts.apple.com/.../id<digits>?i=<episode-id>` → `CONTENT_TYPE=podcast`, `PODCAST_MODE=M` (Apple). Extract `APPLE_PODCAST_ID=<digits>` from the `id<digits>` segment and `EP_GUID=<episode-id>` from the `i=` query parameter.
2. **Auto-detection by URL path** (URL entries only): URL path ends in `.xml`, `.rss`, or `/feed` → `CONTENT_TYPE=podcast`, `PODCAST_MODE=N` (RSS, deferred root-tag confirmation during fetch).
3. **Explicit directives**:
   - `[podcast-rss]` → `PODCAST_MODE=N` regardless of URL path.
   - `[podcast]` on a YouTube URL → keep `CONTENT_TYPE=video` for download (Mode A/B), but set `PODCAST_LENGTH_CHECK=true` so Step 1.5 still runs after download to potentially trigger Path D.
   - `[podcast]` on a local audio path (`.mp3`/`.m4a`/`.wav`) → `PODCAST_MODE=O`.
4. **Local audio validation** (when `PODCAST_MODE=O`):
   - If the path does not start with `/` → fail: `(failed YYYY-MM-DD — local audio entry must be an absolute path)`.
   - If the path does not exist OR is not a regular file → fail: `(failed YYYY-MM-DD — local audio file does not exist or is not a regular file)`.
   - If the extension is not `.mp3`/`.m4a`/`.wav` (case-insensitive) → fail: `(failed YYYY-MM-DD — local audio entry must have .mp3, .m4a, or .wav extension)`.
   - If the file is empty (zero bytes) → fail: `(failed YYYY-MM-DD — local audio file is empty)`.
5. **Malformed local audio (no `[podcast]` directive)**: If the entry is an absolute path ending in `.mp3`/`.m4a`/`.wav` but `[podcast]` is NOT present → add to `MALFORMED[]` with: `(failed YYYY-MM-DD — local audio file requires explicit [podcast] directive)`. Do not run Step 0b or dispatch a sub-agent.
6. Extract slug:
   - For Mode L/M/N: deferred until after title resolution in Phase 1 (use episode-ID or feed-hash temp naming meanwhile).
   - For Mode O: `[podcast title: ...]` if supplied, otherwise the filename basename without extension.
7. Dedup:
   - Mode L: Check A by Spotify episode ID (path segment after `/episode/`); Check B by slug post-download.
   - Mode M: Check A by Apple `i=` GUID; Check B by slug post-resolution.
   - Mode N: Check A skipped; Check B by slug post-resolution.
   - Mode O: Check A skipped; Check B by slug match against `~/Documents/truth-analyses/`.
8. Continue to Phase 1 Mode L / M / N / O — do NOT fall through to the local-folder check below.

Progress indicator: `⏳ Step 0b: Podcast entry detected (mode: L|M|N|O), checking for duplicates...`

### Sub-step 0a-local: Detect local folder entry

After parsing directives, check if the clean entry (after stripping any `[...]` directive) starts with `/` and does NOT start with `http`. If so, this is a local folder entry:

1. Set `CONTENT_TYPE=local-folder` and `TRANSCRIPT_SOURCE=ocr`.
2. Validate the path:
   - If the path does not exist OR is not a directory → mark as failed in `RESULTS[]`: `(failed YYYY-MM-DD — path does not exist or is not a directory)` and skip this entry (no sub-agent dispatch).
3. **Check folder depth** (NEW):
   - Recursively scan the folder tree to find the maximum nesting depth
   - Use this bash command to check depth:
     ```bash
     MAX_DEPTH=$(find /path/to/folder -type d -printf '%d\n' 2>/dev/null | sort -rn | head -1)
     BASE_DEPTH=$(echo "/path/to/folder" | tr -cd '/' | wc -c)
     RELATIVE_DEPTH=$((MAX_DEPTH - BASE_DEPTH))
     ```
   - If `RELATIVE_DEPTH > 5` → mark as failed in `RESULTS[]`: `(failed YYYY-MM-DD — folder structure exceeds maximum depth of 5 levels. Found: N levels)` and skip this entry (no sub-agent dispatch).
   - Report depth in progress indicator: `⏳ Step 0b: Local folder detected (depth: N levels), checking for duplicates...`
4. **Scan for supported image files recursively**:
   - Look for files with extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` (case-insensitive)
   - Scan recursively up to depth 5 using:
     ```bash
     find /path/to/folder -maxdepth 5 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.webp" \)
     ```
   - If no supported image files found → mark as failed in `RESULTS[]`: `(failed YYYY-MM-DD — no supported image files found in folder tree)` and skip this entry (no sub-agent dispatch).
   - Report image count and distribution: `✓ Found N images across M subfolders`
5. Extract slug:
   - If `[title: ...]` directive is present, slugify the title text
   - Otherwise, slugify the folder basename (e.g., `/path/to/my-carousel-images` → slug `my-carousel-images`)
6. For dedup, run Check B only (local slug match against `~/Documents/truth-analyses/` filenames). Skip Check A entirely. No `yt-dlp --get-title` network call is made.

Progress indicator for local folder: `⏳ Step 0b: Local folder detected (depth: N levels, M images), checking for duplicates...`

If this is NOT a local folder entry, continue with the normal URL duplicate check below.

### Check B — Title/slug match (Phase 1 — server call)

> Check A (video ID match) has already run for all URLs in Phase 0. Only URLs that passed Check A without a match reach this step.

To check for title-based duplicates, run:

```bash
yt-dlp --get-title '<PENDING_URL>'
```

> **Rate-limit note**: This command contacts the server. It counts as one server request toward the inter-request delay budget (see Step 1). After this call completes, apply the same 45–75 second randomized delay before the next server call (whether that is another title lookup or a download). The retry/backoff rules from Step 1 also apply if this command returns a rate-limit error.

Slugify the returned title: lowercase, replace spaces and special characters with hyphens, strip leading/trailing hyphens.

Then check whether any file in `~/Documents/truth-analyses/` has a filename containing that slug:

```bash
ls ~/Documents/truth-analyses/ | grep -i "<slug>"
```

If a matching file exists → **duplicate detected**. Note the matched filename and add a `duplicate` entry to `RESULTS[]`. Do not dispatch a sub-agent.

### If duplicate detected

Report:
```
⚠️  Duplicate content detected for URL N of N: <PENDING_URL>
    Already analyzed as: truth-analyses/<existing-file>.md
    Skipping transcription — will link to existing analysis.
```

Add a `duplicate` entry to `RESULTS[]` with the matched file info. Do not dispatch a sub-agent — skip directly to the next URL's download.

### If no duplicate found

Report `✓ Step 0b: No duplicate found — proceeding with download.` and continue to Step 1.

---

## Phase 1 Step 1: Download content (rate-limited, pipelined with Phase 1 Step 2)

All server calls in this step are subject to the inter-request delay and exponential backoff rules described at the end of this section.

### Phase 1 prerequisite — process-singleton guard (mandatory)

Before ANY writes (including the `> $MANIFEST` truncation that orchestrators like `phase1-v3.sh` perform at startup), the orchestrator MUST acquire a lock and refuse to start if another Phase 1 instance is already running. The 2026-05-23 batch run had three concurrent `phase1-v3.sh` processes interleaving writes to `manifest.tsv`, producing torn rows and double-dispatched sub-agents.

Use an atomic `mkdir` lockdir + PID-liveness check (the `flock(1)` command-line utility is not installed on macOS by default, so we cannot rely on it):

```bash
LOCKDIR=/tmp/url-analyzer/phase1.lockdir

acquire_lock() {
  if mkdir "$LOCKDIR" 2>/dev/null; then
    echo $$ > "$LOCKDIR/pid"
    trap 'rm -rf "$LOCKDIR"' EXIT
    return 0
  fi
  return 1
}

if ! acquire_lock; then
  HOLDER=$(cat "$LOCKDIR/pid" 2>/dev/null)
  if [ -n "$HOLDER" ] && kill -0 "$HOLDER" 2>/dev/null; then
    echo "❌ Another Phase 1 run is in progress (PID $HOLDER, lock: $LOCKDIR). Refusing to start." >&2
    exit 2
  else
    # Stale lock from a dead/killed process — clean up and retry once
    echo "⚠️  Stale lock from dead PID $HOLDER; removing and acquiring." >&2
    rm -rf "$LOCKDIR"
    acquire_lock || { echo "❌ Could not acquire lock after stale-lock cleanup." >&2; exit 2; }
  fi
fi

# Lock held. From this point on, all per-URL work — including the initial
#   > $MANIFEST
# truncation — is safe against concurrent writers.
```

This pattern works on macOS, Linux, and any POSIX system without external dependencies. The lock is released on clean exit, `kill <signal>`, or even `kill -9` (the EXIT trap doesn't fire on -9, but the next invocation's PID-liveness check detects the stale lock and recovers automatically).

If using a Python wrapper instead of bash, the equivalent guard is `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` held for the lifetime of the wrapper process — POSIX `fcntl.flock` IS available on macOS even though the `flock(1)` command-line utility is not.

### Phase 1 prerequisite — export Firefox cookies (one-time per batch)

If any Instagram URL is in the batch, export the user's Firefox Instagram cookies once before the per-URL loop. The cookies file is used by both `yt-dlp` (via `--cookies-from-browser firefox` natively) AND the authenticated Playwright scraper in Mode F (which loads the Netscape-format file directly).

```bash
mkdir -p /tmp/url-analyzer
# Use ANY known-good IG post URL from your current batch as the cookie-export trigger.
# (yt-dlp's --cookies side effect runs even though we discard the metadata print.)
# DO NOT hard-code a specific post ID — that post could be deleted, made private, or
# coincidentally collide with a batch slug. Pull from the first IG URL in the batch.
ANY_IG_POST_URL="${1:-https://www.instagram.com/}"   # caller passes the first IG URL; bare homepage works as a fallback but yt-dlp will print "Unsupported URL" — that's harmless, cookies still export
yt-dlp --cookies-from-browser firefox --cookies /tmp/url-analyzer/ig-cookies.txt \
  --no-warnings --skip-download --ignore-no-formats-error \
  --print "ignored" "$ANY_IG_POST_URL" 2>/dev/null
# /tmp/url-analyzer/ig-cookies.txt now holds all instagram.com cookies in Netscape format
# (sessionid, csrftoken, ds_user_id, ig_did, etc.)
```

This call is a single light HTTP fetch and counts as one server visit (apply the normal delay after it).

### Content type detection and download strategy

1. **If `CONTENT_TYPE=plain-text`**: Skip Phase 1 fetching → Mode K (copy local `.txt` into `/tmp/url-analyzer/`). No server call.
2. **If `CONTENT_TYPE=article`** (`[article]` directive): Skip yt-dlp entirely → Mode H (HTML fetch + readable-body extraction).
3. **If `CONTENT_TYPE=podcast`** (Spotify host / Apple Podcasts host / `[podcast]` / `[podcast-rss]` / local `.mp3`-`.m4a`-`.wav` with `[podcast]`): route to **Mode L** (Spotify), **Mode M** (Apple), **Mode N** (RSS), or **Mode O** (local audio). Then run Step 1.4 (timestamp trim if applicable) + Step 1.5 (duration probe) before Step 2. Long episodes (>30 min) use Step 2 **Path D** (chunked Whisper); short episodes use Path B.
4. **If YouTube URL and NOT `AUDIO_ONLY=true`**: Try captions first (Mode A). If captions found → set `TRANSCRIPT_SOURCE=captions`, done. If no captions → fall back to Mode B (audio download + Whisper). If `[podcast]` directive is also present, run Step 1.5 after download to potentially trigger Path D.
5. **If `AUDIO_ONLY=true`**: Skip caption attempt → Mode B (audio download + Whisper) directly.
6. **If LinkedIn URL**: Mode D (three-stage pipeline)
7. **If Facebook/Instagram URL**: Mode E (yt-dlp audio + thumbnail; both saved). If yt-dlp reports "No video formats found" but extracts metadata → Mode F (image/carousel).
8. **If yt-dlp fails with other errors**: Apply retry logic.

> **Captions-first rationale**: Caption fetches transfer ~10KB of metadata vs ~15MB for audio. When captions exist, this eliminates both the large download AND the 3–5 minute Whisper transcription, reducing per-URL processing from minutes to seconds.

---

### Mode A — Captions (default for YouTube, or `TRANSCRIPT_ONLY=true`)

**Progress indicator**: `⏳ Step 1/7: Fetching captions (transcript-only mode)...`

Attempt to download YouTube's built-in captions. This is a lightweight metadata request — no audio or video data is transferred.

```bash
yt-dlp --skip-download \
  --write-subs --write-auto-subs \
  --sub-lang "en.*" \
  --sub-format vtt \
  --cookies-from-browser firefox \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

This produces a file such as `/tmp/url-analyzer/<slug>.en.vtt` or `/tmp/url-analyzer/<slug>.en-orig.vtt`.

**If captions are found**: Report `✓ Step 1/7: Captions downloaded — skipping audio download and Whisper.` Set source flag `TRANSCRIPT_SOURCE=captions`. Continue to inter-request delay, then next URL.

**If no captions found** (yt-dlp output contains "There are no subtitles" or no `.vtt` file is created): Report `⚠️  No captions found for <URL> — falling back to audio download + Whisper.` Then run Mode B below as the fallback.

---

### Mode B — Audio download (fallback from Mode A, or `AUDIO_ONLY=true`)

**Progress indicator**: `⏳ Step 1/7: Downloading audio...`

#### With timestamp range (`TIMESTAMP_RANGE=true`)

Download only the specified segment — `yt-dlp` will trim server-side before transferring:

```bash
yt-dlp --cookies-from-browser firefox --remote-components ejs:github \
  -x --audio-format mp3 \
  --download-sections "*<START>-<END>" \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

Replace `<START>` and `<END>` with the values parsed in Step 0b (e.g. `00:05:00` and `00:15:00`).

#### Without timestamp range (full audio, default)

```bash
yt-dlp --cookies-from-browser firefox --remote-components ejs:github \
  -x --audio-format mp3 \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

Set source flag `TRANSCRIPT_SOURCE=whisper` after a successful download.

---

### Mode C — Transcript-only + timestamp range (`TRANSCRIPT_ONLY=true` and `TIMESTAMP_RANGE=true`)

**Progress indicator**: `⏳ Step 1/7: Fetching captions for timestamp range...`

Download the full caption file using the Mode A command (captions are tiny text files; partial caption download is not supported by yt-dlp). The timestamp filtering happens in Phase 2 (Step 2).

If no captions are found, fall back to Mode B with `--download-sections`.

---

### Mode D — LinkedIn URLs (automated, three-stage pipeline)

**Progress indicator**: `⏳ Step 1/7: Downloading audio from LinkedIn...`

LinkedIn videos use MPEG-DASH streaming and require authentication. The skill tries three stages in order, stopping at the first success.

---

#### Stage D-1: yt-dlp direct download (works for standard post/feed URLs)

yt-dlp has a LinkedIn extractor that matches these URL patterns:
- `linkedin.com/posts/<slug>-<digits>-<4chars>` (e.g. `.../posts/pratik-joshi-123456789-abcd`)
- `linkedin.com/feed/update/urn:li:activity:<digits>`

For these patterns, attempt a direct audio download using Firefox cookies for authentication:

```bash
yt-dlp --cookies-from-browser firefox \
  -x --audio-format mp3 \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to transcription + sub-agent dispatch.

**If it fails** (unsupported URL pattern, auth error, or yt-dlp error): move to Stage D-2.

---

#### Stage D-2: yt-dlp URL extraction → ffmpeg

Even if yt-dlp can't download directly, it can often extract the underlying DASH manifest URL without transferring any media. Use that URL with ffmpeg:

```bash
# Step 1: extract the raw stream URL(s)
STREAM_URL=$(yt-dlp --cookies-from-browser firefox --get-url '<URL>' 2>/dev/null | head -1)

# Step 2: if a URL was returned, extract audio with ffmpeg
if [ -n "$STREAM_URL" ]; then
  ffmpeg -y \
    -i "$STREAM_URL" \
    -map 0:a:0 \
    -acodec libmp3lame -q:a 2 \
    /tmp/url-analyzer/<slug>.mp3
fi
```

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to transcription + sub-agent dispatch.

**If it fails** (no URL returned, or ffmpeg error): move to Stage D-3.

---

#### Stage D-3: Direct DASH manifest URL (user-supplied or already in watch-urls.md)

When a `dms.licdn.com/playlist/vid/dash/` URL is in the pending list (user already extracted it from the Network tab), use ffmpeg directly — no yt-dlp needed.

> **Critical**: Do NOT use `-c copy`. LinkedIn DASH streams embed audio as HE-AAC (SBR) whose container metadata is inconsistent with the bitstream. Using `-c copy` creates a file with a corrupt `mdat` extended-size header (`0xFFFFFFFCF...`) that no decoder can subsequently read. Always re-encode to MP3.

> **Protocol whitelist**: ffmpeg requires explicit permission to follow HTTPS redirects from DASH manifests. Pass `-allowed_extensions ALL -protocol_whitelist file,https,crypto,tcp,tls` before the `-i` flag.

```bash
ffmpeg -y \
  -allowed_extensions ALL \
  -protocol_whitelist file,https,crypto,tcp,tls \
  -i '<DASH_URL>' \
  -map 0:a:0 \
  -acodec libmp3lame -q:a 2 \
  /tmp/url-analyzer/<slug>.mp3
```

- The video ID for the slug is the 4th path segment of the DASH URL (e.g. `D4D05AQEnN8uEJr57uA`).
- `-map 0:a:0` selects the first audio stream; `-q:a 2` produces high-quality VBR MP3 (~190 kbps).
- Expect a few non-fatal decoder warnings (`Number of bands exceeds limit`, `Queue input is backward in time`) — these are normal for HE-AAC SBR streams and do not corrupt the output.

**If the user provides a local `.mp4` file** (already downloaded from a DASH URL) instead of a manifest URL, the file may have the same corrupt `mdat` issue. In that case, re-download audio fresh from the original DASH URL using the command above rather than trying to extract from the local file.

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to transcription + sub-agent dispatch.

---

#### If all three stages fail — manual fallback

Report the following instructions:

```
❌ Could not auto-download LinkedIn video after 3 attempts.

Manual workaround — extract the DASH manifest URL:
1. Open the LinkedIn post in Firefox (must be logged in)
2. Press F12 → Network tab
3. In the search/filter box, type: playlist
4. Play the video
5. Look for a row with Type = "dash" and size ~20–25 KB
6. Right-click that row → Copy → Copy URL
7. Replace this URL in watch-urls.md with the copied DASH URL
   (it looks like: https://dms.licdn.com/playlist/vid/dash/...)
8. Re-run the analyzer — Stage D-3 will handle it automatically
```

Then add a `failed` entry to `RESULTS[]`: `(failed YYYY-MM-DD — all automated LinkedIn stages failed; replace with DASH manifest URL from Network tab)`. Do not dispatch a sub-agent.

---

**Note**: `[transcript-only]` is not supported for LinkedIn — there are no caption tracks in LinkedIn DASH manifests. The directive is silently ignored; audio + Whisper is always used.

---

### Mode E — Facebook/Instagram URLs (yt-dlp audio + thumbnail)

**Progress indicator**: `⏳ Step 1/7: Downloading audio + thumbnail from Facebook/Instagram...`

Facebook reels, videos, and Instagram content are supported via yt-dlp's built-in extractors. Use authenticated Firefox cookies. **Always grab the thumbnail in addition to the audio** — Instagram reels routinely have music-only audio or background-noise audio where Whisper produces hallucinated song lyrics or single words ("You", "Hehehee", "ДИНАМИЧНАЯ МУЗЫКА"). The actual claims are in the on-screen text overlay, which the thumbnail captures.

#### Step E-1: Probe metadata first (decide audio vs silent-video vs carousel)

**Always pass `--ignore-no-formats-error`** — without it, carousel posts return non-zero and look like a probe failure, when in fact they're successful image-only posts that should route to Mode F. The `head -1` is also important: carousels emit one `--print` line per slide.

```bash
yt-dlp --cookies-from-browser firefox --no-warnings --ignore-no-formats-error \
  --print "%(uploader_id)s|%(uploader)s|%(title)s|%(duration)s|%(acodec)s|%(_type)s|%(playlist_count)s" \
  '<URL>' | head -1
```

Capture: `HANDLE`, `UPLOADER`, `TITLE`, `DURATION`, `ACODEC`, `TYPE`, `PLAYLIST_COUNT`.

**Routing decision:**
- If `DURATION` is non-empty AND `ACODEC` is `none`/`NA`/`null` → **silent-video** path (skip audio download, fetch thumbnail only).
- If `DURATION` is non-empty AND `ACODEC` is a real codec (e.g. `mp4a.40.5`) → **video-audio** path (audio + thumbnail).
- If `DURATION` is empty (or `NA`) AND `PLAYLIST_COUNT > 0` → fall through to **Mode F** (image carousel, authenticated Playwright scraper).
- If `DURATION` is empty AND no `PLAYLIST_COUNT` → single-image post; fall through to Mode F.

#### Step E-2a: video-audio path

```bash
# Audio
yt-dlp --cookies-from-browser firefox --no-warnings \
  -x --audio-format mp3 \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'

# Thumbnail (separate call; some yt-dlp versions don't write both in one shot when -x is set)
yt-dlp --cookies-from-browser firefox --no-warnings \
  --skip-download --write-thumbnail --convert-thumbnails jpg \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

Set `TRANSCRIPT_SOURCE=whisper`, `THUMBNAIL_AVAILABLE=true`. Whisper transcribes `<slug>.mp3` in the background (see Step 2 Path B). Sub-agent will inspect BOTH the transcript AND the thumbnail.

#### Step E-2b: silent-video path

```bash
yt-dlp --cookies-from-browser firefox --no-warnings \
  --skip-download --write-thumbnail --convert-thumbnails jpg \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

Set `TRANSCRIPT_SOURCE=ocr`, `CONTENT_TYPE=silent-video`. No Whisper. Sub-agent works from thumbnail only.

**Supported URL patterns:**
- `facebook.com/reel/ID` (Facebook Reels)
- `facebook.com/watch/?v=ID` (Facebook Watch videos)
- `facebook.com/<username>/videos/ID` (Profile videos)
- `fb.watch/ID` (Facebook short links)
- `instagram.com/reel/ID` (Instagram Reels)
- `instagram.com/p/ID` (Instagram posts that are reels-as-posts)

**If audio or thumbnail fetch succeeds**: proceed to Step 2 + sub-agent dispatch.

**If both fail**: Apply the retry logic from the next section. Facebook videos may require being logged into Firefox for private or region-restricted content.

**Note**: `[transcript-only]` is not supported for Facebook/Instagram — there are no caption tracks available. The directive is silently ignored; audio + Whisper is always used (with thumbnail as fallback).

---

### Mode F — Image/Carousel Posts (Instagram only; Facebook/Twitter image posts not yet supported)

**Progress indicator**: `⏳ Step 1/7: Downloading carousel images via authenticated Playwright...`

Social media platforms support image-only posts (single images or carousels). yt-dlp identifies these posts (it can pull `uploader_id`, `playlist_count`, `title`) but **cannot extract the actual image URLs** — its JSON output has empty `thumbnails` and `formats` arrays for image-only carousels, and `--write-thumbnail` produces "There are no video thumbnails to download". Mode F therefore bypasses yt-dlp entirely for image extraction and uses an authenticated Playwright scraper.

**Detection** (with `--ignore-no-formats-error`):
- yt-dlp prints "No video formats found" warning but still emits metadata
- `playlist_count > 0` and `_type=playlist` → carousel
- `playlist_count = 1` or absent + no duration → single image post

#### Step F-1: Confirm carousel via metadata probe

```bash
META=$(timeout 30 yt-dlp --cookies-from-browser firefox --no-warnings --ignore-no-formats-error --skip-download \
  --print "%(uploader_id)s|%(uploader)s|%(title)s|%(playlist_count)s" \
  '<URL>' | head -1)
# META = "1234|Display Name|Video by handle|7" for a 7-slide carousel
```

#### Step F-2: Reuse cookies exported in the Phase 1 prerequisite

The Netscape-format cookies file at `/tmp/url-analyzer/ig-cookies.txt` was already exported once at the start of Phase 1 (see "Phase 1 prerequisite — export Firefox cookies (one-time per batch)" above). The Playwright scraper loads this same file directly — no re-export needed. If the file is missing (e.g., the user re-ran starting at Phase 1 mid-batch and the prerequisite block was skipped), re-run that prerequisite block before continuing here.

#### Step F-3: Scrape carousel images via Playwright (authenticated)

Run `ig_carousel_scraper.py` (lives next to this SKILL.md):

```bash
python3 ~/.claude/skills/url-truth-analyzer/ig_carousel_scraper.py \
  '<URL>' /tmp/url-analyzer/ig-cookies.txt > /tmp/url-analyzer/<slug>-scrape.json
```

The scraper:
1. Loads Instagram cookies from the Netscape file into a fresh Chromium context.
2. Navigates to the post URL.
3. Filters DOM `img` elements: keeps only those whose alt starts with `Photo by ` or `Video by ` AND whose natural dimensions are ≥ 600px (this excludes the 150×150 profile picture, comment avatars, and Instagram UI icons).
4. Clicks the "Next" button up to 14 times to walk through all carousel slides, harvesting newly-loaded images after each click.
5. Outputs JSON with the list of image URLs and per-image metadata.

Then download each image with curl:

```bash
N=1
python3 -c "import json; print('\n'.join(json.load(open('/tmp/url-analyzer/<slug>-scrape.json')).get('images', [])))" | \
while IFS= read -r IMG_URL; do
  curl -s -L --max-time 20 -H "User-Agent: Mozilla/5.0" \
    -o "/tmp/url-analyzer/<slug>-${N}.jpg" "$IMG_URL"
  # Reject empty/tiny files (failed downloads)
  [ "$(stat -f%z "/tmp/url-analyzer/<slug>-${N}.jpg" 2>/dev/null || echo 0)" -lt 1000 ] && \
    rm -f "/tmp/url-analyzer/<slug>-${N}.jpg"
  N=$((N+1))
done
```

#### Step F-4: Set flags + dispatch

If at least one image landed:
- Set `CONTENT_TYPE=image-carousel`, `TRANSCRIPT_SOURCE=ocr`
- Dispatch a sub-agent (Mode F dispatch instructions tell the sub-agent to expect multiple `<slug>-N.jpg` files and to deduplicate visually — the scraper may collect more image elements than there are unique slides because Instagram serves multiple aspect ratios per slide).

If zero images landed: add a `failed` entry: `(failed YYYY-MM-DD — Playwright scraper returned no images; check cookies / IG login status)`.

**Why this approach**:
- yt-dlp's Instagram extractor has no support for image-only carousels (it can list the playlist but emits no `url` or `thumbnails` per entry).
- Direct curl scraping fails because Instagram's web app is JS-rendered — the HTML returned by curl is a 600KB+ shell with zero post image URLs.
- Authenticated Chromium + Firefox cookies is the only currently-supported scraping path for IG image-only carousels.

**Supported URL patterns** (Mode F):
- `instagram.com/p/ID` and `instagram.com/p/ID?img_index=N` (carousel posts; `img_index` is the slide the user shared but the scraper walks all slides anyway)
- `instagram.com/reel/ID` only if the post was converted to image (rare; usually yt-dlp succeeds on reels via Mode E)
- For Facebook/Twitter image posts, the scraper currently targets the Instagram DOM only — extend it for other platforms when needed.

**Dependencies**:
- `playwright` Python package (`pip3 install --user --break-system-packages playwright`)
- Chromium browser (`playwright install chromium`)
- User must be logged into Instagram in Firefox so `--cookies-from-browser firefox` returns a valid session.

**Rate limiting**:
- Each scraper run is a server visit; apply the standard 45–75s inter-request delay.
- A scrape takes ~10–15s (Chromium launch + DOM walk + carousel clicks); be aware that this consumes part of the delay window.

---

### Mode I — Local Folder of Images (no download needed)

**Progress indicator**: `⏳ Step 1/7: Copying local images to working directory...`

When `CONTENT_TYPE=local-folder` (detected in Step 0a-local), no download is needed. Instead, copy the supported image files **recursively** from the source folder tree into `/tmp/url-analyzer/` using the standard slug naming convention so Path C can find them:

```bash
# Create working directory
mkdir -p /tmp/url-analyzer

# Find all images recursively (up to depth 5, already validated in Phase 0)
readarray -t IMG_FILES < <(find /path/to/folder -maxdepth 5 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.webp" \) | sort)

IMG_COUNT=${#IMG_FILES[@]}

# Warn if large folder
if [ "$IMG_COUNT" -ge 20 ]; then
  echo "⚠️  Folder tree contains $IMG_COUNT images — analysis may take a while."
fi

# Copy images with sequential naming, preserving subfolder structure in metadata
N=1
for img in "${IMG_FILES[@]}"; do
  # Extract relative path for metadata tracking
  REL_PATH="${img#/path/to/folder/}"

  cp "$img" "/tmp/url-analyzer/<slug>-${N}.jpg"

  # Store relative path mapping for analysis context
  echo "$N: $REL_PATH" >> "/tmp/url-analyzer/<slug>-paths.txt"

  N=$((N + 1))
done
```

This copy step ensures:
- The working directory `/tmp/url-analyzer/` contains files named `<slug>-1.jpg`, `<slug>-2.jpg`, etc. — matching the convention Mode F uses
- Original user files are **never** modified or deleted
- Path C finds images using the same glob pattern
- A `<slug>-paths.txt` file preserves the original subfolder structure for context during analysis (e.g., "Image 3 from subfolder 'before-photos': ...")

**No inter-request delay** is needed after this step (no server was contacted).
**No retry logic** applies.
**Does not count toward batch cooldown.**

Set `CONTENT_TYPE=image` and `TRANSCRIPT_SOURCE=ocr`, dispatch a sub-agent for OCR + analysis.

Report: `✓ Step 1/7: N local images staged for analysis (from M subfolders, no download needed).`

---

### Mode H — Article URL (HTML fetch + readable-body extraction)

**Progress indicator**: `⏳ Step 1/7: Fetching article HTML and extracting readable body...`

When `CONTENT_TYPE=article` (set by `[article]` directive), skip yt-dlp entirely. Fetch the page and extract just the readable article body — strip nav, ads, footers, comments, related-content widgets.

#### Step H-1: Fetch and extract with trafilatura (preferred)

```bash
mkdir -p /tmp/url-analyzer

python3 - <<'EOF' > /tmp/url-analyzer/<slug>.txt
import sys
try:
    import trafilatura
except ImportError:
    sys.stderr.write("MISSING_TRAFILATURA\n")
    sys.exit(2)

url = '<URL>'
downloaded = trafilatura.fetch_url(url)
if not downloaded:
    sys.stderr.write("FETCH_FAILED\n")
    sys.exit(3)

# Extract title separately for slug derivation
metadata = trafilatura.extract_metadata(downloaded)
title = (metadata.title if metadata and metadata.title else '').strip()
sys.stderr.write(f"TITLE::{title}\n")

text = trafilatura.extract(
    downloaded,
    include_comments=False,
    include_tables=False,
    favor_recall=True,
)
if not text:
    sys.stderr.write("EXTRACT_FAILED\n")
    sys.exit(4)

print(text)
EOF
```

The script prints the article body to stdout (redirected to `<slug>.txt`) and emits `TITLE::<title>` on stderr so the parent can read the page's `<title>` to derive the slug if `[article title: ...]` was not supplied.

If `trafilatura` is not installed, install it once:

```bash
pip3 install --user --break-system-packages trafilatura
```

#### Step H-2: Fallback — curl + pandoc

If `trafilatura` cannot be installed (sandboxed environment) or the extraction fails, fall back to:

```bash
curl -sL -A "Mozilla/5.0" '<URL>' \
  | pandoc -f html -t plain --wrap=none \
  > /tmp/url-analyzer/<slug>.txt

# Derive title from <title> tag
TITLE=$(curl -sL -A "Mozilla/5.0" '<URL>' \
  | python3 -c "import sys,re; m=re.search(r'<title[^>]*>(.*?)</title>', sys.stdin.read(), re.I|re.S); print((m.group(1) if m else '').strip())")
```

The pandoc fallback is noisier (may include nav/footer text) but always works if pandoc and curl are present.

#### Step H-3: Slug + dedup

1. If `[article title: ...]` was supplied in the directive block, use that title (already slugified in Step 0a-article).
2. Otherwise, slugify the title captured from Step H-1 or H-2.
3. Now run Check B (local slug match against `~/Documents/truth-analyses/` filenames). If a match is found, mark this entry as a duplicate, delete the temp `<slug>.txt`, and skip sub-agent dispatch.
4. If no duplicate, validate the extracted text:
   - If the file is empty or under 200 characters → mark as failed: `(failed YYYY-MM-DD — article body extraction produced too little text; site may be paywalled or JS-rendered)`. Skip sub-agent dispatch.
5. Otherwise: set `TRANSCRIPT_SOURCE=html`, dispatch a sub-agent for Steps 3–6. Apply the standard inter-request delay (this was a server call).

**Notes**:
- `[transcript-only]`, `[audio-only]`, and `[timestamp-range]` are silently ignored for `[article]` entries.
- Paywalled articles often produce empty or stub extractions. The 200-character minimum catches these — user can manually paste the article text into a `.txt` file and re-add with `[plain-text]` if needed.
- Channel reputation (Step 4c) uses the URL's hostname/publication as the "source channel".

**After Mode H success**: Report `✓ Step 1/7: Article body extracted (N words) — sub-agent dispatched.`

---

### Mode K — Plain-text file (no fetch, local read)

**Progress indicator**: `⏳ Step 1/7: Copying plain-text file to working directory...`

When `CONTENT_TYPE=plain-text` (set by `[plain-text]` directive in Step 0a-plaintext), no fetch is required. Copy the file's contents into `/tmp/url-analyzer/<slug>.txt`:

```bash
mkdir -p /tmp/url-analyzer
cp '<absolute-path-to-.txt>' '/tmp/url-analyzer/<slug>.txt'
```

Validate:
- If the copy fails for any reason → mark as failed: `(failed YYYY-MM-DD — could not read plain-text file: <error>)`.

This step makes **no server calls**. No inter-request delay. No retry logic. Does not count toward batch cooldown.

Set `CONTENT_TYPE=plain-text` and `TRANSCRIPT_SOURCE=plain-text`. Dispatch a sub-agent for Steps 3–6 immediately.

For Step 4c (channel reputation), there is no channel — the sub-agent records `Source channel: N/A (plain-text file)` and skips the reputation paragraph.

**Original file safety**: Never modify or delete the user's source `.txt` file. Step 6 cleanup deletes only the copy at `/tmp/url-analyzer/<slug>.txt`.

**After Mode K**: Report `✓ Step 1/7: Plain-text file staged (N words, no download needed).`

---

### Mode L — Spotify podcast episode (yt-dlp + DRM detection)

**Progress indicator**: `⏳ Step 1/7: Probing + downloading Spotify episode...`

Spotify exposes some podcast episodes via yt-dlp's Spotify extractor (when the publisher distributes outside the Spotify+ DRM walled garden). Spotify Originals / Exclusives are DRM-protected and will fail — the failure message routes the user to the publisher's RSS instead.

**Step L-1: Episode-ID temp naming + combined probe+download**

Use the Spotify episode ID (path segment after `/episode/`) as the temp filename until the title-derived slug is known.

```bash
EP_ID=$(echo '<URL>' | grep -oE '/episode/[A-Za-z0-9]+' | sed 's|/episode/||')

mkdir -p /tmp/url-analyzer
yt-dlp --cookies-from-browser firefox --no-warnings \
  -x --audio-format mp3 \
  --print-to-file "%(title)s|%(duration)s|%(uploader)s" "/tmp/url-analyzer/sp-${EP_ID}.meta" \
  -o "/tmp/url-analyzer/sp-${EP_ID}.%(ext)s" '<URL>' 2>&1 | tee "/tmp/url-analyzer/sp-${EP_ID}.ytdlp.log"
```

This is a single yt-dlp invocation — probe (`--print-to-file`) and download happen in one call. Mode L therefore consumes **1 server-call** budget. The normal Step 0b `--get-title` pre-check is **skipped for Spotify URLs** (the title arrives via this combined call); dedup runs post-download by slug.

**Step L-2: Title → slug derivation + rename**

```bash
TITLE=$(cut -d'|' -f1 "/tmp/url-analyzer/sp-${EP_ID}.meta")
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')
mv "/tmp/url-analyzer/sp-${EP_ID}.mp3" "/tmp/url-analyzer/${SLUG}.mp3"
mv "/tmp/url-analyzer/sp-${EP_ID}.meta" "/tmp/url-analyzer/${SLUG}.meta"
AUDIO_PATH="/tmp/url-analyzer/${SLUG}.mp3"
```

Now run Check B (slug-match against `~/Documents/truth-analyses/`); if duplicate, delete the just-downloaded `.mp3` and emit a duplicate entry.

**Step L-3: Failure detection — distinct DRM / region-lock / 429 / generic**

```bash
LOG="/tmp/url-analyzer/sp-${EP_ID}.ytdlp.log"
if grep -qiE 'DRM|Spotify\+|Spotify exclusive' "$LOG"; then
  FAIL_MSG="Spotify exclusive / DRM-protected. Try the publisher's RSS feed instead; add as [podcast-rss]."
elif grep -qiE 'not available in your country|geo|region' "$LOG"; then
  FAIL_MSG="Spotify episode region-locked. Try via VPN or via the publisher's RSS feed [podcast-rss]."
elif grep -qiE 'HTTP Error 429|Too Many Requests|rate limit' "$LOG"; then
  FAIL_MSG="Spotify rate-limited (after standard exponential backoff retries exhausted). Retry manually after several hours."
else
  FAIL_MSG="Spotify download failed: $(tail -1 "$LOG")"
fi
```

**Step L-4: Rate-limit** — 1 server call total. Apply standard 45–75s delay after success or after the DRM-failed log message.

**Note**: `[transcript-only]` is silently ignored for Spotify (no caption tracks). `TRANSCRIPT_SOURCE=whisper`. Proceed to Step 1.4 (timestamp trim if applicable), then Step 1.5 (duration probe).

---

### Mode M — Apple Podcasts (iTunes Lookup → RSS resolution)

**Progress indicator**: `⏳ Step 1/7: Resolving Apple Podcasts feedUrl via iTunes Lookup...`

Apple Podcasts has no public episode-audio API; episodes are fetched from the publisher's RSS feed (which Apple does expose via iTunes Lookup). This mode resolves the feed URL, then delegates to Mode N with a GUID-match hint.

**Step M-1: Extract IDs from URL**

```bash
APPLE_PODCAST_ID=$(echo '<URL>' | grep -oE 'id[0-9]+' | tr -d 'id')
EP_GUID=$(echo '<URL>' | grep -oE '[?&]i=[^&]+' | sed 's/^[?&]i=//')
```

**Step M-2: iTunes Lookup with concrete failure detection**

```bash
LOOKUP_HTTP=$(curl -sL -w '\n%{http_code}' "https://itunes.apple.com/lookup?id=$APPLE_PODCAST_ID")
HTTP_CODE=$(echo "$LOOKUP_HTTP" | tail -1)
LOOKUP_BODY=$(echo "$LOOKUP_HTTP" | sed '$d')

if [ "$HTTP_CODE" = "451" ]; then
  FAIL_MSG="Apple Podcasts feed region-locked (HTTP 451). Try via VPN or use the publisher's RSS feed directly with [podcast-rss]."
  exit_failed
fi

FEED_URL=$(echo "$LOOKUP_BODY" | python3 -c "import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print('__JSON_PARSE_ERROR__'); sys.exit(0)
if not d.get('results'): print('__NO_RESULTS__'); sys.exit(0)
r = d['results'][0]
if 'feedUrl' not in r or not r['feedUrl']: print('__NO_FEED_URL__'); sys.exit(0)
print(r['feedUrl'])")

case "$FEED_URL" in
  __JSON_PARSE_ERROR__)
    FAIL_MSG="Apple Podcasts: iTunes Lookup returned malformed JSON"
    exit_failed ;;
  __NO_RESULTS__)
    FAIL_MSG="Apple Podcasts: iTunes Lookup returned no results for podcast id $APPLE_PODCAST_ID (podcast may be removed or region-locked from your IP)"
    exit_failed ;;
  __NO_FEED_URL__)
    FAIL_MSG="Apple Podcasts: iTunes Lookup returned no feedUrl for podcast id $APPLE_PODCAST_ID. Likely Apple Podcasts Subscriptions-only (paywalled)."
    exit_failed ;;
esac
```

**Step M-3: Probe resolved feed URL to distinguish public from paywalled/region-locked**

```bash
STATUS=$(curl -sI "$FEED_URL" -o /dev/null -w '%{http_code}')
if [ -z "$STATUS" ] || [ "$STATUS" = "000" ]; then
  STATUS=$(curl -skI "$FEED_URL" -o /dev/null -w '%{http_code}')
  [ "$STATUS" != "000" ] && echo "⚠️  Apple feed required insecure TLS (-k) — publisher has bad cert chain."
fi
case "$STATUS" in
  200|301|302|307|308) ;;
  401|403) FAIL_MSG="Apple Podcasts: feed URL requires auth (HTTP $STATUS); likely paywalled"; exit_failed ;;
  451) FAIL_MSG="Apple Podcasts feed region-locked (HTTP 451)"; exit_failed ;;
esac
```

**Step M-4: Delegate to Mode N with GUID hint**

Invoke Mode N with `FEED_URL` and `EP_GUID`. Mode N iterates items and matches against `<guid>`, `<enclosure url>`, or item `<link>` containing `$EP_GUID` (publishers stash the Apple `i=` value in different places). If no GUID match is found, Mode N emits a non-fatal warning and uses the most-recent episode instead. The Step 7 entry should append a note when this fallback occurs.

**Step M-5: Rate-limit** — 3 server calls clustered tightly (iTunes Lookup + RSS XML fetch + enclosure download — plus 1 HEAD probe for the feed, which is sub-second). Apply ONE 45–75s delay after the enclosure download (clustered-call treatment matches `Mode F` carousel scrape).

**Note**: `[transcript-only]` is silently ignored. `TRANSCRIPT_SOURCE=whisper`. Proceed to Step 1.4 / 1.5 after Mode N download completes.

---

### Mode N — Generic podcast RSS feed

**Progress indicator**: `⏳ Step 1/7: Fetching RSS feed XML and parsing for episode enclosure...`

This mode handles direct RSS feed URLs (with `[podcast-rss]` directive or auto-detected by URL path) and is also invoked by Mode M as the second stage of Apple resolution.

**Step N-1: Fetch feed + root-tag confirmation**

```bash
mkdir -p /tmp/url-analyzer
FEED_HASH=$(echo '<RSS_URL>' | shasum -a 1 | cut -c1-12)
FEED_PATH="/tmp/url-analyzer/feed-${FEED_HASH}.xml"
curl -sL -A "Mozilla/5.0" --max-time 60 '<RSS_URL>' > "$FEED_PATH"

# Strip UTF-8 BOM if present (some publishers emit it; ET.parse chokes)
sed -i '' -e '1s/^\xEF\xBB\xBF//' "$FEED_PATH" 2>/dev/null || true

# Root-tag sniff via streaming iterparse (handles huge feeds without loading full file)
ROOT_TAG=$(python3 - "$FEED_PATH" <<'EOF'
import sys
from xml.etree import ElementTree as ET
try:
    for ev, el in ET.iterparse(sys.argv[1], events=('start',)):
        print(el.tag.split('}', 1)[-1] if '}' in el.tag else el.tag); break
except Exception:
    print('')
EOF
)
case "$ROOT_TAG" in
  rss|feed) ;;
  *) FAIL_MSG="URL did not return RSS or Atom XML at root (got: '$ROOT_TAG')"; exit_failed ;;
esac
```

**Step N-2: Parse feed → choose episode (with pubDate-sorted ordering, namespace-agnostic, GUID match)**

```bash
PARSE_OUT=$(python3 - "$FEED_PATH" "${EPISODE_INDEX:-1}" "${EP_GUID:-}" <<'EOF'
import sys, json
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

feed_path, ep_index, ep_guid = sys.argv[1], int(sys.argv[2]), sys.argv[3]

try:
    tree = ET.parse(feed_path)
except ET.ParseError as e:
    print(json.dumps({"error": f"RSS parse error: {e}"})); sys.exit(0)
except Exception as e:
    print(json.dumps({"error": f"feed read error: {e}"})); sys.exit(0)

root = tree.getroot()

def lname(t):
    return t.split('}', 1)[-1] if '}' in t else t

items = [el for el in root.iter() if lname(el.tag) in ('item', 'entry')]
if not items:
    print(json.dumps({"error": "no <item> or <entry> elements found in feed"})); sys.exit(0)

def child_text(item, target_local):
    for c in item:
        if lname(c.tag) == target_local:
            return (c.text or '').strip()
    return ''

def child_attr(item, target_local, attr):
    for c in item:
        if lname(c.tag) == target_local:
            return c.get(attr, '')
    return ''

def find_enclosure_url(item):
    u = child_attr(item, 'enclosure', 'url')
    if u: return u
    for c in item:
        if lname(c.tag) == 'link' and c.get('rel') == 'enclosure':
            return c.get('href', '')
    for c in item:
        if lname(c.tag) == 'content' and c.get('url') and (
                c.get('type', '').startswith('audio') or c.get('medium') == 'audio'):
            return c.get('url')
    return ''

def find_pubdate(item):
    for tag in ('pubDate', 'published', 'updated'):
        txt = child_text(item, tag)
        if not txt: continue
        try:
            return parsedate_to_datetime(txt)
        except Exception:
            try:
                return datetime.fromisoformat(txt.replace('Z', '+00:00'))
            except Exception:
                continue
    return datetime.fromtimestamp(0, tz=timezone.utc)

# Sort by pubDate descending (newest first) — required for [episode: N] semantics
items.sort(key=find_pubdate, reverse=True)

chosen = None
chosen_idx = ep_index - 1
guid_matched = False

if ep_guid:
    for i, it in enumerate(items):
        guid = child_text(it, 'guid')
        enc_url = find_enclosure_url(it)
        link = child_attr(it, 'link', 'href') or child_text(it, 'link')
        if ep_guid in guid or ep_guid in enc_url or ep_guid in link:
            chosen, chosen_idx, guid_matched = it, i, True
            break

if chosen is None:
    if chosen_idx < 0 or chosen_idx >= len(items):
        chosen_idx = 0
    chosen = items[chosen_idx]

title = child_text(chosen, 'title')
enc_url = find_enclosure_url(chosen)
duration = ''
for c in chosen:
    if lname(c.tag) == 'duration':
        duration = (c.text or '').strip(); break
guid = child_text(chosen, 'guid')

if not enc_url:
    print(json.dumps({"error": "no audio enclosure found in selected item (video-only or transcript-only feed)"})); sys.exit(0)

print(json.dumps({
    "title": title,
    "url": enc_url,
    "duration": duration,
    "guid": guid,
    "chosen_index": chosen_idx,
    "total_items": len(items),
    "guid_matched": guid_matched,
    "guid_requested": bool(ep_guid),
}))
EOF
)

ENCLOSURE_URL=$(echo "$PARSE_OUT" | python3 -c "import json, sys; d=json.loads(sys.stdin.read()); print(d.get('url',''))")
ERROR_MSG=$(echo "$PARSE_OUT" | python3 -c "import json, sys; d=json.loads(sys.stdin.read()); print(d.get('error',''))")

if [ -n "$ERROR_MSG" ]; then
  FAIL_MSG="$ERROR_MSG"
  exit_failed
fi
```

**Step N-3: Title → slug + Check B + download enclosure**

```bash
TITLE=$(echo "$PARSE_OUT" | python3 -c "import json, sys; print(json.loads(sys.stdin.read())['title'])")
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//' | head -c 60)

# Check B dedup (slug match against ~/Documents/truth-analyses/) AND Stage B in-batch dedup
# (if another already-resolved RSS entry in the batch has the same slug, skip download here).

curl -sL -A "Mozilla/5.0" --max-time 600 \
  -o /tmp/url-analyzer/${SLUG}.mp3 "$ENCLOSURE_URL"
AUDIO_PATH="/tmp/url-analyzer/${SLUG}.mp3"

# Rename feed cache to slug for consistent cleanup
mv "$FEED_PATH" "/tmp/url-analyzer/${SLUG}.feed.xml"
```

**Step N-4: Apple GUID fallback notation**

When invoked by Mode M with an `EP_GUID` that did not match any item (`guid_matched=false` AND `guid_requested=true`), append a note to the Step 7 entry: `... (analyzed YYYY-MM-DD; Apple GUID not found in RSS — analyzed newest episode "<title>" → truth-analyses/...)`. The user can verify whether the right episode was processed.

**Step N-5: Rate-limit** — 2 server calls clustered (XML fetch + enclosure download). Apply ONE 45–75s delay after the enclosure download.

**Note**: `[transcript-only]`, `[audio-only]`, and `[timestamp-range]` are silently ignored. `TRANSCRIPT_SOURCE=whisper`. Proceed to Step 1.4 / 1.5.

---

### Mode O — Local audio file (.mp3 / .m4a / .wav)

**Progress indicator**: `⏳ Step 1/7: Copying local audio to working directory...`

No fetch. Mirror of Mode K (plain-text), but for audio. Validation already happened in Sub-step 0a-podcast; this step only stages the file.

```bash
mkdir -p /tmp/url-analyzer
EXT=$(echo '<absolute-path>' | awk -F. '{print tolower($NF)}')

SLUG="${TITLE_OVERRIDE_SLUG:-$(basename '<absolute-path>' ".$EXT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')}"
cp '<absolute-path>' "/tmp/url-analyzer/${SLUG}.${EXT}"
AUDIO_PATH="/tmp/url-analyzer/${SLUG}.${EXT}"
```

`AUDIO_PATH` preserves the original extension so subsequent steps (ffprobe, ffmpeg chunking, Whisper) work uniformly with `.mp3`/`.m4a`/`.wav`. Modes L/M/N all set `AUDIO_PATH` to a `.mp3` path; Mode O is the only mode that may set it to `.m4a` or `.wav`.

**No server call** — no inter-request delay, no batch-cooldown counter, no retry logic.

Set `CONTENT_TYPE=podcast`, `TRANSCRIPT_SOURCE=whisper`. For Step 4c (channel reputation), there is no channel — the sub-agent records `Source channel: N/A (local audio file)` and skips the reputation paragraph.

**Original file safety**: Never modify or delete the user's source audio file. Step 6 cleanup deletes only the copy under `/tmp/url-analyzer/`.

**After Mode O**: Report `✓ Step 1/7: Local audio staged (extension: <ext>, no download needed).` Proceed to Step 1.4 / 1.5.

---

## Step 1.4: Timestamp trim (podcasts only, when `TIMESTAMP_RANGE=true`)

**Progress indicator**: `⏳ Step 1.4: Trimming audio to requested timestamp range...`

If the entry has a `[HH:MM:SS-HH:MM:SS]` directive, trim the downloaded audio **before** duration classification. This means a 90-minute episode trimmed to `[00:05:00-00:15:00]` (10 minutes) routes to the short path, not the long path. The trim uses `-c copy` (stream copy, no re-encode) because it operates on the already-encoded file Modes L/M/N produced.

```bash
if [ "$TIMESTAMP_RANGE" = "true" ]; then
  TRIMMED="${AUDIO_PATH%.*}.trimmed.${AUDIO_PATH##*.}"
  ffmpeg -y -i "$AUDIO_PATH" -ss "${START}" -to "${END}" -c copy "$TRIMMED" && \
    mv "$TRIMMED" "$AUDIO_PATH"
fi
```

Only applies to `CONTENT_TYPE=podcast`. For all other content types, this step is a no-op.

---

## Step 1.5: Duration probe + long/short routing (podcasts only)

**Progress indicator**: `⏳ Step 1.5: Probing audio duration to classify long vs short...`

Classify the (possibly trimmed) audio as **short** (≤30 min) or **long** (>30 min). `ffprobe` works uniformly on `.mp3`/`.m4a`/`.wav` so `$AUDIO_PATH` is read directly.

```bash
DURATION_SEC=$(ffprobe -v quiet -show_entries format=duration \
  -of csv=p=0 "$AUDIO_PATH" 2>/dev/null | cut -d. -f1)
if [ -z "$DURATION_SEC" ] || [ "$DURATION_SEC" -lt 1 ]; then
  DURATION_SEC=0
  echo "⚠️  Step 1.5: Could not determine duration via ffprobe; defaulting to short Whisper path."
fi

WHISPER_MODEL_OVERRIDE="${WHISPER_MODEL_FROM_DIRECTIVE:-}"
if [ "$DURATION_SEC" -gt 1800 ]; then
  PODCAST_LENGTH=long
  WHISPER_MODEL="${WHISPER_MODEL_OVERRIDE:-medium}"
  if [ "$WHISPER_MODEL" = "large-v3" ]; then
    MAX_WHISPER_JOBS=1   # 3 GB model × 2 = 6 GB+, force serial on 16 GB systems
  else
    MAX_WHISPER_JOBS=2
  fi
else
  PODCAST_LENGTH=short
  WHISPER_MODEL=small
  MAX_WHISPER_JOBS=1   # n/a but set for safety
fi
```

**Routing**:
- `PODCAST_LENGTH=short` → Step 2 Path B (existing single-pass Whisper `small`).
- `PODCAST_LENGTH=long` → Step 2 Path D (new chunked Whisper, see below).

**Step 1.5 also runs for YouTube URLs with `[podcast]` directive** (`PODCAST_LENGTH_CHECK=true` set in Sub-step 0a-podcast) so long YouTube interviews can also opt into Path D.

**Sub-agent dispatch timing (long path):** Step 2 Path D for a 90-minute episode at `medium` takes ~5–15 minutes. Path D MUST run as a background process so the parent can proceed with the next URL's download during the inter-request delay. The sub-agent for this URL is dispatched LATE (after Path D's stitch step writes the transcript `.txt` atomically), not after the delay ends. The existing "await transcript ready" logic at the end of Phase 1 already handles this — verify the `wait` loop iterates over Path D background PIDs in addition to Path B PIDs.

---

### Retry with exponential backoff

If `yt-dlp` fails and the output contains any of: `Sign in to confirm`, `HTTP Error 429`, `Too Many Requests`, or `rate limit` — this is a server-side rate limit. Apply exponential backoff:

| Attempt | Wait before retry |
|---|---|
| 1st retry | 90 seconds |
| 2nd retry | 180 seconds |
| 3rd retry | 360 seconds |
| After 3rd failure | Add `failed` entry to `RESULTS[]`, continue to next URL |

For any other error (private video, bad URL, **LinkedIn extraction failure**, etc.) — do not retry. Add a `failed` entry to `RESULTS[]` immediately and continue to the next URL.

Report retry attempts as they happen:
```
⚠️  Rate limited on URL N — waiting 90s before retry 1/3...
```

If all 3 retries fail, report:
```
❌ Failed: <URL> — rate limited after 3 retries. Will be marked in watch-urls.md during batch update.
```

---

### Inter-request delay (with pipelined transcription + sub-agent dispatch)

After each URL's download completes (success or skip), **start transcription immediately, dispatch a sub-agent when ready, then enter the delay**:

1. **If `TRANSCRIPT_SOURCE=captions`**: Run VTT-to-text conversion inline (instant, ~1s — see Step 2 Path A). Then **dispatch a sub-agent** for this URL's analysis. Then enter delay.
2. **If `TRANSCRIPT_SOURCE=whisper`**: Spawn Whisper as a background process, then enter delay. Whisper runs concurrently during the wait:

```bash
whisper /tmp/url-analyzer/<slug>.mp3 --model small --output_format txt --output_dir /tmp/url-analyzer/ &
WHISPER_PID_<N>=$!
sleep $((45 + RANDOM % 31))   # randomized: 45–75 seconds — Whisper runs during this wait
```

3. Before starting the next URL's server calls, verify the background Whisper job completed:

```bash
wait $WHISPER_PID_<N>
```

4. **After Whisper completes**: Dispatch a sub-agent for this URL's analysis (see Sub-agent dispatch protocol). The sub-agent runs concurrently with the remaining downloads.

If Whisper finishes before the delay ends, the sub-agent is dispatched immediately and the delay still runs to completion (rate-limit protection). If Whisper takes longer than the delay (rare for short videos), the next URL waits for Whisper to finish first, then the sub-agent is dispatched.

**Delay rules**:
- Apply between every consecutive URL, including after Check B title lookups (see Step 0b).
- Do **not** apply before the very first URL.
- The randomized jitter prevents a detectable fixed-interval fingerprint.
- **Reduced delay for caption-only fetches**: When Mode A succeeds (captions found, no audio download needed), the delay can be reduced to **15–30 seconds** since caption fetches are lightweight metadata requests:

```bash
sleep $((15 + RANDOM % 16))   # randomized: 15–30 seconds for caption-only
```

**Exception**: Local folder entries (Mode I), plain-text file entries (Mode K), and local audio entries (Mode O) do not count toward the inter-request delay or batch cooldown counters, since no server calls are made. Article fetches (Mode H) and podcast modes L/M/N DO make network requests and should count toward rate limits.

**Manifest write ordering**: The orchestrator MUST write each URL's manifest row to `/tmp/url-analyzer/manifest.tsv` AFTER all download steps for that URL have completed AND BEFORE entering the inter-request delay. Writes are streaming (one row per URL, appended) rather than buffered-then-flushed — this trades a small interruption-window race (kill between download completion and manifest append → URL re-downloaded next run) against the protection of losing all rows if the process dies during the delay. Sub-agent dispatch reads only rows with `status=OK`. The process-singleton guard (see "Phase 1 prerequisite — process-singleton guard" above) is the actual protection against concurrent writers; `PIPE_BUF` atomicity is a property of pipes, not regular files, so DO NOT rely on it for append safety to `manifest.tsv`. Use `printf` (not `echo -e`) to write rows, and tab-delimit fields explicitly.

**Podcast mode rate-limit budget:**
- **Mode L (Spotify)** — 1 server call (combined yt-dlp probe+download invocation). Step 0b `--get-title` pre-check is skipped for Spotify URLs because Mode L produces the title via the same call. Apply standard 45–75s delay after the download (success OR DRM-failed log).
- **Mode M (Apple Podcasts)** — 3 server calls clustered tightly: (a) iTunes Lookup, (b) feed `HEAD` probe, (c) RSS XML fetch + (d) enclosure download. The first three are sub-second metadata calls; apply ONE 45–75s delay after the enclosure download (matches Mode F carousel scrape's clustered-call treatment).
- **Mode N (Generic RSS)** — 2 server calls clustered: (a) RSS XML fetch + (b) enclosure download. Apply ONE 45–75s delay after the enclosure download.
- **Mode O (Local audio)** — 0 server calls. No inter-request delay. Does not count toward batch cooldown.

**Channel enumeration (Phase 0 Step 0) rate-limit budget:**
- Each channel `channel_enumerator.py` call is ONE server interaction → apply one 45–75s inter-request delay after it (before the first expanded item's download) and count it toward the 5-item batch cooldown.
- Two bounded sub-exceptions inside the enumerator are intentional and do NOT each incur the full delay: (a) **generic feed probing** uses lightweight HEAD requests that stop at the first hit (a bounded burst, not 45–75s spacing); (b) **YouTube multi-tab `--strict-order`** counts each per-tab `--dump-json` call as one delay unit, not one per video.
- The expanded permalinks themselves are ordinary URLs and follow all standard delay/cooldown rules above.

### Batch cooldown

After every **5th** successful or attempted download, insert an additional pause before continuing:

```bash
sleep 300   # 5-minute cooldown after each group of 5
```

This gives the server-side rate-limit window time to reset before the next batch. The count resets after each cooldown.

**After all Phase 1 downloads complete**: Report `✓ Phase 1 complete: X downloaded, Z failed. Y sub-agents dispatched and running.`

After reporting, wait for all outstanding background Whisper processes (any that haven't triggered sub-agent dispatch yet):

```bash
for pid in "${WHISPER_PIDS[@]}"; do
  wait $pid
done
```

Then dispatch sub-agents for any remaining transcripts that completed after their download's delay ended. Finally, proceed to **Result collection** (see below).

---

## Sub-agent dispatch protocol

### When to dispatch

A sub-agent is dispatched **as soon as a URL's transcript `.txt` file is ready** — either:
- Immediately after VTT-to-text conversion (captions, ~1s), or
- After the background Whisper process completes (awaited before the next download starts)

For **local folder entries**: dispatch a sub-agent immediately after images are staged into `/tmp/url-analyzer/` (Mode I copy step).

For **image-carousel entries (Mode F)**: dispatch a sub-agent immediately after the Playwright scraper output is converted to `<slug>-N.jpg` files via curl (Step F-3). The sub-agent reads all `/tmp/url-analyzer/<slug>-*.jpg` files; the parent does not run OCR.

For **failed downloads**: do not dispatch a sub-agent. Add a `failed` entry to `RESULTS[]` directly.

For **duplicates** (detected in Phase 0 or Step 0b): do not dispatch a sub-agent. Add a `duplicate` entry to `RESULTS[]` directly.

### How to dispatch

Use the Task tool with `subagent_type="generalPurpose"` and `run_in_background=true`. Each sub-agent runs independently with no concurrency cap — all are spawned immediately as transcripts become ready.

Collect all returned agent IDs in a `PENDING_AGENTS[]` list for later polling.

### Sub-agent prompt template

Each sub-agent receives a self-contained prompt with everything it needs. The parent constructs the prompt from the URL's metadata:

```
You are analyzing content for truth claims. Run Steps 2 (if needed), 3, 4, 5, and 6 from the analysis workflow below.

## Context
- URL or path: <clean_url_or_path>
- Slug: <slug>
- Title: <title>
- Handle / uploader: <uploader_id> / <uploader>
- Content type: <video|audio|image|article|plain-text|silent-video|podcast>
- Transcript source: <captions|whisper|ocr|html|plain-text>
- Transcript file: /tmp/url-analyzer/<slug>.txt
- Thumbnail file: /tmp/url-analyzer/<slug>.jpg  ← present for Instagram/Facebook reels (Mode E) and silent-video
- Transcript degenerate: <unknown|n/a>  ← "unknown" for Instagram/Facebook reels (Mode E) and long podcasts — the sub-agent runs the `<30 words / music-only / hallucinated lyrics` check itself. "n/a" for YouTube captions, LinkedIn Whisper, article, plain-text, short podcasts, and other routes where the transcript is authoritative.
- Podcast length: <short|long|n/a>  ← only set when content type is podcast
- Chunk offsets: <comma-separated minute marks if long, otherwise "n/a">
- Whisper model used: <small|medium|large-v3|n/a>
- Directives: <parsed directives or "none">
- Display only: <true|false>
- Date: <YYYY-MM-DD>

## For standard video/audio with usable transcript (YouTube captions/Whisper, LinkedIn Whisper, FB video-audio with non-degenerate transcript, short podcasts)
Read /tmp/url-analyzer/<slug>.txt as the authoritative content. No thumbnail file is expected. Proceed to Step 3.

## For local-folder content (TRANSCRIPT_SOURCE=ocr, multiple .jpg files + paths-mapping)
Files: /tmp/url-analyzer/<slug>-1.jpg through <slug>-N.jpg (copied from the user's source folder tree).
Also: /tmp/url-analyzer/<slug>-paths.txt — a one-per-line mapping of `<index>: <relative subfolder path>` preserved from the original folder structure.

When OCR-ing, read `<slug>-paths.txt` first to give each image its original subfolder context (e.g., `before-photos/`, `week-1/`, `control-group/`). The subfolder names often carry semantic meaning the OCR can't infer. Proceed to Step 3 after writing the combined OCR+visual analysis to `/tmp/url-analyzer/<slug>.txt`.

## For single-image content (TRANSCRIPT_SOURCE=ocr, exactly one .jpg)
File: /tmp/url-analyzer/<slug>-1.jpg only.

The Playwright scraper produced a single image for a single-image post (PLAYLIST_COUNT was empty/1 in the Mode F probe). Treat as a degenerate image-carousel with N=1; no visual deduplication needed. Note that the scraper may also have collected explore-panel decoys (other posts on the page) — these were filtered out by the parent before dispatch and you should only see the target image.

## For Instagram/Facebook reels (Mode E) — dual-input pattern
EVERY Instagram/Facebook reel has BOTH a transcript and a thumbnail. You MUST inspect both:
1. Read /tmp/url-analyzer/<slug>.txt.
2. Compute the degenerate-transcript check yourself (the parent forwards `Transcript degenerate: unknown` for Mode E and does NOT pre-compute):
   - Run `wc -w < /tmp/url-analyzer/<slug>.txt`. If the count is `<30`, mark the transcript as degenerate.
   - Also mark as degenerate when the transcript reads as song lyrics, music description (e.g., `ДИНАМИЧНАЯ МУЗЫКА`, `MUSIC`, `музыка`), or a single-word hallucination (`You`, `Hehehee`, `Yeah`).
3. Run Tesseract on /tmp/url-analyzer/<slug>.jpg: `tesseract /tmp/url-analyzer/<slug>.jpg stdout --dpi 300`.
4. Use the Read tool to view the thumbnail visually (text overlay, brand, charts, gestures).
5. If the transcript is degenerate (per step 2), treat the THUMBNAIL TEXT OVERLAY as authoritative for claim extraction. Reels lead with the hook on-screen.
6. If both transcript and thumbnail are uninformative, return Grade C / "no claims extractable" rather than fabricating.

## For silent-video content (TRANSCRIPT_SOURCE=ocr, no transcript file)
There is only a thumbnail. Run Tesseract + Read tool on /tmp/url-analyzer/<slug>.jpg. Write combined OCR + visual analysis to /tmp/url-analyzer/<slug>.txt before proceeding to Step 3.

## For image-carousel content (TRANSCRIPT_SOURCE=ocr, multiple .jpg files)
Run Step 2 Path C first: use Tesseract OCR on images at /tmp/url-analyzer/<slug>*.jpg
and Read tool for visual analysis, then save combined output to /tmp/url-analyzer/<slug>.txt.

## For article content (TRANSCRIPT_SOURCE=html) or plain-text content (TRANSCRIPT_SOURCE=plain-text)
Step 2 is a no-op — the transcript file at /tmp/url-analyzer/<slug>.txt was already produced
by Mode H or Mode K in Phase 1. Read it directly and proceed to Step 3.

## For long podcast content (CONTENT_TYPE=podcast, PODCAST_LENGTH=long)
The transcript at /tmp/url-analyzer/<slug>.txt is segmented with `=== Chunk N (~M min mark) ===`
headers, one per ~10-minute window (already produced by Step 2 Path D in Phase 1).
1. Group your Step 4 claim extraction by chunk: list each chunk's primary claims under its timestamp header.
2. When citing a specific claim in your Verdict or ELI5 section, include the approximate timestamp
   range in parentheses, e.g. `(claimed around the 40 min mark)`.
3. In the Verdict section, explicitly note whether the show's accuracy holds consistently throughout
   or varies by segment — e.g. "Strong fact base in the first hour; speculative claims in the closing 20 min."
4. Channel reputation (Step 4c) treats the show + host as the source channel (e.g. "The Daily / Michael Barbaro").
5. If `Transcript degenerate=true` (sub-30 words per chunk average across all chunks — almost certainly
   silence/music or non-speech content), return Grade C / "no claims extractable" rather than fabricating.
   The Step 7 entry will still be `analyzed`, not `failed`.

## For short podcast content (CONTENT_TYPE=podcast, PODCAST_LENGTH=short)
Treat the transcript like a video — single-pass claim extraction, no chunk grouping. Channel reputation
still uses the podcast show + host as the source channel.

## Step 3: Classify content
Read the transcript and classify as Medical or General Science.
<include Step 3 instructions verbatim>

## Step 4: Analyze
If Medical: perform EBM SORT analysis using the rubric below.
If General Science: extract and validate each claim.
Then assess channel/handle reputation.
<include Step 4a/4b/4c instructions verbatim>

## EBM Reference (for medical content only)
<include full contents of ebm-reference.md>

## Step 5: Save analysis
If DISPLAY_ONLY=false: save to ~/Documents/truth-analyses/<date>-<slug>.md
and copy to ~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/
If DISPLAY_ONLY=true: return the full analysis text in your final response. If the analysis markdown contains any line consisting solely of `---` or the literal string `---END RESULT---`, base64-encode the entire markdown and emit it as `display_analysis: base64:<encoded>` in the `---RESULT---` trailer to avoid accidentally terminating the parent's parser.
<include Step 5 template verbatim>

## Step 6: Cleanup
Delete temp files for this URL only: /tmp/url-analyzer/<slug>*
Never delete the analysis file or original source folders.

## Required response format
End your response with exactly this block so the parent can parse your result. Use the **literal** delimiters `---RESULT---` and `---END RESULT---` — these must be the only occurrences of these exact strings in the trailer; the parent finds the block by searching from the END of your response backward for `---END RESULT---`, then matching to the nearest preceding `---RESULT---`.

For multiline `display_analysis` content (which may itself contain `---` dividers, e.g. EBM SORT rubric separators or the saved-analysis template's own dividers), base64-encode the markdown and prefix with `base64:`. Plain inline markdown and `none` remain backward-compatible.

---RESULT---
status: success|failed
slug: <slug>
analysis_path: <path to saved .md file, or "none" if display-only>
content_type: Medical|General Science
title: <video/post title>
url: <clean_url>
display_analysis: none | <inline-markdown-without-triple-dashes> | base64:<base64-encoded full analysis markdown>
error: <error message if failed, otherwise "none">
---END RESULT---
```

The parent reads `ebm-reference.md` once and injects its contents into every sub-agent prompt that might need it (all of them, since classification happens inside the sub-agent).

### Result collection

After all Phase 1 downloads are complete and all sub-agents have been dispatched:

1. Poll each sub-agent using `AwaitShell` or by reading its output file, waiting for all to complete.
2. Parse the `---RESULT---` block from each sub-agent's final response. Locate the block by searching from the END of the response backward for `---END RESULT---`, then matching to the nearest preceding `---RESULT---` — this avoids mis-terminating on any inner `---` dividers in the body.
3. Collect all results into `RESULTS[]`:
   - Successful analyses (with file paths)
   - Failed analyses (with error reasons)
   - Display-only analyses (with returned markdown text)
   - Duplicates (recorded earlier in Phase 0 / Step 0b)
4. For display-only results: if `display_analysis` starts with `base64:`, decode the remainder (`base64 -d` or Python `base64.b64decode`) before rendering. Plain inline markdown and `none` render as-is. Output the resulting `display_analysis` text to the user in the conversation.

Report:
```
⏳ Awaiting N sub-agents... (M completed, K in progress)
✓ All sub-agents complete: X succeeded, Y failed, Z display-only
```

Then proceed to **Step 7 (batch)**.

### Edge cases

**Display-only URLs** (`DISPLAY_ONLY=true`):
- The sub-agent runs Steps 3–4 normally but skips Step 5 file save. Instead, it returns the full analysis markdown in the `display_analysis` field of its result.
- The parent displays the returned analysis text in the conversation after collecting all results.
- These URLs are not added to `## Processed` in the batch Step 7 update.

**Sub-agent failure**:
- If a sub-agent crashes, times out, or returns `status: failed`, the parent records the error.
- The URL is added to `## Processed` as a failed entry with the error reason from the sub-agent's result.
- Other sub-agents are not affected — each is fully independent.

**Local folder entries**:
- Dispatched as sub-agents after image staging (Mode I copy step) during Phase 0/1.
- The sub-agent runs Step 2 Path C (OCR + visual analysis) first, then Steps 3–6.
- No inter-request delay is consumed, so these sub-agents are dispatched immediately.

**Partial completion** (e.g., user interrupts mid-run):
- Any sub-agents that already completed will have saved their analysis files locally — these are safe.
- Any sub-agents still running will be interrupted — their temp files may remain in `/tmp/url-analyzer/`.
- `watch-urls.md` will NOT have been updated (batch Step 7 hasn't run yet), so all URLs remain in `## Pending` for a clean re-run.
- Re-running the skill will re-triage all pending URLs. Previously saved analysis files will be detected as duplicates via Check B slug match, so no redundant work occurs.
- The Phase 1 manifest (`/tmp/url-analyzer/manifest.tsv`) is truncated on every Phase 1 start (after the singleton lock is held). Any "OK" rows for URLs whose sub-agents did not complete before interruption are lost — those URLs will be re-downloaded on the next run. This is acceptable because Check B slug match still prevents redundant analysis, but it does consume a fresh rate-limit budget per re-run.
- The `/tmp/url-analyzer/` working directory is NOT cleaned between runs. Stale `<slug>.mp3`, `<slug>.jpg`, `<slug>-N.jpg`, and `<slug>.whisper.done` files from interrupted runs may collide with new downloads. If a re-run produces unexpected results, manually `rm -f /tmp/url-analyzer/*` before retrying.
- The Phase 1 singleton lockdir at `/tmp/url-analyzer/phase1.lockdir` is removed automatically on process exit (the EXIT trap fires on clean exit and most signals; `kill -9` is the exception). If you suspect a stuck lockdir, `cat /tmp/url-analyzer/phase1.lockdir/pid` shows the holder PID — verify with `kill -0 $HOLDER`; if dead, `rm -rf /tmp/url-analyzer/phase1.lockdir` is safe. The next invocation's PID-liveness branch performs the same cleanup automatically.

**Inline URL auto-detection** (URL provided directly in the user's message):
- `DISPLAY_ONLY=true` is set automatically. Only one URL to process.
- Sub-agent dispatch still applies: a single sub-agent is spawned for the analysis.
- The parent displays the result in the conversation. No `watch-urls.md` update or git sync.

---

## Phase 1 Step 2: Extract text content (pipelined into Phase 1 Step 1)

> **Pipelining note**: For URL entries, Step 2 now runs **during Phase 1** — either inline (captions → instant VTT-to-text) or as a background process (Whisper running during the inter-request delay). By the time the sub-agent starts, the transcript is already available.
>
> For **local folder entries** (Path C — OCR + visual analysis), Step 2 runs inside the sub-agent, since it requires LLM vision capabilities that cannot be backgrounded.

No network calls. No delays. Runs entirely on local files.

The extraction method depends on the content type:
- **Video/audio content** (`TRANSCRIPT_SOURCE=captions` or `whisper`) → Path A or B below (pipelined into Phase 1 delays)
- **Image content** (`TRANSCRIPT_SOURCE=ocr`) → Path C below (runs in Phase 2)
- **Article content** (`TRANSCRIPT_SOURCE=html`) → No-op. The transcript was already produced by Mode H in Phase 1.
- **Plain-text content** (`TRANSCRIPT_SOURCE=plain-text`) → No-op. The transcript was already produced by Mode K in Phase 1.
- **Long podcast content** (`CONTENT_TYPE=podcast`, `PODCAST_LENGTH=long`) → Path D below (chunked Whisper, parallel, runs as a background process during Phase 1 delay; can take 5–15 min).
- **Short podcast content** (`CONTENT_TYPE=podcast`, `PODCAST_LENGTH=short`) → Path B (existing single-pass Whisper `small`).

---

### Path A — Convert captions to plain text (`TRANSCRIPT_SOURCE=captions`)

**Progress indicator**: `⏳ Step 2/7: Converting captions to plain text...`

Locate the downloaded `.vtt` file (e.g. `/tmp/url-analyzer/<slug>.en.vtt` or `/tmp/url-analyzer/<slug>.en-orig.vtt`). Run the following Python one-liner to strip all VTT metadata, timing lines, HTML tags, and caption duplication artifacts, producing a clean plain-text transcript:

```bash
python3 - << 'EOF'
import re, glob, sys

# Find the VTT file
vtt_files = glob.glob('/tmp/url-analyzer/<slug>*.vtt')
if not vtt_files:
    sys.exit("No VTT file found")

content = open(vtt_files[0], encoding='utf-8').read()

# Remove WEBVTT header and metadata block
content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
# Remove timestamp lines (00:00:00.000 --> 00:00:00.000 align:start position:0%)
content = re.sub(r'\d{1,2}:\d{2}[\d:.]+\s*-->\s*\d{1,2}:\d{2}[\d:.]+[^\n]*\n', '', content)
# Remove HTML tags (position/colour tags YouTube embeds in auto-captions)
content = re.sub(r'<[^>]+>', '', content)
# Remove cue sequence numbers (lines containing only digits)
content = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)
# Remove NOTE blocks
content = re.sub(r'^NOTE\b.*$', '', content, flags=re.MULTILINE)

# Collect non-empty lines and deduplicate consecutive identical lines
# (auto-captions repeat the same phrase across overlapping cues)
lines = [l.strip() for l in content.splitlines() if l.strip()]
deduped = []
for line in lines:
    if not deduped or line != deduped[-1]:
        deduped.append(line)

print(' '.join(deduped))
EOF
> /tmp/url-analyzer/<slug>.txt
```

#### Timestamp filtering (if `TIMESTAMP_RANGE=true`)

If a timestamp range was specified, filter the VTT file **before** converting — keep only cue blocks that overlap with the requested `[START, END]` window:

```bash
python3 - << 'EOF'
import re, glob, sys

START = '<START_IN_SECONDS>'   # e.g. 300  for 00:05:00
END   = '<END_IN_SECONDS>'     # e.g. 900  for 00:15:00

def ts_to_sec(t):
    parts = t.strip().replace(',', '.').split(':')
    parts = [float(p) for p in parts]
    return sum(v * 60**(len(parts)-1-i) for i, v in enumerate(parts))

vtt_files = glob.glob('/tmp/url-analyzer/<slug>*.vtt')
if not vtt_files:
    sys.exit("No VTT file found")

content = open(vtt_files[0], encoding='utf-8').read()
blocks = re.split(r'\n{2,}', content)

filtered = []
for block in blocks:
    m = re.search(r'(\d{1,2}:\d{2}[\d:.]+)\s*-->\s*(\d{1,2}:\d{2}[\d:.]+)', block)
    if m:
        b_start = ts_to_sec(m.group(1))
        b_end   = ts_to_sec(m.group(2))
        if b_end >= float(START) and b_start <= float(END):
            text = re.sub(r'\d{1,2}:\d{2}[\d:.]+\s*-->\s*\d{1,2}:\d{2}[\d:.]+[^\n]*\n?', '', block)
            text = re.sub(r'<[^>]+>', '', text).strip()
            if text:
                filtered.append(text)

lines = []
for chunk in filtered:
    for line in chunk.splitlines():
        line = line.strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)

print(' '.join(lines))
EOF
> /tmp/url-analyzer/<slug>.txt
```

**After conversion**: Report `✓ Step 2/7: Transcript ready from captions (N words)`

---

### Path B — Whisper transcription (`TRANSCRIPT_SOURCE=whisper`)

**Progress indicator**: `⏳ Step 2/7: Transcribing audio with Whisper...`

Whisper runs entirely locally on the downloaded `.mp3`. No delays or rate-limiting rules apply.

```bash
whisper /tmp/url-analyzer/<slug>.mp3 --model small --output_format txt --output_dir /tmp/url-analyzer/
```

Whisper already segments by timestamp internally; no post-processing is needed for timestamp-range audio (the file was already trimmed in Phase 1).

Capture the output `.txt` file as the transcript.

#### Music / hallucination detection (Instagram & Facebook only)

Whisper on a music-only or near-silent Instagram reel routinely emits one of these patterns:
- Empty file (0 bytes)
- A single token: `You`, `Hehehee`, `Yeah`
- Foreign-language music description: `ДИНАМИЧНАЯ МУЗЫКА`, `музыка`, `MUSIC`
- A few song-lyric fragments unrelated to the post (e.g., `She hit the floor, low low low`)

**The degenerate-transcript check runs INSIDE the sub-agent, not in the parent.** The parent does not inspect the transcript after Whisper finishes — it only forwards `Transcript degenerate: unknown` in the sub-agent prompt for Mode E / long-podcast routes (see "## For Instagram/Facebook reels (Mode E) — dual-input pattern" in the dispatch template). The sub-agent runs `wc -w < /tmp/url-analyzer/<slug>.txt` itself and applies the heuristic below.

The heuristic the sub-agent must apply:
1. Word count `<30` → degenerate.
2. Transcript reads as song lyrics, music description (`ДИНАМИЧНАЯ МУЗЫКА`, `MUSIC`, `музыка`), or a single-word hallucination (`You`, `Hehehee`, `Yeah`) → degenerate, even if word count ≥30.
3. When degenerate: treat the transcript as zero-information noise, extract claims primarily from the thumbnail's text overlay via OCR + visual analysis (the thumbnail was already downloaded in Mode E), and if neither transcript nor thumbnail provides extractable content, return Grade C / "no claims extractable" rather than fabricating.

**Do not gate on language**: Russian "ДИНАМИЧНАЯ МУЗЫКА" is a music description, not a Russian post. The word-count + lexical-pattern checks catch this without requiring per-language logic.

**After transcription completes**: Report `✓ Step 2/7: Transcription complete via Whisper (N words; sub-agent will assess degeneracy)`

---

### Path C — OCR + visual analysis (`TRANSCRIPT_SOURCE=ocr`)

**Progress indicator**: `⏳ Step 2/7: Extracting text from images with OCR...`

For image posts, extract text using Tesseract OCR and analyze visual content using Claude's vision capabilities.

#### Step C-1: OCR text extraction

Find all downloaded images and run OCR on each:

```bash
for img in /tmp/url-analyzer/<slug>*.{jpg,jpeg,png,gif,bmp,webp}; do
  [ -f "$img" ] || continue
  tesseract "$img" stdout --dpi 300 2>/dev/null
done > /tmp/url-analyzer/<slug>.txt
```

If tesseract is not installed, install it first:

```bash
# macOS
brew install tesseract

# Verify installation
tesseract --version
```

#### Step C-2: Visual content analysis (with subfolder context)

Read each image file using Claude's vision API to extract:
1. **Text content**: Any visible text, captions, or overlays (validates OCR results)
2. **Visual claims**: Charts, graphs, infographics, before/after photos, product labels
3. **Context**: People, settings, branding, emotional appeals
4. **Implied claims**: What health/science claims are suggested by the imagery, even if not stated explicitly?

**For local folder entries**: If a `<slug>-paths.txt` file exists (created in Mode I), use it to provide subfolder context for each image. This helps identify organizational structure (e.g., "before" vs "after" folders, numbered sequences, date-based organization).

For each image, use the Read tool to view it, then analyze:
- What factual claims are made visually (graphs, charts, statistics)?
- Are there any misleading visual techniques (cropped context, cherry-picked comparisons, manipulated images)?
- Does the text overlay match what's shown in the image?
- **If from local folder**: Does the subfolder name provide meaningful context (e.g., "before-surgery/", "week-1/", "control-group/")?

Combine OCR text + visual analysis into a single content summary saved to `/tmp/url-analyzer/<slug>.txt`.

**Format**:
```
=== Image 1 ===
Source: [subfolder path if from local folder, otherwise "carousel image 1"]
OCR Text: [extracted text]
Visual Content: [description of what's shown]
Claims: [factual claims made by this image]

=== Image 2 ===
Source: [subfolder path if from local folder, otherwise "carousel image 2"]
[repeat for each image in carousel]

=== Combined Analysis ===
[summary of all claims across all images]
[Note organizational patterns if from nested folders]
```

**After analysis**: Report `✓ Step 2/7: Text extraction complete via OCR + visual analysis (N images analyzed across M subfolders, K words extracted)`

---

### Path D — Chunked Whisper for long podcasts (`TRANSCRIPT_SOURCE=whisper`, `PODCAST_LENGTH=long`)

**Progress indicator**: `⏳ Step 2/7: Splitting long podcast into 10-minute chunks for parallel Whisper transcription...`

Long podcasts (>30 min, classified by Step 1.5) bypass Path B and run a chunked Whisper pipeline. Chunking is required because single-pass Whisper on a 90-minute file takes 15–30 minutes and risks running out of GPU memory; parallel chunks finish in ~5–10 minutes wall-clock with the `medium` model.

**Step D-1: Split with ffmpeg segment muxer (re-encoding, NOT `-c copy`)**

```bash
mkdir -p /tmp/url-analyzer/${SLUG}-chunks
ffmpeg -y -i "$AUDIO_PATH" \
  -f segment -segment_time 600 -reset_timestamps 1 \
  -c:a libmp3lame -q:a 4 \
  /tmp/url-analyzer/${SLUG}-chunks/chunk-%03d.mp3

CHUNK_COUNT=$(ls /tmp/url-analyzer/${SLUG}-chunks/chunk-*.mp3 2>/dev/null | wc -l | tr -d ' ')
if [ "$CHUNK_COUNT" -eq 0 ]; then
  FAIL_MSG="ffmpeg produced zero chunks from $AUDIO_PATH — file may be corrupt"
  exit_failed
fi
```

**Re-encoding rationale**: `-c copy` on the segment muxer can leave dangling frames at chunk boundaries that Whisper transcribes as garbage (similar issue to LinkedIn DASH HE-AAC corruption documented in Mode D). `-c:a libmp3lame -q:a 4` re-encodes each chunk cleanly (CPU cost ~30s per hour of audio on modern hardware) at ~165 kbps VBR. The CPU tradeoff is worth the transcript quality.

`$AUDIO_PATH` is used (not a hardcoded `.mp3` path) so Mode O sources with `.m4a` or `.wav` extensions are handled uniformly — ffmpeg decodes any of them and re-encodes the chunks to mp3.

**Step D-2: Parallel Whisper with portable concurrency cap**

```bash
# $MAX_WHISPER_JOBS set by Step 1.5 (1 for large-v3, 2 otherwise)
# macOS bash 3.2 lacks `wait -n`, so use PID array + polling
PIDS=()
for chunk in /tmp/url-analyzer/${SLUG}-chunks/chunk-*.mp3; do
  [ -f "$chunk" ] || continue
  while [ "$(jobs -r | wc -l)" -ge "$MAX_WHISPER_JOBS" ]; do sleep 2; done
  whisper "$chunk" --model "$WHISPER_MODEL" \
    --output_format txt \
    --output_dir /tmp/url-analyzer/${SLUG}-chunks/ &
  PIDS+=($!)
done
for pid in "${PIDS[@]}"; do wait $pid; done
```

**Step D-3: Stitch chunk transcripts with timestamp headers**

```bash
python3 - <<EOF > /tmp/url-analyzer/${SLUG}.txt
import glob
chunks = sorted(glob.glob('/tmp/url-analyzer/${SLUG}-chunks/chunk-*.txt'))
out = []
for i, ch in enumerate(chunks):
    offset_min = i * 10
    out.append(f"=== Chunk {i+1} (~{offset_min} min mark) ===")
    try:
        out.append(open(ch).read().strip())
    except FileNotFoundError:
        out.append("[chunk failed to transcribe]")
    out.append("")
print('\n'.join(out))
EOF
```

The transcript file at `/tmp/url-analyzer/${SLUG}.txt` is written atomically as the LAST step. The existing sub-agent "await transcript ready" dispatch logic detects this and spawns the analysis sub-agent.

**Step D-4: Degenerate transcript detection (mostly silence / music)**

```bash
TOTAL_WORDS=$(wc -w < /tmp/url-analyzer/${SLUG}.txt)
EXPECTED_MIN_WORDS=$(( CHUNK_COUNT * 30 ))   # ~30 words/chunk × N chunks
if [ "$TOTAL_WORDS" -lt "$EXPECTED_MIN_WORDS" ]; then
  TRANSCRIPT_DEGENERATE=true
fi
```

When `TRANSCRIPT_DEGENERATE=true`, the sub-agent prompt instructs the sub-agent to return **Grade C / "no claims extractable"** rather than fabricating (mirrors Mode E behavior for music-only Instagram reels). The Step 7 entry is still `analyzed` (not `failed`) because the analysis itself completed correctly — it just found no claims.

**Only ffmpeg-level chunking failure (Step D-1) produces a `failed` entry**; transcription-then-empty is a successful analysis with no claims.

**After Path D**: Report `✓ Step 2/7: Long podcast transcription complete via chunked Whisper (N chunks × ~10 min, model: $WHISPER_MODEL, $TOTAL_WORDS words total; degenerate=$TRANSCRIPT_DEGENERATE)`

---

## Step 3: Classify the content (Phase 2 — runs inside sub-agent)

**Progress indicator**: `⏳ Step 3/7: Classifying content type...`

Read the extracted text (transcript for video/audio, OCR output for images) and determine the content type:

**Medical** — content is medical if it mentions any of:
- Diagnoses, symptoms, diseases, or conditions
- Drugs, supplements, dosages, or treatments
- Clinical trials, studies, or patient outcomes
- Surgery, procedures, or medical devices
- Claims about health benefits or risks

**General science** — everything else: physics, chemistry, biology, psychology, nutrition (non-clinical), technology, environment, astronomy, etc.

If genuinely ambiguous, classify as **General science** and note the ambiguity.

**After classification**: Report `✓ Step 3/7: Classified as [Medical | General Science]`

---

## Step 4a: Medical content — EBM SORT Analysis (Phase 2 — runs inside sub-agent)

**Progress indicator**: `⏳ Step 4/7: Performing EBM SORT analysis...`

Read [ebm-reference.md](ebm-reference.md) for the full rubric before starting.

EBM SORT = **Strength Of Recommendation Taxonomy**. It grades clinical recommendations based on the quality and type of evidence behind them. Apply in two passes:

### Pass 1 — Four analysis lenses

Work through the transcript using these four lenses (these are analytical dimensions, not the SORT acronym itself):

- **Safety**: What harms, side effects, or risks are mentioned or omitted? Are they quantified with absolute numbers (not just relative risk)?
- **Outcomes**: Are claims backed by *patient-oriented* evidence (POEMs — mortality, morbidity, quality of life) or only *disease-oriented* evidence (DOEs — lab values, imaging, biomarkers)? DOEs do not always translate to patient benefit.
- **Risks of bias**: What is the study design (RCT > cohort > case series > anecdote)? Who funded it? Is there cherry-picking, missing comparators, or undisclosed conflicts of interest?
- **Total evidence**: Is this claim consistent with or contradicted by the broader body of literature? Is the cited study an outlier?

### Pass 2 — Assign a SORT grade

Based on Pass 1, assign one of:

- **Grade A** — Consistent, good-quality patient-oriented evidence (POEMs from well-designed RCTs or systematic reviews)
- **Grade B** — Inconsistent or limited-quality patient-oriented evidence, or good-quality disease-oriented evidence only
- **Grade C** — Consensus, disease-oriented evidence, expert opinion, usual practice, or case series only

See `ebm-reference.md` for grade decision rules and edge cases.

**Peer-reviewed citations**: End the analysis with 3–5 real, specific citations from:
- PubMed (pubmed.ncbi.nlm.nih.gov)
- Cochrane Library (cochranelibrary.com)
- BMJ Evidence-Based Medicine (ebm.bmj.com)

Format each citation as: `Author(s), Title, Journal, Year — [link]`

---

## Step 4b: General science — Claim validation (Phase 2 — runs inside sub-agent)

**Progress indicator**: `⏳ Step 4/7: Validating science claims...`

1. **Extract claims**: List each distinct factual claim made in the content (transcript or images) as a numbered bullet.

2. **For each claim**:
   - State whether the claim is **supported**, **contested**, or **refuted** by current scientific consensus
   - Briefly explain the mechanism or evidence that would prove or disprove it (e.g., reproducible experiment, peer consensus, physical law)
   - Note any important caveats, nuances, or missing context
   - **For image-based claims**: Note if the visual presentation is misleading (e.g., cropped graphs, unlabeled axes, cherry-picked comparisons, before/after photos without controls)

3. **Find validation sources**: For each major claim, search the broader web for credible content that demonstrates, validates, or refutes it. Sources to consider:
   - **Videos**: YouTube channels from established science communicators (e.g., Veritasium, SciShow, PBS Space Time, Kurzgesagt, 3Blue1Brown), Vimeo, university/institution portals, TED/TEDx, PBS, BBC, National Geographic, Smithsonian Channel clips, conference talks from established institutions
   - **Articles**: Peer-reviewed papers, fact-checking sites (Snopes, FactCheck.org, Health Feedback), reputable science journalism (Scientific American, Nature News, Science News)
   - **Images**: Original sources of charts/graphs, reverse image search for context, fact-checker analyses of viral images

   **Credibility filter**: Only link content from verified, named creators or institutions. Skip sources that are anonymous, lack citations, or make extraordinary claims without evidence. Flag any claim where no credible validation exists.

---

## Step 4c: Channel / handle reputation (Phase 2 — runs inside sub-agent, for all URL content)

**Progress indicator**: `⏳ Step 4c/7: Assessing channel / handle reputation...`

Independent of the per-claim analysis in Step 4a/4b, briefly characterize the source channel, handle, or author that posted this content. This helps the reader weight the analysis against the creator's track record.

1. Identify the source:
   - For URL entries (video/audio/image): extract the uploader/channel/handle from the platform. Use `yt-dlp --print "%(uploader)s|%(uploader_id)s|%(channel)s|%(channel_url)s" '<URL>'` or inspect the `uploader`, `uploader_id`, and `channel` fields in `yt-dlp -J '<URL>'`. For Instagram/Facebook reels, `uploader_id` gives the handle. For LinkedIn, use the author name from the post URL slug.
   - For **article entries** (`CONTENT_TYPE=article`): the "source channel" is the publication. Use the URL's registrable domain (e.g. `nytimes.com`, `substack.com/@author`) and, if available, the article byline parsed from the HTML metadata (`<meta name="author">` or trafilatura's `metadata.author`). Research the publication and the byline author separately if both are present.
   - For **local folder entries**: there is no channel. Record `Source channel: N/A (local folder)` and skip the reputation paragraph.
   - For **plain-text entries** (`CONTENT_TYPE=plain-text`): there is no channel. Record `Source channel: N/A (plain-text file)` and skip the reputation paragraph.
   - For **channel-enumerated items** (carrying `CHANNEL_HANDLE`/`CHANNEL_PLATFORM` from Phase 0 Step 0): use that handle directly — do NOT run a per-item `yt-dlp --print "%(uploader)s"` lookup. Because all items from one channel share a handle, the `### @<handle>` cache lookup below naturally computes the reputation once and reuses it for every sibling item in the batch (the first item researches and writes the cache; the rest hit the fresh cache entry).

2. Check the persistent handles cache first:
   - Read `~/Documents/truth-analyses/.handles-cache.md` if it exists.
   - The cache is a markdown file with one section per handle (heading: `### @<handle>`), containing the most-recent reputation paragraph, the date researched, and source URLs used.
   - If the handle is present AND the cache entry is less than 90 days old: reuse the cached paragraph verbatim and skip the web-search step (step 3 below).
   - If the handle is present BUT older than 90 days: use the cached paragraph as a starting point, perform a single targeted web search for any new fact-checks or retractions since the cache date, and emit an updated paragraph.
   - If the handle is NOT present: proceed to step 3 (research from scratch) AND, after writing your analysis, append a new `### @<handle>` section to the cache with today's date, the reputation paragraph you produced, and citation URLs used.
   - Use a `mkdir`-lockdir append guard (the same pattern as the Phase 1 process-singleton guard, because `flock(1)` is not installed on macOS):
     ```bash
     LOCKDIR=/tmp/url-analyzer/handles-cache.lockdir
     while ! mkdir "$LOCKDIR" 2>/dev/null; do
       HOLDER=$(cat "$LOCKDIR/pid" 2>/dev/null)
       if [ -z "$HOLDER" ] || ! kill -0 "$HOLDER" 2>/dev/null; then
         rm -rf "$LOCKDIR"   # stale lock from a dead writer
       else
         sleep 1             # active writer, wait briefly
       fi
     done
     echo $$ > "$LOCKDIR/pid"
     # ... append your `### @<handle>` section to ~/Documents/truth-analyses/.handles-cache.md ...
     rm -rf "$LOCKDIR"
     ```
   - The cache file lives at `~/Documents/truth-analyses/.handles-cache.md` (sibling to the analyses directory) — explicitly OUTSIDE the three skill-mirror locations (`~/.claude/skills/`, `~/.cursor/skills/`, `~/AI-Lab-Bench/LLM_Skills/`) so mutable runtime state does not break the md5-identity invariant the mirrors maintain.

3. Research the handle (only if not served by the cache; 1 web search, max 2 if the first is ambiguous):
   - Search for the handle/channel name plus terms like `fact check`, `controversy`, `misinformation`, `credentials`, `retraction`, `debunked`, or `reputation`.
   - Prefer signals from fact-checker coverage (Health Feedback, Snopes, FactCheck.org, Full Fact, AltNews, BOOM Live), mainstream journalism, academic or professional credentials on verified profiles, platform verification badges, and prior analyses of the same handle in `~/Documents/truth-analyses/`.
   - If the handle is obscure and produces no credible signal, say so explicitly — do not fabricate a reputation.

4. Write 2–4 sentences covering, where substantiated:
   - Typical content style (explainer, opinion/commentary, news aggregation, motivational, product promotion, satire, call-out, etc.).
   - Track record on truthfulness (prior fact-checks, retractions, misinformation flags — or, conversely, a clean peer-reviewed / institutional record).
   - Verified credentials or platform status (blue check, institutional affiliation, medical license, PhD) — only if substantiated.
   - Known conflicts of interest (product lines, sponsorships, political alignment) that materially affect how the content should be read.

5. Calibration rules:
   - Documented misinformation history → state it plainly with a specific example or citation.
   - Broadly reputable → state it plainly.
   - No credible signal either way → write: `No notable public record on this handle's truthfulness was found; evaluate this post on its own merits.`
   - Never infer reputation purely from follower count, aesthetics, or confidence of delivery.

This paragraph feeds the `## Channel Reputation` section of the Step 5 template.

---

## Step 5: Output format (Phase 2 — runs inside sub-agent)

### If `DISPLAY_ONLY=true` — return analysis in sub-agent result

**Progress indicator**: `⏳ Step 5/7: Preparing analysis for display...`

Instead of saving to a file, include the full analysis markdown in the `display_analysis` field of the sub-agent's `---RESULT---` block. Use the same template below to generate the content. Skip the "Sync to AI-Lab-Bench repository" sub-step entirely. The parent agent will display this text in the conversation after collecting all results.

After preparing, report `✓ Step 5/7: Analysis prepared for display (display-only mode — no files written).` and proceed to Step 6.

### If `DISPLAY_ONLY=false` (default) — save to file

**Progress indicator**: `⏳ Step 5/7: Saving analysis...`

Save to `~/Documents/truth-analyses/YYYY-MM-DD-<slugified-title>.md`:

```markdown
# Truth Analysis: <Post Title or Video Title>
**Source URL**: <URL>                                  ← for URL entries (video/audio/image/article/podcast-from-URL)
**Source**: Local folder: /path/to/folder (N images)   ← for local folder entries
**Source**: Plain-text file: /path/to/file.txt         ← for plain-text entries
**Source**: Local audio file: /path/to/file.mp3        ← for Mode O (local audio podcast) entries
**Analyzed**: YYYY-MM-DD
**Content type**: Medical | General Science
**Format**: Video | Audio | Image Post | Carousel (N images) | Article | Plain Text | Podcast (short) | Podcast (long, N chunks)

**Share?**: <one sentence recommendation: Yes/No/With caveats — would you share this with a scientifically curious friend who knows nothing about the topic, if your goal is for them to come away with an accurate understanding?>

## Summary
<2–3 sentence overview of what the content claims>

## Channel Reputation
**Source channel / handle**: <uploader / uploader_id / channel name, or "N/A (local folder)">
<2–4 sentences on the channel's typical content style, track record on truthfulness (prior fact-checks, retractions, or clean record), verified credentials, and any conflicts of interest. If no credible public record exists, state: "No notable public record on this handle's truthfulness was found; evaluate this post on its own merits.">

## Analysis

### [Medical: SORT Analysis | Science: Claim Validation]
<Full analysis here>

[For image content, include:]
### Visual Analysis
<Analysis of visual presentation: misleading techniques, context, emotional appeals>

## Evidence / Validation Links
<Citations or validation sources — videos, articles, fact-checks, original image sources>

## Verdict
<One-paragraph plain-language summary of how trustworthy this content is>

## ELI5 — Friend to Friend
<2–4 sentences explaining the verdict as if you're texting a friend who asked "hey is this legit?" Keep it casual, jargon-free, and honest. Use everyday analogies if they help. No hedging — give a clear thumbs-up, thumbs-down, or "it's complicated.">
```

**After saving**: Report `✓ Step 5/7: Analysis saved to ~/Documents/truth-analyses/YYYY-MM-DD-<slug>.md`

### Sync to AI-Lab-Bench repository

After saving the local copy, also copy the analysis file into the AI-Lab-Bench repo for later git sync:

```bash
# Ensure the target directory exists
mkdir -p ~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/

# Copy the analysis file
cp ~/Documents/truth-analyses/YYYY-MM-DD-<slug>.md \
   ~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/
```

If the copy fails (e.g., repo directory missing), report a warning but do **not** fail the URL:
```
⚠️  Could not copy analysis to AI-Lab-Bench repo — git sync will be incomplete for this file.
```

**After sync copy**: Update the report to `✓ Step 5/7: Analysis saved locally and staged for GitHub sync.`

---

## Step 6: Cleanup downloaded files (Phase 2 — runs inside sub-agent)

**Progress indicator**: `⏳ Step 6/7: Cleaning up temporary files...`

The `extract_audio` command downloads video/audio files and creates working directories in the current working directory. After the analysis is complete, delete all downloaded files and folders to save disk space.

**What to keep:**
- The original URL (already in watch-urls.md)
- The truth analysis markdown file in `~/Documents/truth-analyses/`

**What to delete** (only files belonging to this sub-agent's slug):
- `/tmp/url-analyzer/<slug>.*` — all temp files for this URL (`.mp3`, `.m4a`, `.wav`, `.mp4`, `.vtt`, `.srt`, `.jpg`, `.png`, `.txt`, `.meta`, `.feed.xml`, `_transcription.txt`)
- `/tmp/url-analyzer/<slug>-*.jpg` — carousel/folder images for this slug
- `/tmp/url-analyzer/<slug>-paths.txt` — subfolder mapping file if present
- `/tmp/url-analyzer/<slug>-chunks/` — entire directory (chunked Whisper output for long podcasts, Step 2 Path D)
- `/tmp/url-analyzer/sp-<EP_ID>.*` — Spotify pre-rename temp files (Mode L), if Mode L failed before the slug-rename step
- `/tmp/url-analyzer/feed-<HASH>.xml` — RSS feed XML cache (Mode N) — already renamed to `<slug>.feed.xml` on success
- Any folders created by `extract_audio` (typically long hash-named directories)

**Local folder entries**: Delete only copies in `/tmp/url-analyzer/` and intermediary files. **Never delete the original source folder or its contents.** The original folder path is user-managed data.

**Plain-text entries**: Delete only the copy at `/tmp/url-analyzer/<slug>.txt`. **Never delete the user's original `.txt` source file.**

**Article entries**: Delete the extracted body at `/tmp/url-analyzer/<slug>.txt`. There is no other state to remove.

**Podcast entries (Mode O — local audio)**: Delete only the copy at `/tmp/url-analyzer/<slug>.<ext>` (and chunks dir if Path D ran). **Never delete the user's original audio source file** — it lives outside `/tmp/url-analyzer/`.

**Podcast entries (Modes L/M/N)**: Delete the downloaded `.mp3`, the `.meta` and `.ytdlp.log` (Mode L), the `.feed.xml` (Modes M/N), and the chunks dir (Path D). No external user files to preserve.

**How to clean up:**
```bash
rm -f /tmp/url-analyzer/<slug>.*
rm -f /tmp/url-analyzer/<slug>-*.jpg
rm -f /tmp/url-analyzer/<slug>-paths.txt
rm -rf /tmp/url-analyzer/<slug>-chunks/
```

Do **not** delete files belonging to other slugs — other sub-agents may still be using them.

**After cleanup**: Report `✓ Step 6/7: Cleanup complete. Kept: analysis file. Removed: N MB of temporary files.`

---

## Step 7: Batch-update watch-urls.md (runs in parent, after all sub-agents complete)

**Progress indicator**: `📋 Step 7: Batch-updating watch-urls.md with N results...`

> **Why batch?** Sub-agents run concurrently. If each sub-agent updated `watch-urls.md` independently, concurrent file writes would cause race conditions and data loss. Instead, sub-agents skip Step 7 entirely. The parent collects all results and performs a single atomic update.

### If ALL URLs had `DISPLAY_ONLY=true` — skip this step

Do not update `watch-urls.md`. All URLs were one-off analyses displayed in the conversation. Report `✓ Step 7: Skipped watch-urls.md update (all URLs were display-only).` and proceed to post-processing.

### Batch update procedure

After collecting results from all sub-agents (plus duplicates and failures recorded by the parent):

1. Read the current `watch-urls.md` file.
2. Remove **all processed URLs** from `## Pending` in a single edit.
3. Append **all new entries** to `## Processed` in a single edit, directly below the `## Processed` heading (before any existing processed entries).

**Rules for updating the Processed section:**
- If `## Processed` already exists in the file, append all new entries directly below the heading, preserving everything else unchanged.
- If `## Processed` does not exist, create it as a new section at the end of the file.
- Never create a duplicate `## Processed` heading.
- Process entries in the same order they appeared in `## Pending` (preserves the user's original ordering).

### Entry formats (same as before, now written in batch)

**Normal entry** (sub-agent returned `status: success`):
```
- <URL> (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

If a directive was used, append it in parentheses for traceability:
```
- <URL> [transcript-only] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <URL> [00:05:00-00:15:00] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <URL> [transcript-only 00:05:00-00:15:00] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Local folder entry** (sub-agent returned `status: success`):
```
- /path/to/folder (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- /path/to/folder [title: My Title] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Article entry** (sub-agent returned `status: success`):
```
- <URL> [article] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <URL> [article title: My Title] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Plain-text entry** (sub-agent returned `status: success`):
```
- /path/to/file.txt [plain-text] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- /path/to/file.txt [plain-text title: My Title] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Podcast entry** (sub-agent returned `status: success`):
```
- <SPOTIFY_URL> [podcast] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <APPLE_URL> [podcast] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <APPLE_URL> [podcast] (analyzed YYYY-MM-DD; Apple GUID not found in RSS — analyzed newest episode "<title>" → truth-analyses/YYYY-MM-DD-<slug>.md)
- <RSS_URL> [podcast-rss] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <RSS_URL> [podcast-rss episode: 3] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <YOUTUBE_URL> [podcast] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <ANY_URL> [podcast whisper-model: large-v3] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- /path/to/file.mp3 [podcast] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- /path/to/file.m4a [podcast title: My Episode Title] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Duplicate entry** (detected by parent in Phase 0 or Step 0b):
```
- <URL> (duplicate of <original-URL> → see truth-analyses/<existing-file>.md)
```

**Failed entry** (download failed in parent, or sub-agent returned `status: failed`):
```
- <URL> (failed YYYY-MM-DD — rate limited after 3 retries, retry manually)
- <URL> (failed YYYY-MM-DD — all automated LinkedIn stages failed; replace with DASH manifest URL from Network tab)
- <URL> (failed YYYY-MM-DD — <specific error reason>)
```

**Failed local folder entry**:
```
- /path/to/folder (failed YYYY-MM-DD — path does not exist or is not a directory)
- /path/to/folder (failed YYYY-MM-DD — no supported image files found in folder tree)
- /path/to/folder (failed YYYY-MM-DD — folder structure exceeds maximum depth of 5 levels. Found: N levels)
```

**Channel entry** (expanded in Phase 0 Step 0). Record a nested **channel summary** PLUS one flat
per-item line each (so future Check A/B dedup sees the items normally — dedup parses the flat lines,
not the nested sub-bullets):
```
- <channel-url> [channel:N] (expanded YYYY-MM-DD — found M/N newest, processed P, duplicate D, failed F)
  - <item-url-1> → truth-analyses/YYYY-MM-DD-<slug>.md
  - <item-url-2> → failed: <reason>
- <item-url-1> (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md; expanded from <channel-url>)
- <item-url-2> (failed YYYY-MM-DD — <reason>; expanded from <channel-url>)
```
**Failed channel expansion** (enumeration produced no items):
```
- <channel-entry> (failed YYYY-MM-DD — channel enumeration failed: <reason>; retry: <action>)
- <channel-entry> (failed YYYY-MM-DD — Instagram cookies missing/login wall; export Firefox cookies and retry)
- <channel-entry> (failed YYYY-MM-DD — bare handle requires platform hint: platform:youtube or platform:instagram)
```

**Failed article entry**:
```
- <URL> [article] (failed YYYY-MM-DD — article body extraction produced too little text; site may be paywalled or JS-rendered)
- <URL> [article] (failed YYYY-MM-DD — fetch failed: <HTTP status or curl error>)
```

**Failed plain-text entry**:
```
- /path/to/file.txt [plain-text] (failed YYYY-MM-DD — file does not exist or is not a regular file)
- /path/to/file.txt [plain-text] (failed YYYY-MM-DD — plain-text entry must be a .txt file)
- /path/to/file.txt [plain-text] (failed YYYY-MM-DD — plain-text file is empty)
```

**Failed podcast entry** (status-semantics note: a degenerate transcript — sub-30 words/chunk avg, e.g. all silence/music — is `analyzed` with Grade C verdict, NOT `failed`. Only the failures below mark the entry `failed`):
```
# Spotify
- <SPOTIFY_URL> [podcast] (failed YYYY-MM-DD — Spotify exclusive / DRM-protected. Try the publisher's RSS feed instead; add as [podcast-rss].)
- <SPOTIFY_URL> [podcast] (failed YYYY-MM-DD — Spotify episode region-locked. Try via VPN or via the publisher's RSS feed [podcast-rss].)
- <SPOTIFY_URL> [podcast] (failed YYYY-MM-DD — Spotify rate-limited after exponential backoff retries exhausted. Retry manually after several hours.)

# Apple Podcasts
- <APPLE_URL> [podcast] (failed YYYY-MM-DD — Apple Podcasts: iTunes Lookup returned malformed JSON)
- <APPLE_URL> [podcast] (failed YYYY-MM-DD — Apple Podcasts: iTunes Lookup returned no results for podcast id N — likely removed or region-locked)
- <APPLE_URL> [podcast] (failed YYYY-MM-DD — Apple Podcasts: iTunes Lookup returned no feedUrl for podcast id N — likely Apple Podcasts Subscriptions-only)
- <APPLE_URL> [podcast] (failed YYYY-MM-DD — Apple Podcasts: feed URL requires auth (HTTP 4xx); likely paywalled)
- <APPLE_URL> [podcast] (failed YYYY-MM-DD — Apple Podcasts feed region-locked (HTTP 451))

# RSS
- <RSS_URL> [podcast-rss] (failed YYYY-MM-DD — URL did not return RSS or Atom XML at root (got: '<actual-tag>'))
- <RSS_URL> [podcast-rss] (failed YYYY-MM-DD — RSS parse error: <reason>)
- <RSS_URL> [podcast-rss] (failed YYYY-MM-DD — no <item> or <entry> elements found in feed)
- <RSS_URL> [podcast-rss] (failed YYYY-MM-DD — no audio enclosure found in selected item — video-only or transcript-only feed)

# Local audio (Mode O)
- /path/to/file.mp3 [podcast] (failed YYYY-MM-DD — local audio entry must be an absolute path)
- /path/to/file.mp3 [podcast] (failed YYYY-MM-DD — local audio file does not exist or is not a regular file)
- /path/to/file.xyz [podcast] (failed YYYY-MM-DD — local audio entry must have .mp3, .m4a, or .wav extension)
- /path/to/file.mp3 [podcast] (failed YYYY-MM-DD — local audio file is empty)
- /path/to/file.mp3 (failed YYYY-MM-DD — local audio file requires explicit [podcast] directive)   ← MALFORMED[] partition

# Path D long-podcast chunking
- <URL> [podcast] (failed YYYY-MM-DD — ffmpeg produced zero chunks from audio file — file may be corrupt)
```

**Display-only entry** (sub-agent returned `status: success` with `DISPLAY_ONLY=true`):
Do not add to `## Processed`. These are one-off analyses not tracked in `watch-urls.md`.

Failed entries remain actionable: re-add the URL to `## Pending` on a future run to retry it, or for LinkedIn post URLs, replace the entry with the DASH manifest URL (from the Network tab) and re-run.

**After batch update**: Report `✅ Step 7: watch-urls.md updated — N entries moved from Pending to Processed.`

---

## Post-processing: Sync analyses to GitHub

**Progress indicator**: `⏳ Post-processing: Syncing new analyses to GitHub...`

This step runs **once** after the batch Step 7 update completes. It pushes any new analysis files to the AI-Lab-Bench repository.

**If ALL processed URLs had `DISPLAY_ONLY=true`**: Skip this entire section. Report `ℹ️  GitHub sync skipped — all URLs were display-only (no files written).` and end.

### Pre-flight checks

Before attempting git operations, verify the repo is usable:

```bash
# Check 1: Does the repo directory exist?
if [ ! -d ~/AI-Lab-Bench/.git ]; then
  echo "⚠️  AI-Lab-Bench repo not found at ~/AI-Lab-Bench — skipping GitHub sync."
  exit 0
fi

# Check 2: Are there any new analysis files to push?
cd ~/AI-Lab-Bench
NEW_FILES=$(git status --porcelain LLM_Skills/url-truth-analyzer/truth-analyses/ 2>/dev/null)
if [ -z "$NEW_FILES" ]; then
  echo "ℹ️  No new analysis files to sync to GitHub."
  exit 0
fi
```

If either check fails, skip this step entirely with a warning — do not error out.

### Git workflow

```bash
cd ~/AI-Lab-Bench

# 1. Pull latest to avoid conflicts (rebase to keep history linear)
git pull --rebase origin main

# 2. Stage only the truth-analyses directory (never stage unrelated changes)
git add LLM_Skills/url-truth-analyzer/truth-analyses/*.md

# 3. Commit with a descriptive message
git commit -m "Add truth analyses: $(date +%Y-%m-%d)

Files added:
$(git diff --cached --name-only | sed 's/^/  /')"

# 4. Push to remote
git push origin main
```

### Error handling

| Failure point | Action |
|---|---|
| `git pull --rebase` fails (merge conflict) | Abort rebase (`git rebase --abort`), report warning, skip push. Files remain locally in both `~/Documents/truth-analyses/` and in the repo working tree for manual resolution. |
| `git add` finds no files | Skip commit and push. Report `ℹ️  No new files to commit.` |
| `git commit` fails | Report warning. Do not push. |
| `git push` fails (network, auth) | Report warning with the specific error. The commit is preserved locally — user can manually `cd ~/AI-Lab-Bench && git push origin main` later. |
| Repo directory missing | Already caught in pre-flight. Report and skip. |

**After all error cases**: The primary save location (`~/Documents/truth-analyses/`) is never affected. GitHub sync is best-effort — failure here never causes data loss or blocks the analysis workflow.

### Reporting

**On success**:
```
✅ GitHub sync complete: pushed N new analysis file(s) to AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/
   Commit: <short-hash> — <first line of commit message>
```

**On partial failure** (some files committed but push failed):
```
⚠️  GitHub sync incomplete: N file(s) committed locally but push failed.
   Run manually: cd ~/AI-Lab-Bench && git push origin main
```

**On skip** (no new files or repo missing):
```
ℹ️  GitHub sync skipped — <reason>.
```

---

## Dependencies

- `yt-dlp` — required for YouTube (Modes A/B), LinkedIn (Mode D), Facebook/Instagram (Modes E/F), Spotify (Mode L).
- `ffmpeg` + `ffprobe` — required for LinkedIn DASH (Mode D), trim (Step 1.4), duration probe (Step 1.5), and chunked Whisper splitting (Step 2 Path D). Available via `brew install ffmpeg` on macOS.
- `whisper` — Python package (`pip3 install --user --break-system-packages openai-whisper`). Required models depend on usage:
  - `small` (~250 MB) — default for short content (videos, short podcasts).
  - `medium` (~1.5 GB) — default for long podcasts (Step 2 Path D).
  - `large-v3` (~3 GB) — optional, activated via `[whisper-model: large-v3]`. When this model is used in Path D, chunked-Whisper concurrency is automatically capped at 1 to avoid OOM on 16 GB systems.
- `tesseract` — required for image OCR (Mode F, Mode I, Path C). `brew install tesseract`.
- `trafilatura` (preferred) or `pandoc` (fallback) — required for article body extraction (Mode H).
- `curl` — required for article fetching (Mode H), iTunes Lookup (Mode M), RSS feed + enclosure download (Mode N).
- `xml.etree.ElementTree` — Python stdlib. No install needed. Used for RSS/Atom parsing (Mode N).
- Python `playwright` + Chromium — required for Instagram carousel scraping (Mode F).
- Firefox with logged-in sessions — required for authenticated yt-dlp cookie extraction (LinkedIn, Facebook, Instagram, Spotify). iTunes Lookup and generic RSS feeds need no authentication.

---

## Out of scope (intentionally — these are NOT supported)

- **Speaker diarization** for podcasts (who-said-what) — would require `pyannote.audio` and heavy ML deps; not worth the maintenance burden.
- **Live podcast streams** — only completed episodes with downloadable audio.
- **Transcript-only mode for podcasts** — no native caption tracks exist on Spotify, Apple Podcasts, or generic RSS feeds. The `[transcript-only]` directive is silently ignored for podcast entries.
- **Per-chapter EBM SORT grading** — long podcasts get ONE overall SORT grade, with timestamp-keyed evidence callouts in the analysis text. Per-chapter grading would require chapter-level claim segmentation which is fragile.
- **Video-only RSS feeds** (no `<enclosure>` element pointing at audio) — fails with explicit message.
- **Transcript-only RSS feeds** — fails with the same "no audio enclosure" message.
- **Apple Podcasts Subscriptions** (paywalled, no public RSS) — iTunes Lookup returns no `feedUrl`; fails with explicit message.
- **Spotify Originals / Exclusives** (DRM-protected) — yt-dlp cannot extract; fails with explicit message pointing the user at the publisher's RSS.
- **Same-slug temp file collisions across runs** — if two unrelated podcasts produce identical episode title slugs (e.g. both titled "Episode 1"), the second one will overwrite the first's temp files mid-flight. In-batch dedup catches same-feed/same-episode-ID duplicates, but cross-podcast slug collision is documented and deferred. Fix would require per-entry temp subdirs (`/tmp/url-analyzer/<slug>-<shorthash>/`), an architectural change.
- **`jobs -r` concurrency cap scope** — Step 2 Path D's `jobs -r | wc -l` counts ALL background jobs in the sub-agent's shell, including unrelated ones. In practice the sub-agent shell is isolated and only runs chunked Whisper, so this is a non-issue.
