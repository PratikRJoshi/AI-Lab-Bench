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
```

**Directive rules:**
- Directives are placed on the same line as the URL, separated by a space.
- The `[...]` block is stripped before any URL is passed to `yt-dlp` or used for video ID extraction.
- Timestamps use `HH:MM:SS` or `MM:SS` format, separated by a hyphen. Both the start and end must be specified.
- Directives are case-insensitive: `[Transcript-Only]` and `[transcript-only]` are equivalent.
- If no directive is present, YouTube URLs default to **captions-first**: attempt to fetch captions, then fall back to audio download + Whisper if no captions are available. Non-YouTube platforms always use audio download (no captions available).
- **`[audio-only]`**: Forces audio download + Whisper transcription, skipping the caption attempt entirely. Use when auto-generated captions are known to be poor quality or in the wrong language.
- **Local folder paths**: If the entry starts with `/` (absolute path) instead of `http`, it is treated as a local folder containing images. All supported image files (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`) are treated as a single post. The `[transcript-only]` and timestamp directives are ignored for folder entries. Only flat directory scanning (no recursion into subdirectories).
- **`[display-only]`**: The sub-agent returns the analysis text instead of saving to a file; the parent displays it in the conversation. Skips Step 5 file save (analysis is returned in the sub-agent result instead), Step 6 cleanup still runs, Step 7 `watch-urls.md` update is skipped for this URL, and GitHub sync skips this URL. Useful for quick one-off checks or when the user provides a URL inline rather than via `watch-urls.md`. Can combine with other directives (e.g. `[display-only transcript-only]`). When a URL is provided directly in the user's message (not from `watch-urls.md`), `display-only` is implied automatically.
- **`[article]`**: Treats the URL as an HTML article/blog/news page rather than a video. The skill fetches the page with `curl` (or `WebFetch`) and extracts the readable body using `trafilatura` (preferred) or `pandoc -f html -t plain` (fallback). Skips yt-dlp, captions, audio download, and Whisper entirely. The extracted text becomes the transcript at `/tmp/url-analyzer/<slug>.txt`. The slug is derived from the article's `<title>` tag (or `[article title: ...]` if provided). Dedup uses Check B (slug match) only — Check A is skipped for article URLs. Inter-request delay still applies (the fetch is a server call). `[transcript-only]`, `[audio-only]`, and `[timestamp-range]` are silently ignored for articles.
- **`[plain-text]`**: Treats the entry as a path to a local `.txt` file containing the content to analyze. No network call. The file's contents are copied into `/tmp/url-analyzer/<slug>.txt` and the sub-agent runs Steps 3–6 directly. The slug is derived from the filename basename (without extension) or `[plain-text title: ...]` if provided. Both Check A and the `yt-dlp` part of Check B are skipped — dedup uses local slug match against `~/Documents/truth-analyses/` only. No inter-request delay, no batch cooldown, no retry logic (no server contacted). The path must end in `.txt` and the file must exist; otherwise the entry is marked failed. Other directives are ignored.

---

## Workflow overview

**Inline URL auto-detection**: When the user provides a URL directly in their message (not from `watch-urls.md`), treat it as `DISPLAY_ONLY=true` automatically. Skip Phase 0 dedup checks (no `watch-urls.md` to read), run Phase 1 + Phase 2 normally, display the analysis in the conversation, clean up temp files, and stop. No files are written, no `watch-urls.md` is updated, no GitHub sync runs.

**Inline plain-text auto-detection**: When the user pastes a block of plain text in their message (not a URL, not a path) and asks for truth analysis, treat it as `CONTENT_TYPE=plain-text` with `DISPLAY_ONLY=true` automatically. Write the pasted text to `/tmp/url-analyzer/inline-<timestamp>.txt`, dispatch a single sub-agent for Steps 3–6, display the analysis in the conversation, then clean up. No `watch-urls.md` entry is created. The slug for the temp file is `inline-<YYYYMMDD-HHMMSS>`. If the user provides an explicit title in their message, use that for the slug instead.

**Inline article URL auto-detection**: When an inline URL is clearly an article (e.g. domains like nytimes.com, medium.com, substack.com, wordpress.com, blog hosts) and not a known video/social platform, treat it as if `[article]` were specified. If ambiguous, ask the user once whether to treat it as an article or attempt video extraction.

Processing happens in **four phases** plus post-processing. Phase -1 (housekeeping) archives old data. Phase 0 is instant and local. Phase 1 pipelines server calls with local transcription **and dispatches sub-agents for analysis as each transcript becomes ready**. Phase 2 runs in parallel across sub-agents.

### Phase -1 — Housekeeping (automatic, runs before Phase 0)

Runs at the start of every `process watch-urls.md` invocation. Archives processed entries and analysis files older than 30 days. Skipped entirely for inline URL auto-detection (no `watch-urls.md` involved).

### Phase 0 — Batch triage (instant, local)

Before any server calls, run a single pass over ALL pending URLs:

1. Parse directives for every entry
2. Run Check A (video ID match) for every URL entry that doesn't have the `[article]` or `[plain-text]` directive, against the `## Processed` list. For `[article]` entries, Check A is an exact URL string match against processed URLs. For `[plain-text]` entries, Check A is skipped entirely.
3. Partition into five lists:
   - `DUPLICATES[]` — Check A matched; record for batch `watch-urls.md` update, no further processing
   - `NEEDS_PROCESSING[]` — video/audio/image URL entries requiring download + analysis
   - `LOCAL_FOLDERS[]` — local folder entries (skip Phase 1 downloads, dispatch sub-agents directly)
   - `ARTICLES[]` — entries with `[article]` directive (fetch HTML in Phase 1, then dispatch sub-agent)
   - `PLAIN_TEXT[]` — entries with `[plain-text]` directive (no fetch, dispatch sub-agent directly)

Phase 0 makes zero server calls. Duplicates are resolved instantly.

### Phase 1 — Download + transcribe + dispatch (rate-limited, pipelined)

For each URL in `NEEDS_PROCESSING`, **one at a time, in order**:

1. Step 0b: Check B title/slug match (server call — `yt-dlp --get-title`)
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

### Step 1: Parse all directives

For every pending entry, run Sub-step 0a (directive parsing — see below) to extract the clean URL and any mode flags.

### Step 2: Run Check A for all URLs

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
| Other platforms | no video ID — goes to `NEEDS_PROCESSING` for Check B |

Then parse every processed entry in `## Processed` in `watch-urls.md` **and** in `LLM_Skills/url-truth-analyzer/watch_urls_archive.md` (if it exists) and extract the video ID from each processed URL using the same rules. This ensures dedup works even after old entries have been archived by Phase -1.

**Skip processed entries marked `failed`** when building the dedup index. A failed entry means the user is allowed (and likely intends) to retry the same URL on a subsequent run; treating it as a duplicate silently drops the retry. Only `analyzed YYYY-MM-DD` and `duplicate of` entries count for dedup.

For each pending URL whose video ID matches any non-failed processed URL's video ID (from either file) → add to `DUPLICATES[]` with the matching processed entry (URL + analysis file path).

### Step 3: Partition entries

Classify each pending entry into one of five lists:

- **`DUPLICATES[]`** — Check A matched a processed entry. These are done — write their Step 7 entries immediately (duplicate format).
- **`PLAIN_TEXT[]`** — Entry has `[plain-text]` directive. Skips Phase 1 fetching entirely; sub-agent dispatched after Mode K copy.
- **`ARTICLES[]`** — Entry has `[article]` directive. Skips yt-dlp; Phase 1 runs Mode H (HTML fetch + body extraction), then sub-agent.
- **`LOCAL_FOLDERS[]`** — Entry starts with `/` and is not an `http` URL (and has no `[plain-text]` directive). These skip Phase 1 entirely.
- **`NEEDS_PROCESSING[]`** — Everything else (video/audio/image URLs). These enter Phase 1 for Check B + download + transcription.

**Routing priority** when multiple conditions could match: `[plain-text]` > `[article]` > absolute-path local folder > URL processing. A `.txt` file path without `[plain-text]` is treated as a (likely empty) folder and will fail validation — this is intentional, since the user opted not to auto-route.

### Step 4: Record duplicates for batch update

For each entry in `DUPLICATES[]`, add to the `RESULTS[]` collection with status `duplicate` and the matching processed entry details. These are written to `watch-urls.md` later in the parent's batch Step 7, not immediately.

Report:
```
📋 Phase 0 complete: N total entries triaged
   ⚠️  X duplicate(s) resolved instantly (Check A video ID match)
   📥 Y URL(s) queued for Phase 1 (download + transcribe + dispatch)
   📁 Z local folder(s) queued for sub-agent dispatch (OCR + analysis)
   📰 A article(s) queued for Phase 1 (HTML fetch + body extraction)
   📝 B plain-text file(s) queued for sub-agent dispatch (no fetch)
```

---

## Step 0b: Parse directives + Check B title dedup (Phase 1 — per URL)

**Progress indicator**: `⏳ Step 0b: Parsing directives, checking title dedup...`

### Sub-step 0a: Parse URL directives

Before anything else, check whether the pending line contains a `[...]` directive block.

1. Split the line on the first ` [` — everything before it is the **clean URL**; everything inside `[...]` is the **directive string**.
2. Parse the directive string (case-insensitive):
   - If it contains `transcript-only` → set mode flag `TRANSCRIPT_ONLY=true`
   - If it matches a timestamp pattern like `00:05:00-00:15:00` or `5:00-15:00` → extract `START` and `END` values and set `TIMESTAMP_RANGE=true`
   - If it contains `audio-only` → set mode flag `AUDIO_ONLY=true`
   - If it contains `display-only` → set mode flag `DISPLAY_ONLY=true`
   - Multiple directives can be present in the same block, e.g. `[transcript-only 00:05:00-00:15:00]`
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

## Step 1: Download content (Phase 1 — rate-limited, pipelined with Step 2)

All server calls in this step are subject to the inter-request delay and exponential backoff rules described at the end of this section.

### Phase 1 prerequisite — export Firefox cookies (one-time per batch)

If any Instagram URL is in the batch, export the user's Firefox Instagram cookies once before the per-URL loop. The cookies file is used by both `yt-dlp` (via `--cookies-from-browser firefox` natively) AND the authenticated Playwright scraper in Mode F (which loads the Netscape-format file directly).

```bash
mkdir -p /tmp/url-analyzer
yt-dlp --cookies-from-browser firefox --cookies /tmp/url-analyzer/ig-cookies.txt \
  --no-warnings --skip-download --ignore-no-formats-error \
  --print "ignored" 'https://www.instagram.com/' 2>/dev/null
# /tmp/url-analyzer/ig-cookies.txt now holds all instagram.com cookies in Netscape format
# (sessionid, csrftoken, ds_user_id, ig_did, etc.)
```

This call is a single light HTTP fetch and counts as one server visit (apply the normal delay after it).

### Content type detection and download strategy

1. **If `CONTENT_TYPE=plain-text`**: Skip Phase 1 fetching → Mode K (copy local `.txt` into `/tmp/url-analyzer/`). No server call.
2. **If `CONTENT_TYPE=article`** (`[article]` directive): Skip yt-dlp entirely → Mode H (HTML fetch + readable-body extraction).
3. **If YouTube URL and NOT `AUDIO_ONLY=true`**: Try captions first (Mode A). If captions found → set `TRANSCRIPT_SOURCE=captions`, done. If no captions → fall back to Mode B (audio download + Whisper).
4. **If `AUDIO_ONLY=true`**: Skip caption attempt → Mode B (audio download + Whisper) directly.
5. **If LinkedIn URL**: Mode D (three-stage pipeline)
6. **If Facebook/Instagram URL**: Mode E (yt-dlp audio + thumbnail; both saved). If yt-dlp reports "No video formats found" but extracts metadata → Mode F (image/carousel).
7. **If yt-dlp fails with other errors**: Apply retry logic.

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

### Mode F — Image/Carousel Posts (Instagram, Facebook, Twitter/X)

**Progress indicator**: `⏳ Step 1/7: Downloading carousel images via authenticated Playwright...`

Social media platforms support image-only posts (single images or carousels). yt-dlp identifies these posts (it can pull `uploader_id`, `playlist_count`, `title`) but **cannot extract the actual image URLs** — its JSON output has empty `thumbnails` and `formats` arrays for image-only carousels. Calling `--write-thumbnail` produces "There are no video thumbnails to download" because the IG extractor only writes thumbnails for video formats.

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

#### Step F-2: Export Firefox cookies to Netscape format (once per batch)

The Playwright scraper needs the same Instagram session that Firefox holds. Export cookies once at the start of Phase 1:

```bash
yt-dlp --cookies-from-browser firefox --cookies /tmp/url-analyzer/ig-cookies.txt \
  --no-warnings --skip-download --ignore-no-formats-error \
  --print "ignored" 'https://www.instagram.com/' 2>/dev/null
# This populates /tmp/url-analyzer/ig-cookies.txt with all instagram.com cookies in Netscape format.
```

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
- The previous browser-mode scraper was wrong because it ran logged out and pulled explore-panel decoys. Loading the user's real Firefox cookies fixes that.

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

**Exception**: Local folder entries (Mode I) and plain-text file entries (Mode K) do not count toward the inter-request delay or batch cooldown counters, since no server calls are made. Article fetches (Mode H) DO make network requests and should count toward rate limits.

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
- Content type: <video|audio|image|article|plain-text|silent-video>
- Transcript source: <captions|whisper|ocr|html|plain-text>
- Transcript file: /tmp/url-analyzer/<slug>.txt
- Thumbnail file: /tmp/url-analyzer/<slug>.jpg  ← present for Instagram/Facebook reels (Mode E) and silent-video
- Transcript degenerate: <true|false>  ← true when Whisper produced <30 words / music-only / hallucinated lyrics
- Directives: <parsed directives or "none">
- Display only: <true|false>
- Date: <YYYY-MM-DD>

## For Instagram/Facebook reels (Mode E) — dual-input pattern
EVERY Instagram/Facebook reel has BOTH a transcript and a thumbnail. You MUST inspect both:
1. Read /tmp/url-analyzer/<slug>.txt.
2. Run Tesseract on /tmp/url-analyzer/<slug>.jpg: `tesseract /tmp/url-analyzer/<slug>.jpg stdout --dpi 300`.
3. Use the Read tool to view the thumbnail visually (text overlay, brand, charts, gestures).
4. If `Transcript degenerate=true` (or transcript reads as song lyrics / music description / single word), treat the THUMBNAIL TEXT OVERLAY as authoritative for claim extraction. Reels lead with the hook on-screen.
5. If both transcript and thumbnail are uninformative, return Grade C / "no claims extractable" rather than fabricating.

## For silent-video content (TRANSCRIPT_SOURCE=ocr, no transcript file)
There is only a thumbnail. Run Tesseract + Read tool on /tmp/url-analyzer/<slug>.jpg. Write combined OCR + visual analysis to /tmp/url-analyzer/<slug>.txt before proceeding to Step 3.

## For image-carousel content (TRANSCRIPT_SOURCE=ocr, multiple .jpg files)
Run Step 2 Path C first: use Tesseract OCR on images at /tmp/url-analyzer/<slug>*.jpg
and Read tool for visual analysis, then save combined output to /tmp/url-analyzer/<slug>.txt.

## For article content (TRANSCRIPT_SOURCE=html) or plain-text content (TRANSCRIPT_SOURCE=plain-text)
Step 2 is a no-op — the transcript file at /tmp/url-analyzer/<slug>.txt was already produced
by Mode H or Mode K in Phase 1. Read it directly and proceed to Step 3.

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
If DISPLAY_ONLY=true: return the full analysis text in your final response.
<include Step 5 template verbatim>

## Step 6: Cleanup
Delete temp files for this URL only: /tmp/url-analyzer/<slug>*
Never delete the analysis file or original source folders.

## Required response format
End your response with exactly this block so the parent can parse your result:

---RESULT---
status: success|failed
slug: <slug>
analysis_path: <path to saved .md file, or "none" if display-only>
content_type: Medical|General Science
title: <video/post title>
url: <clean_url>
display_analysis: <full analysis markdown if display-only, otherwise "none">
error: <error message if failed, otherwise "none">
---END RESULT---
```

The parent reads `ebm-reference.md` once and injects its contents into every sub-agent prompt that might need it (all of them, since classification happens inside the sub-agent).

### Result collection

After all Phase 1 downloads are complete and all sub-agents have been dispatched:

1. Poll each sub-agent using `AwaitShell` or by reading its output file, waiting for all to complete.
2. Parse the `---RESULT---` block from each sub-agent's final response.
3. Collect all results into `RESULTS[]`:
   - Successful analyses (with file paths)
   - Failed analyses (with error reasons)
   - Display-only analyses (with returned markdown text)
   - Duplicates (recorded earlier in Phase 0 / Step 0b)
4. For display-only results: output the `display_analysis` text to the user in the conversation.

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

**Inline URL auto-detection** (URL provided directly in the user's message):
- `DISPLAY_ONLY=true` is set automatically. Only one URL to process.
- Sub-agent dispatch still applies: a single sub-agent is spawned for the analysis.
- The parent displays the result in the conversation. No `watch-urls.md` update or git sync.

---

## Step 2: Extract text content (pipelined into Phase 1)

> **Pipelining note**: For URL entries, Step 2 now runs **during Phase 1** — either inline (captions → instant VTT-to-text) or as a background process (Whisper running during the inter-request delay). By the time the sub-agent starts, the transcript is already available.
>
> For **local folder entries** (Path C — OCR + visual analysis), Step 2 runs inside the sub-agent, since it requires LLM vision capabilities that cannot be backgrounded.

No network calls. No delays. Runs entirely on local files.

The extraction method depends on the content type:
- **Video/audio content** (`TRANSCRIPT_SOURCE=captions` or `whisper`) → Path A or B below (pipelined into Phase 1 delays)
- **Image content** (`TRANSCRIPT_SOURCE=ocr`) → Path C below (runs in Phase 2)
- **Article content** (`TRANSCRIPT_SOURCE=html`) → No-op. The transcript was already produced by Mode H in Phase 1.
- **Plain-text content** (`TRANSCRIPT_SOURCE=plain-text`) → No-op. The transcript was already produced by Mode K in Phase 1.

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

After Whisper finishes, run this check:

```bash
WORDS=$(wc -w < /tmp/url-analyzer/<slug>.txt)
if [ "$WORDS" -lt 30 ]; then
  TRANSCRIPT_QUALITY=low
fi
```

When `TRANSCRIPT_QUALITY=low`, mark the URL with `TRANSCRIPT_DEGENERATE=true` so the sub-agent prompt explicitly tells the sub-agent:
1. Treat the transcript as zero-information / noise.
2. Extract claims primarily from the thumbnail's text overlay via OCR + visual analysis (the thumbnail was already downloaded in Mode E).
3. If neither transcript nor thumbnail provides extractable content, return Grade C / "no claims extractable" rather than fabricating.

**Do not gate on language**: Russian "ДИНАМИЧНАЯ МУЗЫКА" is a music description, not a Russian post. The word-count check catches this without requiring per-language logic.

**After transcription completes**: Report `✓ Step 2/7: Transcription complete via Whisper (N words; degenerate=<true|false>)`

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

2. Research the handle (1 web search, max 2 if the first is ambiguous):
   - Search for the handle/channel name plus terms like `fact check`, `controversy`, `misinformation`, `credentials`, `retraction`, `debunked`, or `reputation`.
   - Prefer signals from fact-checker coverage (Health Feedback, Snopes, FactCheck.org, Full Fact, AltNews, BOOM Live), mainstream journalism, academic or professional credentials on verified profiles, platform verification badges, and prior analyses of the same handle in `~/Documents/truth-analyses/`.
   - If the handle is obscure and produces no credible signal, say so explicitly — do not fabricate a reputation.

3. Write 2–4 sentences covering, where substantiated:
   - Typical content style (explainer, opinion/commentary, news aggregation, motivational, product promotion, satire, call-out, etc.).
   - Track record on truthfulness (prior fact-checks, retractions, misinformation flags — or, conversely, a clean peer-reviewed / institutional record).
   - Verified credentials or platform status (blue check, institutional affiliation, medical license, PhD) — only if substantiated.
   - Known conflicts of interest (product lines, sponsorships, political alignment) that materially affect how the content should be read.

4. Calibration rules:
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
**Source URL**: <URL>                                  ← for URL entries (video/audio/image/article)
**Source**: Local folder: /path/to/folder (N images)   ← for local folder entries
**Source**: Plain-text file: /path/to/file.txt         ← for plain-text entries
**Analyzed**: YYYY-MM-DD
**Content type**: Medical | General Science
**Format**: Video | Audio | Image Post | Carousel (N images) | Article | Plain Text

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
- `/tmp/url-analyzer/<slug>.*` — all temp files for this URL (`.mp3`, `.mp4`, `.wav`, `.vtt`, `.srt`, `.jpg`, `.png`, `.txt`, `_transcription.txt`)
- `/tmp/url-analyzer/<slug>-*.jpg` — carousel/folder images for this slug
- `/tmp/url-analyzer/<slug>-paths.txt` — subfolder mapping file if present
- Any folders created by `extract_audio` (typically long hash-named directories)

**Local folder entries**: Delete only copies in `/tmp/url-analyzer/` and intermediary files. **Never delete the original source folder or its contents.** The original folder path is user-managed data.

**Plain-text entries**: Delete only the copy at `/tmp/url-analyzer/<slug>.txt`. **Never delete the user's original `.txt` source file.**

**Article entries**: Delete the extracted body at `/tmp/url-analyzer/<slug>.txt`. There is no other state to remove.

**How to clean up:**
```bash
rm -f /tmp/url-analyzer/<slug>.*
rm -f /tmp/url-analyzer/<slug>-*.jpg
rm -f /tmp/url-analyzer/<slug>-paths.txt
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
