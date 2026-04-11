---
name: url-truth-analyzer
description: Analyzes URLs for truth claims via transcription, OCR, and EBM SORT grading. Use when the user provides a URL for fact-checking, truth analysis, or asks to process watch_urls.md.
---

# URL Truth Analyzer

---

## Watch file location

Use `LLM_Skills/watch_urls.md` in this repository as the canonical watch file.

## URL directive syntax

Each entry in `## Pending` is a URL, optionally followed by inline directives inside `[...]`. Directives modify *how* the URL is processed; they do not affect the URL itself.

```
# Default — full audio download + Whisper transcription
https://youtu.be/VIDEO_ID

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
```

**Directive rules:**
- Directives are placed on the same line as the URL, separated by a space.
- The `[...]` block is stripped before any URL is passed to `yt-dlp` or used for video ID extraction.
- Timestamps use `HH:MM:SS` or `MM:SS` format, separated by a hyphen. Both the start and end must be specified.
- Directives are case-insensitive: `[Transcript-Only]` and `[transcript-only]` are equivalent.
- If no directive is present, the existing default behaviour (full audio download + Whisper) applies.
- **Local folder paths**: If the entry starts with `/` (absolute path) instead of `http`, it is treated as a local folder containing images. All supported image files (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`) are treated as a single post. The `[transcript-only]` and timestamp directives are ignored for folder entries. Only flat directory scanning (no recursion into subdirectories).
- **Browser automation**: The `[browser-mode]` directive forces the use of Playwright browser automation instead of `yt-dlp`. Use this for Instagram URLs that fail with the standard download methods. Requires playwright Python package and chromium browser installed.

---

## Workflow overview

Processing happens in **two strictly sequential phases**. Never interleave them.

### Phase 1 — Server-touching (rate-limited)

For each pending URL, **one at a time, in order**:

1. Step 0: Parse URL directives, then run duplicate content check (Check A is local; Check B calls `yt-dlp --get-title` — see rate-limit rules below)
2. Step 1: Download based on mode — captions (transcript-only) or audio (default), with optional timestamp trimming. Rate-limit rules apply to all server calls.
3. After each URL's download completes: apply the inter-request delay before starting the next URL (see Step 1)

Phase 1 produces either a caption file (`.vtt`) or an audio file (`.mp3`) per URL, plus a record of which URLs were duplicates, skipped, or failed.

**Local folder entries** skip Phase 1 entirely (no server calls). They proceed directly to Phase 2 starting at Step 2 (Path C). Step 0 runs a local-only dedup variant (Check A skipped, Check B uses folder basename slug against local files only).

### Phase 2 — Local only (unthrottled)

For each file produced in Phase 1, **one at a time, in order** — no delays needed, nothing hits the network:

1. Step 2: Get transcript — either convert `.vtt` captions to plain text (fast, local), or run Whisper on the `.mp3` (CPU-intensive, local)
2. Step 3: Classify + analyze
3. Step 4: Save analysis file
4. Step 5: Cleanup audio/caption file
5. Step 6: Update `watch_urls.md`

### Post-processing — after all URLs complete

1. Sync to GitHub: commit and push new analysis files from `~/AI-Lab-Bench/LLM_Skills/url-truth-analyzer/truth-analyses/` to the remote repository

---

**Progress reporting**: At the start of processing each URL, output a status message to the user:
```
🔄 Processing URL 1 of N: <URL>
  ⏳ Step 0/7: Checking for duplicate content...
```

Update progress after each major step (duplicate check, transcribe, classify, analyze, save, cleanup).

---

## Step 0: Parse directives + duplicate content check

**Progress indicator**: `⏳ Step 0/7: Parsing directives, checking for duplicate content...`

### Sub-step 0a: Parse URL directives

Before anything else, check whether the pending line contains a `[...]` directive block.

1. Split the line on the first ` [` — everything before it is the **clean URL**; everything inside `[...]` is the **directive string**.
2. Parse the directive string (case-insensitive):
   - If it contains `transcript-only` → set mode flag `TRANSCRIPT_ONLY=true`
   - If it matches a timestamp pattern like `00:05:00-00:15:00` or `5:00-15:00` → extract `START` and `END` values and set `TIMESTAMP_RANGE=true`
   - If it contains `browser-mode` → set mode flag `BROWSER_MODE=true`
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
   - Report depth in progress indicator: `⏳ Step 0/7: Local folder detected (depth: N levels), checking for duplicates...`
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

Progress indicator for local folder: `⏳ Step 0/7: Local folder detected (depth: N levels, M images), checking for duplicates...`

If this is NOT a local folder entry, continue with the normal URL duplicate check below.

### Duplicate content check for URLs

Before transcribing, check whether this URL points to content that has already been analyzed under a different URL. Run two checks in order — stop at the first match.

### Check A — Video ID match

Extract the video ID from the **pending URL** using these rules:

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
| Other platforms | skip Check A, go to Check B |

Then parse every processed entry in `## Processed` in `watch_urls.md` and extract the video ID from each processed URL using the same rules.

If the pending URL's video ID matches any processed URL's video ID → **duplicate detected**. Note the matching processed entry (URL + analysis file path) and skip to Step 7.

### Check B — Title/slug match

If Check A found no match, run:

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

Report `✓ Step 0/7: No duplicate found — proceeding with full analysis.` and continue to Step 1.

---

## Step 1: Download content (Phase 1 — rate-limited)

All server calls in this step are subject to the inter-request delay and exponential backoff rules described at the end of this section.

**Content type detection**: First, determine what type of content the URL contains:
- **If `BROWSER_MODE=true`**: Skip yt-dlp entirely, proceed directly to Mode G (browser automation)
- Otherwise, try downloading with yt-dlp:
  - If yt-dlp reports "No video formats found" but successfully extracts metadata → **image/carousel post** → proceed to Mode F
  - If yt-dlp successfully downloads → **video/audio content** → proceed to Modes A-E based on directives
  - If yt-dlp fails with other errors → apply retry logic

---

### Mode A — Transcript-only (`TRANSCRIPT_ONLY=true`)

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

### Mode B — Audio download (default, or fallback from Mode A)

**Progress indicator**: `⏳ Step 1/7: Downloading audio...`

#### With timestamp range (`TIMESTAMP_RANGE=true`)

Download only the specified segment — `yt-dlp` will trim server-side before transferring:

```bash
yt-dlp --cookies-from-browser firefox --remote-components ejs:github \
  -x --audio-format mp3 \
  --download-sections "*<START>-<END>" \
  -o "/tmp/url-analyzer/<slug>.%(ext)s" '<URL>'
```

Replace `<START>` and `<END>` with the values parsed in Step 0 (e.g. `00:05:00` and `00:15:00`).

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

#### Stage D-3: Direct DASH manifest URL (user-supplied or already in watch_urls.md)

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
7. Replace this URL in watch_urls.md with the copied DASH URL
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

**If it fails**: Stop automated download attempts and prompt the user to download the images manually:

```
⚠️  Could not automatically download carousel images for:
    <URL>

Instagram carousel images must be downloaded manually. Please:

1. Go to https://snapinsta.app
2. Paste the following URL into the download box:
   <URL>
3. Download all images from the carousel
4. Save them into a dedicated folder, e.g.:
   ~/Desktop/MyCarousel/
5. Add the folder path to watch_urls.md under ## Pending:
   ~/Desktop/MyCarousel/ [title: <descriptive title>]
6. Re-run the analyzer — it will process the folder as a local image set

The original URL has been moved to ## Processed with a (pending-manual-download) note.
```

Then update `watch_urls.md`: move the URL from `## Pending` to `## Processed` with the annotation:
```
- <URL> (pending-manual-download YYYY-MM-DD — download carousel from https://snapinsta.app and re-add as local folder)
```

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

**When to use**: Instagram URLs that fail with Mode F due to platform blocks. Add `[browser-mode]` directive to the URL in `watch_urls.md`.

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

# Find all images recursively (up to depth 5, already validated in Step 0)
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
❌ Failed: <URL> — rate limited after 3 retries. Marked in watch_urls.md for manual retry.
```

---

### Inter-request delay

After each URL's download completes (success or skip) and before starting the **next** URL's download, wait:

```bash
sleep $((45 + RANDOM % 31))   # randomized: 45–75 seconds
```

- Apply this delay between every consecutive URL, including after Check B title lookups (see Step 0).
- Do **not** apply before the very first URL.
- The randomized jitter prevents a detectable fixed-interval fingerprint.

**Exception**: Local folder entries (Mode I) do not count toward the inter-request delay or batch cooldown counters, since no server calls are made. Browser automation mode (Mode G) does make network requests and should count toward rate limits.

### Batch cooldown

After every **5th** successful or attempted download, insert an additional pause before continuing:

```bash
sleep 300   # 5-minute cooldown after each group of 5
```

This gives the server-side rate-limit window time to reset before the next batch. The count resets after each cooldown.

**After all downloads complete**: Report `✓ Step 1/7: Downloads complete (X succeeded, Y skipped as duplicates, Z failed)`

---

## Step 2: Extract text content (Phase 2 — local)

No network calls. No delays. Runs entirely on local files produced in Phase 1.

The extraction method depends on the content type from Step 1:
- **Video/audio content** (`TRANSCRIPT_SOURCE=captions` or `whisper`) → Path A or B below
- **Image content** (`TRANSCRIPT_SOURCE=ocr`) → Path C below

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

## Step 3: Classify the content (Phase 2 — local)

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

## Step 5: Output format (Phase 2 — local)

**Progress indicator**: `⏳ Step 5/7: Saving analysis...`

Save to `~/Documents/truth-analyses/YYYY-MM-DD-<slugified-title>.md`:

```markdown
# Truth Analysis: <Post Title or Video Title>
**Source URL**: <URL>                          ← for URL entries
**Source**: Local folder: /path/to/folder (N images)   ← for local folder entries
**Analyzed**: YYYY-MM-DD
**Content type**: Medical | General Science
**Format**: Video | Audio | Image Post | Carousel (N images)

## Summary
<2–3 sentence overview of what the content claims>

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

## Share with a Friend
<A 2–4 sentence casual, jargon-free explanation written as if you're texting a friend who sent you the post. Start with the bottom line (trustworthy, partly true, or misleading), then explain what's right and what's wrong in everyday language. No medical or scientific terminology — a 15-year-old should understand it. End with one concrete suggestion for what to do instead, if relevant.>

Example tone: "That migraine remedy reel is mostly wishful thinking. The poppy-seed-in-milk trick sounds legit because poppy seeds *do* contain tiny traces of painkillers, but the amount you'd get from a spoonful is nowhere near enough to actually help a headache — like trying to fill a swimming pool with an eyedropper. If you get migraines often, seeing a neurologist will help way more than any home remedy."

## Broadly Shareable?
<A one-line yes / no / with-caveats verdict on whether this analysis is safe and useful to forward to friends, family, or group chats — followed by 1–2 sentences explaining why. Consider: Could sharing the *original post* (not this analysis) cause harm if someone follows the advice uncritically? Would sharing this analysis help people make better decisions? If the original content is mostly harmless or mostly accurate, a simple "Yes" with a brief note is fine. If the original content could cause real harm (e.g., delay medical treatment, unsafe remedy), say "Yes — and worth flagging" to encourage sharing the analysis as a counterweight. If the analysis is too niche or technical to be broadly useful, say "Not broadly — only relevant if…">
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
- The original URL (already in watch_urls.md)
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

## Step 7: Update watch_urls.md

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
