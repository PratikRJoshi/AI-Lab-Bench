---
name: translate-url
description: Given a video/audio URL, fetches the transcript or lyrics, detects the source language, and presents an interleaved English translation with a word-by-word glossary per line. Use when the user provides a URL and asks to translate, transcribe, or understand content in any language — including song lyrics, podcasts, speeches, or any video/audio. Supports YouTube (auto-captions preferred), Instagram, Twitter/X, Facebook, LinkedIn, and any yt-dlp-supported URL. Optional directive: [transcript-only] to use captions only without Whisper fallback.
---

# translate-url

Fetch transcript from a URL and produce an interleaved English translation with word-by-word glossary.

---

## Input format

The user provides a URL, optionally followed by a directive in `[...]`:

```
https://youtu.be/VIDEO_ID
https://youtu.be/VIDEO_ID [transcript-only]
```

**Directives:**
- `[transcript-only]` — use captions only; do not fall back to Whisper. Fail gracefully if no captions exist.

---

## Dependencies check

Before starting, check that required tools are available:

```bash
which yt-dlp || echo "MISSING: install with brew install yt-dlp"
which whisper || echo "MISSING: install with pip install openai-whisper"
```

If `yt-dlp` is missing, stop and instruct the user to install it. If `whisper` is missing, note it — it's only needed for the audio fallback path.

---

## Phase 1 — Transcription

**Progress:** `🔄 Fetching transcript from: <URL>`

### Step 1: Parse URL and directive

Split input on ` [` — everything before is the clean URL, everything inside `[...]` is the directive string.
- If directive contains `transcript-only` → set `TRANSCRIPT_ONLY=true`
- Use the clean URL for all shell commands

### Step 2: Try captions first

```bash
mkdir -p /tmp/translate-url
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  -o "/tmp/translate-url/%(id)s" "<CLEAN_URL>"
```

Check if any `.vtt` file was created in `/tmp/translate-url/`.

**If `.vtt` found:** Convert to plain text:
- Strip lines matching timestamp pattern: `^\d{2}:\d{2}:\d{2}\.\d{3}` and `-->` lines
- Strip the `WEBVTT` header line
- Strip HTML tags: `<[^>]+>`
- Remove duplicate consecutive lines
- Remove blank lines
- Result: ordered list of transcript lines

**If no `.vtt` found AND `TRANSCRIPT_ONLY=true`:**
```
❌ No captions available for this URL and [transcript-only] was set.
   To use Whisper transcription instead, remove the [transcript-only] directive.
```
Stop.

**If no `.vtt` found AND default mode:** proceed to Step 3.

### Step 3: Audio fallback (Whisper)

**Progress:** `   ⏳ No captions found — downloading audio for Whisper transcription...`

```bash
yt-dlp -x --audio-format mp3 -o "/tmp/translate-url/%(id)s.%(ext)s" "<CLEAN_URL>"
```

Then transcribe (replace `<FILE>` with the downloaded `.mp3` path):
```bash
whisper /tmp/translate-url/<ID>.mp3 --output_format txt --output_dir /tmp/translate-url/
```

Read the resulting `.txt` file. Split into lines — this is the transcript.

---

## Phase 2 — Translation

**Progress:** `🌐 Detecting language...`

### Step 4: Detect language

Examine the first 10 non-empty lines of the transcript and identify the language. Output:

```
🌐 Detected language: <Language Name>
```

### Step 5: English check

If the detected language is English:
```
[Content is already in English — no translation needed]

<full transcript>
```
Stop (skip remaining steps).

### Step 6: Translate line by line

For each non-empty line in the transcript:

**Skip silently if the line matches a filler pattern:**
- `[Music]`, `[Applause]`, `[Laughter]`, `[Cheering]`, or any `[...]` filler token
- Blank lines

**For each real line, output this interleaved block:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Line N — Original]
<original line>

[Line N — English]
<English translation of the line>

[Line N — Word by Word]
<word-by-word glossary>
```

**Word-by-word glossary rules:**

For **non-Latin script languages** (Japanese, Chinese, Korean, Arabic, Hindi, Thai, etc.) — include romanization:
```
君 (kimi) → you
名前 (namae) → name
呼ぶ (yobu) → to call
```

For **Latin-script languages** (Spanish, French, Portuguese, Italian, German, Dutch, etc.) — omit romanization:
```
siempre → always
contigo → with you
recuerdo → memory / I remember
```

If a word has multiple common meanings, list the most contextually relevant one first.

If a line is already in English, output:
```
[Line N — Original]
<line>

[already in English — no translation needed]
```

---

## Phase 3 — Save output to markdown

After all lines are translated, save the full output to a markdown file.

### Step 7: Get video title

```bash
yt-dlp --get-title "<CLEAN_URL>" 2>/dev/null
```

Use the title to create a filename slug:
- Lowercase
- Replace spaces and special characters with hyphens
- Strip non-alphanumeric characters (except hyphens)
- Truncate to 60 characters
- Example: "Tere Vaade Par Jiye Hum" → `tere-vaade-par-jiye-hum`

If title fetch fails, use the video ID as the slug.

### Step 8: Build the markdown file

File path: `~/Documents/translations/YYYY-MM-DD-<slug>.md`

Create `~/Documents/translations/` if it doesn't exist:
```bash
mkdir -p ~/Documents/translations
```

**File structure:**

```markdown
# <Video Title>

**Language:** <Detected Language> | **Source:** <CLEAN_URL> | **Date:** YYYY-MM-DD

> ⚠️ **Note:** Transcription generated by Whisper (speech-to-text). Accuracy may vary for songs, poetry, or heavy accents. Verify against official lyrics if precision matters.

---

## Line 1

> <original line>

**English:** <English translation>

| Word | Romanization | Meaning |
|------|--------------|---------|
| word | romanization | meaning |

---

## Line 2

> <original line>

**English:** <English translation>

| Word | Romanization | Meaning |
|------|--------------|---------|
| word | romanization | meaning |

---
```

**Rules:**
- The `⚠️ Note` disclaimer is included **only when Whisper was used** for transcription. Omit it when captions were the source.
- For **Latin-script languages** (Spanish, French, etc.), omit the Romanization column entirely:

```markdown
| Word | Meaning |
|------|---------|
| siempre | always |
```

- If a line was already in English, write:

```markdown
## Line N

> <original line>

*Already in English — no translation needed.*

---
```

- Filler lines (`[Music]`, `[Applause]`, etc.) are skipped and not written to the file.

### Step 9: Print save confirmation

```
✅ Saved to ~/Documents/translations/YYYY-MM-DD-<slug>.md
```

---

## Phase 4 — Cleanup

After saving the file:

```bash
rm -rf /tmp/translate-url/
```

Output: `✅ Temp files cleaned up.`

---

## Error handling reference

| Situation | Response |
|-----------|----------|
| `yt-dlp` not installed | Stop: "Install with: `brew install yt-dlp`" |
| `whisper` not installed (audio path needed) | Stop: "Install with: `pip install openai-whisper`" |
| Private/unavailable video | Report yt-dlp error, stop |
| No captions + `[transcript-only]` | Report error, stop (see Step 2) |
| Blank / filler line | Skip silently |
| Line already in English | Mark, skip glossary |
