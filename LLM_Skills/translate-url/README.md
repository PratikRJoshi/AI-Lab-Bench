# translate-url

A Claude Code skill that fetches the transcript or lyrics from any video/audio URL, detects the source language, and produces an interleaved English translation with a word-by-word glossary per line — saved as a formatted markdown file.

## What it does

Given a URL, the skill:

1. **Fetches transcript** — tries YouTube auto-captions first (fast); falls back to downloading audio and running OpenAI Whisper if captions aren't available
2. **Detects language** — identifies the source language from the transcript
3. **Translates line by line** — for each line outputs the original, an English translation, and a word-by-word glossary
4. **Saves to markdown** — writes a formatted `.md` file to `~/Documents/translations/` readable on desktop, mobile, and GitHub

## Output format

For each line:

```markdown
## Line 1

> तेरे वादे पर जिये हम, तो ये जान जूट जाना

**English:** We lived on your promises, so know that this life is a lie

| Word | Romanization | Meaning |
|------|--------------|---------|
| तेरे | tere | your |
| वादे | vaade | promises |
| पर | par | on / upon |
```

- **Non-Latin scripts** (Hindi, Japanese, Arabic, etc.): includes romanization column
- **Latin-script languages** (Spanish, French, etc.): romanization column omitted
- **Whisper transcriptions**: includes accuracy disclaimer at top of file

## Supported platforms

| Platform | Transcription method |
|----------|---------------------|
| YouTube | Auto-captions (preferred) or Whisper |
| Instagram, Twitter/X, Facebook, LinkedIn | Whisper (audio download) |
| Any yt-dlp-supported URL | Whisper (audio download) |

## Usage

```
/translate-url https://youtu.be/VIDEO_ID
/translate-url https://youtu.be/VIDEO_ID [transcript-only]
```

**Directives:**
- `[transcript-only]` — use captions only; fail gracefully if none available

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| `yt-dlp` | Caption/audio download | `brew install yt-dlp` |
| `whisper` | Audio transcription fallback | `pip install openai-whisper` |

## Output location

Files are saved to `~/Documents/translations/` with the naming pattern:

```
YYYY-MM-DD-<video-title-slug>.md
```

Example: `2026-04-02-tere-vaade-par-jiye-hum.md`
