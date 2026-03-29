# URL Truth Analyzer

An AI agent skill for [Cursor](https://cursor.sh) that analyzes health and science claims in video, audio, and image content from social media and the web. It transcribes, classifies, and fact-checks content using evidence-based medicine (EBM) grading and peer-reviewed sources.

## What it does

Given a URL or a local folder of screenshots, the skill:

1. **Downloads** audio (via `yt-dlp`) or images from the source
2. **Transcribes** speech with OpenAI Whisper, or extracts text from images with Tesseract OCR + Claude vision analysis
3. **Classifies** content as Medical or General Science
4. **Analyzes** claims using the appropriate framework:
   - **Medical content** — EBM SORT (Strength of Recommendation Taxonomy) analysis with safety, outcomes, bias, and total-evidence lenses, graded A/B/C
   - **General science** — Claim-by-claim validation against scientific consensus with credible sources
5. **Saves** a structured markdown analysis and syncs to this repository

## Supported platforms

| Platform | Content types | Auth method |
|----------|--------------|-------------|
| YouTube | Videos, Shorts | Firefox cookies |
| Instagram | Reels, image posts, carousels | Firefox cookies |
| Facebook | Reels, Watch videos | Firefox cookies |
| LinkedIn | Post videos, DASH streams | Firefox cookies + ffmpeg fallback |
| Twitter/X | Video posts, image posts | Firefox cookies |
| Waking Up | Course audio | Firefox cookies |
| Local folders | Screenshots, photos (recursive up to 5 levels) | N/A |

## Processing modes

| Mode | Trigger | What happens |
|------|---------|--------------|
| **Full audio** (default) | Any video URL | Downloads audio → Whisper transcription |
| **Transcript-only** | `[transcript-only]` directive | Fetches YouTube captions only (no audio download) |
| **Timestamp range** | `[00:05:00-00:15:00]` directive | Downloads/transcribes only the specified segment |
| **Browser automation** | `[browser-mode]` directive | Uses Playwright for Instagram posts that block yt-dlp |
| **Image/OCR** | Image posts or local folders | OCR + Claude vision analysis |

## How to use

### 1. Add URLs to the watch list

Add URLs to `~/Documents/watch-urls.md` under the `## Pending` section:

```markdown
## Pending
https://youtu.be/VIDEO_ID
https://www.instagram.com/p/POST_ID/
~/Desktop/my-screenshots
https://youtu.be/LONG_VIDEO [transcript-only 00:10:00-00:30:00]
```

### 2. Trigger processing

In Cursor, say: **"process watch-urls.md"**

The skill processes each entry sequentially with rate limiting (45–75s between server requests, 5-min cooldown every 5 downloads), detects duplicates, and produces analysis files.

### 3. Read the results

Analyses are saved to `~/Documents/truth-analyses/YYYY-MM-DD-<slug>.md` and automatically pushed to this repository.

## Analysis output format

Each analysis follows a consistent structure:

```markdown
# Truth Analysis: <Title>
**Source URL**: <url>
**Analyzed**: YYYY-MM-DD
**Content type**: Medical | General Science
**Format**: Video | Audio | Image Post | Carousel (N images)

## Summary
## Analysis
### SORT Analysis (medical) or Claim Validation (science)
### Visual Analysis (for image content)
## Evidence / Validation Links
## Verdict
```

## SORT grading scale

| Grade | Meaning | Evidence required |
|:-----:|---------|-------------------|
| **A** | Consistent, good-quality patient-oriented evidence | Multiple RCTs/systematic reviews with patient-oriented outcomes (POEMs) |
| **B** | Limited or inconsistent patient-oriented evidence | RCTs with limitations, or good evidence for disease-oriented endpoints (DOEs) only |
| **C** | Consensus, expert opinion, or no clinical evidence | Case series, mechanistic reasoning, anecdote, or no studies cited |

## Stats

| Metric | Count |
|--------|------:|
| Total analyses | 51 |
| Medical content | 21 |
| General science | 28 |
| Image/carousel analyses | 8 |
| Local folder analyses | 7 |
| Date range | 2026-03-02 to 2026-03-29 |

### Platform breakdown

| Source | Analyses |
|--------|------:|
| YouTube | 36 |
| Instagram | 3 |
| Local folders | 7 |
| LinkedIn | 2 |
| Facebook | 1 |
| Other | 2 |

## Dependencies

- **yt-dlp** — media downloading from social platforms
- **ffmpeg** — audio extraction and format conversion
- **OpenAI Whisper** (`whisper` CLI, `small` model) — speech-to-text transcription
- **Tesseract OCR** — text extraction from images
- **Firefox** — cookie source for authenticated downloads
- **Playwright** (optional) — browser automation for Instagram when yt-dlp is blocked

## File structure

```
url-truth-analyzer/
├── SKILL.md                      # Main skill instructions (agent reads this)
├── README.md                     # This file
├── ebm-reference.md              # EBM SORT grading rubric and PubMed search guide
├── linkedin-workaround.md        # LinkedIn DASH stream extraction guide
├── IMAGE_SUPPORT.md              # Image/carousel processing documentation
├── RECURSIVE_FOLDER_UPDATE.md    # Local folder recursive scanning docs
├── FOLDER_DEPTH_EXAMPLES.md      # Folder depth validation examples
└── truth-analyses/               # All generated analysis files (synced to GitHub)
    ├── 2026-03-02-*.md
    ├── ...
    └── 2026-03-29-*.md
```

## License

Personal project. Not intended for redistribution.
