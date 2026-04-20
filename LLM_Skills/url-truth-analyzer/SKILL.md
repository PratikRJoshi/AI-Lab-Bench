---
name: url-truth-analyzer
description: Analyzes video/audio/image content from URLs and performs truth-claim validation. Supports YouTube, Facebook/Instagram (reels and image posts), Twitter/X, and LinkedIn videos. For video/audio: transcribes with Whisper or captions. For images: downloads and extracts text via OCR, analyzes visual content. For medical content, applies EBM SORT analysis with peer-reviewed citations. For general science, validates claims and finds credible supporting or refuting content. Supports transcript-only mode (YouTube captions) and timestamp-range extraction. Use when the user mentions analyzing URLs, truth claims, transcribing videos, checking medical claims, analyzing social media images, or asks to process the watch-urls.md file.
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

# Browser automation mode for Instagram (when yt-dlp fails)
https://www.instagram.com/p/DWKE4kJDbfz/ [browser-mode]

# Display-only — output analysis in the conversation, skip all file saves and GitHub sync
https://youtu.be/VIDEO_ID [display-only]

# Display-only can combine with other directives
https://youtu.be/VIDEO_ID [display-only transcript-only]
```

**Directive rules:**
- Directives are placed on the same line as the URL, separated by a space.
- The `[...]` block is stripped before any URL is passed to `yt-dlp` or used for video ID extraction.
- Timestamps use `HH:MM:SS` or `MM:SS` format, separated by a hyphen. Both the start and end must be specified.
- Directives are case-insensitive: `[Transcript-Only]` and `[transcript-only]` are equivalent.
- If no directive is present, YouTube URLs default to **captions-first**: attempt to fetch captions, then fall back to audio download + Whisper if no captions are available. Non-YouTube platforms always use audio download (no captions available).
- **`[audio-only]`**: Forces audio download + Whisper transcription, skipping the caption attempt entirely. Use when auto-generated captions are known to be poor quality or in the wrong language.
- **Local folder paths**: If the entry starts with `/` (absolute path) instead of `http`, it is treated as a local folder containing images. All supported image files (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`) are treated as a single post. The `[transcript-only]` and timestamp directives are ignored for folder entries. Only flat directory scanning (no recursion into subdirectories).
- **Browser automation**: The `[browser-mode]` directive forces the use of Playwright browser automation instead of `yt-dlp`. Use this for Instagram URLs that fail with the standard download methods. Requires playwright Python package and chromium browser installed.
- **`[display-only]`**: Outputs the final analysis directly in the conversation instead of saving to any file. Skips Step 5 (file save), Step 6 (cleanup is still run), Step 7 (`watch-urls.md` update), and post-processing (GitHub sync). Useful for quick one-off checks or when the user provides a URL inline rather than via `watch-urls.md`. Can combine with other directives (e.g. `[display-only transcript-only]`). When a URL is provided directly in the user's message (not from `watch-urls.md`), `display-only` is implied automatically.

---

## Workflow overview

**Inline URL auto-detection**: When the user provides a URL directly in their message (not from `watch-urls.md`), treat it as `DISPLAY_ONLY=true` automatically. Skip Phase 0 dedup checks (no `watch-urls.md` to read), run Phase 1 + Phase 2 normally, display the analysis in the conversation, clean up temp files, and stop. No files are written, no `watch-urls.md` is updated, no GitHub sync runs.

Processing happens in **three phases** plus post-processing. Phase 0 is instant and local. Phase 1 pipelines server calls with local transcription. Phase 2 runs analysis sequentially.

### Phase 0 — Batch triage (instant, local)

Before any server calls, run a single pass over ALL pending URLs:

1. Parse directives for every entry
2. Run Check A (video ID match) for every entry against the `## Processed` list
3. Partition into three lists:
   - `DUPLICATES[]` — Check A matched; write Step 7 entries immediately, no further processing
   - `NEEDS_PROCESSING[]` — URL entries requiring download + analysis
   - `LOCAL_FOLDERS[]` — local folder entries (skip Phase 1, go directly to Phase 2)

Phase 0 makes zero server calls. Duplicates are resolved instantly.

### Phase 1 — Download + transcribe (rate-limited, pipelined)

For each URL in `NEEDS_PROCESSING`, **one at a time, in order**:

1. Step 0b: Check B title/slug match (server call — `yt-dlp --get-title`)
2. Step 1: Download content — captions-first for YouTube (lightweight), fall back to audio if no captions found. Other platforms use audio download directly.
3. Step 2 (pipelined): Immediately after download, start transcription:
   - If captions were fetched → convert VTT to plain text inline (instant, ~1s)
   - If audio was downloaded → spawn Whisper as a **background process** so it runs during the mandatory inter-request delay
4. Inter-request delay (45–75s randomized) — Whisper runs concurrently during this wait

Phase 1 produces a transcript `.txt` file per URL. Whisper jobs that outlast the delay are awaited before analysis begins.

**Local folder entries** skip Phase 1 entirely (no server calls). They proceed directly to Phase 2 starting at Step 2 (Path C). Step 0b runs a local-only dedup variant (slug match against `~/Documents/truth-analyses/` filenames).

### Phase 2 — Analyze + save (local, sequential)

For each transcript produced in Phase 1 (plus local folder entries), **one at a time, in order** — no delays needed:

1. Step 3: Classify content (Medical vs General Science)
2. Step 4: Analyze (EBM SORT or Claim Validation)
3. Step 5: Save analysis file — or display in conversation if `DISPLAY_ONLY=true`
4. Step 6: Cleanup temporary files
5. Step 7: Update `watch-urls.md` — skipped if `DISPLAY_ONLY=true`

### Post-processing — after all URLs complete

1. Sync to GitHub: commit and push new analysis files from `~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/` to the remote repository

---

**Progress reporting**: Output status messages at each phase transition:
```
📋 Phase 0: Triaging N URLs... (X duplicates, Y to download, Z local folders)
🔄 Phase 1 [1/Y]: Downloading + transcribing <URL> (captions-first)
   ⏳ Whisper running in background during inter-request delay...
🔄 Phase 1 [2/Y]: Downloading + transcribing <URL>
✓ Phase 1 complete: Y downloaded, X transcripts ready
🔬 Phase 2 [1/M]: Analyzing <URL>
🔬 Phase 2 [2/M]: Analyzing <URL>
✅ All URLs processed. Syncing to GitHub...
```

Update progress after each major step within each phase.

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

Then parse every processed entry in `## Processed` in `watch-urls.md` and extract the video ID from each processed URL using the same rules.

For each pending URL whose video ID matches any processed URL's video ID → add to `DUPLICATES[]` with the matching processed entry (URL + analysis file path).

### Step 3: Partition entries

Classify each pending entry into one of three lists:

- **`DUPLICATES[]`** — Check A matched a processed entry. These are done — write their Step 7 entries immediately (duplicate format).
- **`LOCAL_FOLDERS[]`** — Entry starts with `/` and is not an `http` URL. These skip Phase 1 entirely.
- **`NEEDS_PROCESSING[]`** — Everything else. These enter Phase 1 for Check B + download + transcription.

### Step 4: Resolve duplicates immediately

For each entry in `DUPLICATES[]`, update `watch-urls.md` now (Step 7 duplicate format):
```
- <URL> (duplicate of <original-URL> → see truth-analyses/<existing-file>.md)
```

Report:
```
📋 Phase 0 complete: N total URLs triaged
   ⚠️  X duplicate(s) resolved instantly (Check A video ID match)
   📥 Y URL(s) queued for Phase 1 (download + transcribe)
   📁 Z local folder(s) queued for Phase 2 (OCR + analysis)
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
   - If it contains `browser-mode` → set mode flag `BROWSER_MODE=true`
   - If it contains `audio-only` → set mode flag `AUDIO_ONLY=true`
   - If it contains `display-only` → set mode flag `DISPLAY_ONLY=true`
   - Multiple directives can be present in the same block, e.g. `[transcript-only 00:05:00-00:15:00]`
3. Use the **clean URL** (without the directive block) for all subsequent processing.

Report the parsed mode at the start of the URL:
```
🔄 Processing URL N of N: <clean URL>
   Mode: [transcript-only] [00:05:00–00:15:00]   ← only shown when directives are present
```

### Sub-step 0a-local: Detect local folder entry

After parsing directives, check if the clean entry (after stripping any `[...]` directive) starts with `/` and does NOT start with `http`. If so, this is a local folder entry:

1. Set `CONTENT_TYPE=local-folder` and `TRANSCRIPT_SOURCE=ocr`.
2. Validate the path:
   - If the path does not exist OR is not a directory → mark as failed: `(failed YYYY-MM-DD — path does not exist or is not a directory)` and skip to Step 7.
3. **Check folder depth** (NEW):
   - Recursively scan the folder tree to find the maximum nesting depth
   - Use this bash command to check depth:
     ```bash
     MAX_DEPTH=$(find /path/to/folder -type d -printf '%d\n' 2>/dev/null | sort -rn | head -1)
     BASE_DEPTH=$(echo "/path/to/folder" | tr -cd '/' | wc -c)
     RELATIVE_DEPTH=$((MAX_DEPTH - BASE_DEPTH))
     ```
   - If `RELATIVE_DEPTH > 5` → mark as failed: `(failed YYYY-MM-DD — folder structure exceeds maximum depth of 5 levels. Found: N levels)` and skip to Step 7.
   - Report depth in progress indicator: `⏳ Step 0b: Local folder detected (depth: N levels), checking for duplicates...`
4. **Scan for supported image files recursively**:
   - Look for files with extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` (case-insensitive)
   - Scan recursively up to depth 5 using:
     ```bash
     find /path/to/folder -maxdepth 5 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.webp" \)
     ```
   - If no supported image files found → mark as failed: `(failed YYYY-MM-DD — no supported image files found in folder tree)` and skip to Step 7.
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

If a matching file exists → **duplicate detected**. Note the matched filename and skip to Step 7.

### If duplicate detected

Report:
```
⚠️  Duplicate content detected for URL N of N: <PENDING_URL>
    Already analyzed as: truth-analyses/<existing-file>.md
    Skipping transcription — will link to existing analysis.
```

Then go directly to **Step 7** (skip Steps 1–6). In Step 7, use the special duplicate entry format (see Step 7).

### If no duplicate found

Report `✓ Step 0b: No duplicate found — proceeding with download.` and continue to Step 1.

---

## Step 1: Download content (Phase 1 — rate-limited, pipelined with Step 2)

All server calls in this step are subject to the inter-request delay and exponential backoff rules described at the end of this section.

**Content type detection and download strategy**:

1. **If `BROWSER_MODE=true`**: Skip yt-dlp entirely → Mode G (browser automation)
2. **If YouTube URL and NOT `AUDIO_ONLY=true`**: Try captions first (Mode A). If captions found → set `TRANSCRIPT_SOURCE=captions`, done. If no captions → fall back to Mode B (audio download + Whisper).
3. **If `AUDIO_ONLY=true`**: Skip caption attempt → Mode B (audio download + Whisper) directly.
4. **If LinkedIn URL**: Mode D (three-stage pipeline)
5. **If Facebook/Instagram URL**: Try Mode E (standard yt-dlp audio download). If yt-dlp reports "No video formats found" but extracts metadata → Mode F (image/carousel).
6. **If yt-dlp fails with other errors**: Apply retry logic.

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

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to Phase 2.

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

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to Phase 2.

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

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to Phase 2.

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

Then mark as failed: `(failed YYYY-MM-DD — all automated LinkedIn stages failed; replace with DASH manifest URL from Network tab)`

---

**Note**: `[transcript-only]` is not supported for LinkedIn — there are no caption tracks in LinkedIn DASH manifests. The directive is silently ignored; audio + Whisper is always used.

---

### Mode E — Facebook/Instagram URLs (standard yt-dlp download)

**Progress indicator**: `⏳ Step 1/7: Downloading audio from Facebook...`

Facebook reels, videos, and Instagram content are supported via yt-dlp's built-in extractors. Use the standard Mode B audio download command with cookies for authentication:

```bash
yt-dlp --cookies-from-browser firefox \
  -x --audio-format mp3 \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

**Supported URL patterns:**
- `facebook.com/reel/ID` (Facebook Reels)
- `facebook.com/watch/?v=ID` (Facebook Watch videos)
- `facebook.com/<username>/videos/ID` (Profile videos)
- `fb.watch/ID` (Facebook short links)
- `instagram.com/reel/ID` (Instagram Reels)

**If it succeeds**: set `TRANSCRIPT_SOURCE=whisper`, proceed to Phase 2.

**If it fails**: Apply the retry logic from the next section. Facebook videos may require being logged into Firefox for private or region-restricted content.

**Note**: `[transcript-only]` is not supported for Facebook/Instagram — there are no caption tracks available. The directive is silently ignored; audio + Whisper is always used.

---

### Mode F — Image/Carousel Posts (Instagram, Facebook, Twitter/X)

**Progress indicator**: `⏳ Step 1/7: Downloading images...`

Social media platforms support image-only posts (single images or carousels). When yt-dlp reports "No video formats found" but successfully extracts post metadata, the content is an image post.

**Detection**: yt-dlp output contains:
- `ERROR: [Instagram] <ID>: No video formats found!` or
- `ERROR: [Facebook] <ID>: No video formats found!` or
- `ERROR: [Twitter] <ID>: No video formats found!`
- BUT the extractor successfully retrieved title/description/metadata (playlist info shows items)

**Download images**:

```bash
yt-dlp --cookies-from-browser firefox \
  --skip-download \
  --write-thumbnail \
  --convert-thumbnails jpg \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

For carousel posts (multiple images), yt-dlp downloads each image as `<slug>.1.jpg`, `<slug>.2.jpg`, etc.

If thumbnail extraction fails, try direct image download:

```bash
yt-dlp --cookies-from-browser firefox \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>' 2>&1
```

Then extract image URLs from the JSON metadata:

```bash
yt-dlp --cookies-from-browser firefox -J '<URL>' | \
  python3 -c "import sys, json; d=json.load(sys.stdin); \
  print('\n'.join([img.get('url') for ent in (d.get('entries') or [d]) for img in (ent.get('thumbnails') or []) if img.get('url')]))"
```

Download each image URL with curl:

```bash
curl -L -H "User-Agent: Mozilla/5.0" -o "/tmp/url-analyzer/<slug>-<N>.jpg" "<IMAGE_URL>"
```

**If image download succeeds**: set `CONTENT_TYPE=image` and `TRANSCRIPT_SOURCE=ocr`, proceed to Phase 2.

**If it fails**: Mark as failed with reason "Could not download images from post".

**Supported URL patterns:**
- `instagram.com/p/ID` (Instagram posts — may be carousel)
- `instagram.com/reel/ID` (Instagram Reels — may have no video if post type changed)
- `facebook.com/<user>/posts/ID` (Facebook posts)
- `facebook.com/photo/?fbid=ID` (Facebook photos)
- `twitter.com/<user>/status/ID` or `x.com/<user>/status/ID` (Twitter/X posts with images)

---

### Mode G — Browser automation for Instagram (when [browser-mode] directive is used)

**Progress indicator**: `⏳ Step 1/7: Downloading images via browser automation...`

When the `[browser-mode]` directive is specified for an Instagram URL, use Playwright browser automation to extract image URLs. This bypasses Instagram's anti-scraping measures that block `yt-dlp`.

**When to use**: Instagram URLs that fail with Mode F due to platform blocks. Add `[browser-mode]` directive to the URL in `watch-urls.md`.

**Requirements**:
- Python3 with playwright package installed (`pip3 install --user --break-system-packages playwright`)
- Chromium browser installed (`playwright install chromium`)

**Process**:
1. Run the Instagram scraper script:

```bash
python3 ~/.cursor/skills/url-truth-analyzer/instagram_scraper.py '<URL>' 2>/dev/null
```

2. Parse the JSON output to extract image URLs
3. Download each image using curl:

```bash
# For each image URL from the scraper output
N=1
for img_url in "${IMAGE_URLS[@]}"; do
  curl -L -H "User-Agent: Mozilla/5.0" -o "/tmp/url-analyzer/<slug>-${N}.jpg" "$img_url"
  N=$((N + 1))
done
```

**If browser mode succeeds**: set `CONTENT_TYPE=image` and `TRANSCRIPT_SOURCE=ocr`, proceed to Phase 2.

**If it fails**: Report error and mark as failed with the scraper's error message.

**Note**: Browser automation is slower (10-15 seconds vs 2-5 seconds) but more reliable for Instagram. The scraper extracts the top 10 largest images from the page, filtering out profile pics and thumbnails.

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

Set `CONTENT_TYPE=image` and `TRANSCRIPT_SOURCE=ocr`, proceed to Phase 2.

Report: `✓ Step 1/7: N local images staged for analysis (from M subfolders, no download needed).`

---

### Retry with exponential backoff

If `yt-dlp` fails and the output contains any of: `Sign in to confirm`, `HTTP Error 429`, `Too Many Requests`, or `rate limit` — this is a server-side rate limit. Apply exponential backoff:

| Attempt | Wait before retry |
|---|---|
| 1st retry | 90 seconds |
| 2nd retry | 180 seconds |
| 3rd retry | 360 seconds |
| After 3rd failure | Mark as failed, continue to next URL |

For any other error (private video, bad URL, **LinkedIn extraction failure**, etc.) — do not retry. Mark as failed immediately and continue.

Report retry attempts as they happen:
```
⚠️  Rate limited on URL N — waiting 90s before retry 1/3...
```

If all 3 retries fail, report:
```
❌ Failed: <URL> — rate limited after 3 retries. Marked in watch-urls.md for manual retry.
```

---

### Inter-request delay (with pipelined transcription)

After each URL's download completes (success or skip), **start transcription immediately before entering the delay**:

1. **If `TRANSCRIPT_SOURCE=captions`**: Run VTT-to-text conversion inline (instant, ~1s — see Step 2 Path A). Then enter delay.
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

If Whisper finishes before the delay ends, the delay still runs to completion (rate-limit protection). If Whisper takes longer than the delay (rare for short videos), the next URL waits for Whisper to finish first.

**Delay rules**:
- Apply between every consecutive URL, including after Check B title lookups (see Step 0b).
- Do **not** apply before the very first URL.
- The randomized jitter prevents a detectable fixed-interval fingerprint.
- **Reduced delay for caption-only fetches**: When Mode A succeeds (captions found, no audio download needed), the delay can be reduced to **15–30 seconds** since caption fetches are lightweight metadata requests:

```bash
sleep $((15 + RANDOM % 16))   # randomized: 15–30 seconds for caption-only
```

**Exception**: Local folder entries (Mode I) do not count toward the inter-request delay or batch cooldown counters, since no server calls are made. Browser automation mode (Mode G) does make network requests and should count toward rate limits.

### Batch cooldown

After every **5th** successful or attempted download, insert an additional pause before continuing:

```bash
sleep 300   # 5-minute cooldown after each group of 5
```

This gives the server-side rate-limit window time to reset before the next batch. The count resets after each cooldown.

**After all Phase 1 downloads complete**: Report `✓ Phase 1 complete: X downloaded + transcribed, Z failed. Awaiting any background Whisper jobs...`

After reporting, wait for all outstanding background Whisper processes:

```bash
for pid in "${WHISPER_PIDS[@]}"; do
  wait $pid
done
```

Then report: `✓ All transcripts ready. Entering Phase 2 (analysis)...`

---

## Step 2: Extract text content (pipelined into Phase 1)

> **Pipelining note**: For URL entries, Step 2 now runs **during Phase 1** — either inline (captions → instant VTT-to-text) or as a background process (Whisper running during the inter-request delay). By the time Phase 2 starts, transcripts are already available.
>
> For **local folder entries** (Path C — OCR + visual analysis), Step 2 runs at the start of Phase 2 as before, since it requires LLM vision capabilities that cannot be backgrounded.

No network calls. No delays. Runs entirely on local files.

The extraction method depends on the content type:
- **Video/audio content** (`TRANSCRIPT_SOURCE=captions` or `whisper`) → Path A or B below (pipelined into Phase 1 delays)
- **Image content** (`TRANSCRIPT_SOURCE=ocr`) → Path C below (runs in Phase 2)

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

**After transcription completes**: Report `✓ Step 2/7: Transcription complete via Whisper (N words)`

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

## Step 3: Classify the content (Phase 2 — first step of analysis)

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

## Step 4a: Medical content — EBM SORT Analysis (Phase 2 — local)

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

## Step 4b: General science — Claim validation (Phase 2 — local)

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

## Step 4c: Channel / handle reputation (Phase 2 — runs for all URL content)

**Progress indicator**: `⏳ Step 4c/7: Assessing channel / handle reputation...`

Independent of the per-claim analysis in Step 4a/4b, briefly characterize the source channel, handle, or author that posted this content. This helps the reader weight the analysis against the creator's track record.

1. Identify the source:
   - For URL entries: extract the uploader/channel/handle from the platform. Use `yt-dlp --print "%(uploader)s|%(uploader_id)s|%(channel)s|%(channel_url)s" '<URL>'` or inspect the `uploader`, `uploader_id`, and `channel` fields in `yt-dlp -J '<URL>'`. For Instagram/Facebook reels, `uploader_id` gives the handle. For LinkedIn, use the author name from the post URL slug.
   - For local folder entries: there is no channel. Record `Source channel: N/A (local folder)` and skip the reputation paragraph.

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

## Step 5: Output format (Phase 2 — local)

### If `DISPLAY_ONLY=true` — display in conversation

**Progress indicator**: `⏳ Step 5/7: Displaying analysis...`

Instead of saving to a file, output the full analysis markdown directly in the conversation as a message to the user. Use the same template below, but render it inline. Then skip the "Sync to AI-Lab-Bench repository" sub-step entirely.

After displaying, report `✓ Step 5/7: Analysis displayed in conversation (display-only mode — no files written).` and proceed to Step 6.

### If `DISPLAY_ONLY=false` (default) — save to file

**Progress indicator**: `⏳ Step 5/7: Saving analysis...`

Save to `~/Documents/truth-analyses/YYYY-MM-DD-<slugified-title>.md`:

```markdown
# Truth Analysis: <Post Title or Video Title>
**Source URL**: <URL>                          ← for URL entries
**Source**: Local folder: /path/to/folder (N images)   ← for local folder entries
**Analyzed**: YYYY-MM-DD
**Content type**: Medical | General Science
**Format**: Video | Audio | Image Post | Carousel (N images)

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

## Step 6: Cleanup downloaded files (Phase 2 — local)

**Progress indicator**: `⏳ Step 6/7: Cleaning up temporary files...`

The `extract_audio` command downloads video/audio files and creates working directories in the current working directory. After the analysis is complete, delete all downloaded files and folders to save disk space.

**What to keep:**
- The original URL (already in watch-urls.md)
- The truth analysis markdown file in `~/Documents/truth-analyses/`

**What to delete:**
- Any folders created by `extract_audio` (typically long hash-named directories)
- Any `.mp4`, `.mp3`, `.wav`, `.vtt`, `.srt`, `.jpg`, `.png`, or `_transcription.txt` files in `/tmp/url-analyzer/`
- Any temporary files created during processing

**Local folder entries**: Delete only copies in `/tmp/url-analyzer/` and intermediary files. **Never delete the original source folder or its contents.** The original folder path is user-managed data.

**How to clean up:**
```bash
# Find and delete folders created by extract_audio (they have long hash-like names)
# Look in the current working directory for recently created folders
rm -rf <hash-folder-name>
```

**After cleanup**: Report `✓ Step 6/7: Cleanup complete. Kept: analysis file. Removed: N MB of temporary files.`

---

## Step 7: Update watch-urls.md

### If `DISPLAY_ONLY=true` — skip this step

Do not update `watch-urls.md`. The URL was a one-off analysis displayed in the conversation. Report `✓ Step 7/7: Skipped watch-urls.md update (display-only mode).` and proceed to the next URL or post-processing.

### If `DISPLAY_ONLY=false` (default)

After processing each URL (including cleanup), remove it from `## Pending` and add it to the `## Processed` section with the analysis date.

**Rules for updating the Processed section:**
- If `## Processed` already exists in the file, append the new entry directly below the `## Processed` heading (before any existing processed entries), preserving everything else in the file unchanged.
- If `## Processed` does not exist, create it as a new section at the end of the file.
- Never create a duplicate `## Processed` heading.

The entry format depends on the outcome:

**Normal entry** (full analysis was run):
```
- <URL> (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

If a directive was used, append it in parentheses for traceability:
```
- <URL> [transcript-only] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <URL> [00:05:00-00:15:00] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- <URL> [transcript-only 00:05:00-00:15:00] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Local folder entry** (full analysis was run):
```
- /path/to/folder (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
- /path/to/folder [title: My Title] (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Duplicate entry** (content already analyzed under a different URL):
```
- <URL> (duplicate of <original-URL> → see truth-analyses/<existing-file>.md)
```

**Failed entry** (download failed after all retries due to rate limiting or other error):
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

Failed entries remain actionable: re-add the URL to `## Pending` on a future run to retry it, or for LinkedIn post URLs, replace the entry with the DASH manifest URL (from the Network tab) and re-run.

**Final status**: Report `✅ Completed: <URL>`

---

## Post-processing: Sync analyses to GitHub

**Progress indicator**: `⏳ Post-processing: Syncing new analyses to GitHub...`

This step runs **once** after ALL URLs have been processed (after the last Step 7 completes). It pushes any new analysis files to the AI-Lab-Bench repository.

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
