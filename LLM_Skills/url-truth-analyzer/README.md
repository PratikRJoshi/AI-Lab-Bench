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
| Spotify | Podcast episodes (non-DRM) | Firefox cookies |
| Apple Podcasts | Episodes via iTunes Lookup → publisher RSS | None |
| Generic RSS | Podcast RSS feeds (RSS 2.0 + Atom; `<itunes:duration>` aware) | None |
| Local audio | `.mp3` / `.m4a` / `.wav` files (requires `[podcast]` opt-in) | N/A |

## Processing modes

| Mode | Trigger | What happens |
|------|---------|--------------|
| **Full audio** (default) | Any YouTube/LinkedIn URL | Downloads audio → Whisper transcription |
| **Audio + thumbnail** (Instagram/Facebook reels) | Instagram or Facebook reel URL with audio codec | Downloads both audio AND post thumbnail; Whisper transcribes audio while sub-agent OCRs thumbnail. Music-only / hallucinated transcripts auto-fallback to thumbnail text overlay. |
| **Silent-video / thumbnail-only** | Instagram/Facebook reel with no audio codec | Downloads thumbnail only; sub-agent extracts claims via Tesseract OCR + vision |
| **Image carousel** (authenticated Playwright) | Instagram image-only post (`/p/...?img_index=N`) | yt-dlp identifies the playlist but cannot extract image URLs; `ig_carousel_scraper.py` loads Firefox cookies into Chromium, walks the carousel via the "Next" button, and outputs per-slide image URLs which are then curl'd. |
| **Transcript-only** | `[transcript-only]` directive | Fetches YouTube captions only (no audio download) |
| **Timestamp range** | `[00:05:00-00:15:00]` directive | Downloads/transcribes only the specified segment |
| **Article** | `[article]` directive | curl + trafilatura body extraction |
| **Plain-text** | `[plain-text]` directive on a local .txt | Local read, no network |
| **Image/OCR** | Image posts or local folders | OCR + Claude vision analysis |
| **Podcast (short)** | Spotify/Apple/RSS/YouTube episode ≤30 min, or `.mp3`/`.m4a`/`.wav` with `[podcast]` | Single-pass Whisper `small` |
| **Podcast (long)** | Any podcast source >30 min (auto-detected via `ffprobe`) | Parallel chunked Whisper (`medium` default; `large-v3` opt-in via `[whisper-model: large-v3]`). 10-min chunks with timestamp headers so claim analysis can cite segments. |

## How to use

### 1. Add URLs to the watch list

Add URLs to `~/Documents/watch-urls.md` under the `## Pending` section:

```markdown
## Pending
https://youtu.be/VIDEO_ID
https://www.instagram.com/p/POST_ID/
~/Desktop/my-screenshots
https://youtu.be/LONG_VIDEO [transcript-only 00:10:00-00:30:00]
https://open.spotify.com/episode/EPISODE_ID
https://podcasts.apple.com/us/podcast/SHOW/idDIGITS?i=EP_ID
https://feeds.example.com/show.xml [podcast-rss episode: 2]
/Users/me/Downloads/long-interview.mp3 [podcast]
```

### Podcast support

Now supports podcast episodes from **Spotify** (`open.spotify.com/episode/...`), **Apple Podcasts** (resolved via the iTunes Lookup API → publisher RSS), **generic podcast RSS feeds** (`[podcast-rss]`, with `[episode: N]` for non-newest selection), and **local `.mp3`/`.m4a`/`.wav` files** (`[podcast]` opt-in, mirroring the `[plain-text]` pattern). Episodes are auto-classified by `ffprobe` duration: ≤30 min uses single-pass Whisper `small`; >30 min uses parallel chunked Whisper `medium` (or `large-v3` opt-in via `[whisper-model: large-v3]`) with 10-min segments. Long-podcast analyses are organized by chunk timestamp so you can see whether the show's accuracy holds throughout or drifts in specific segments. Spotify Originals (DRM-protected) and Apple Podcasts Subscriptions (paywalled) emit explicit failure messages directing you to the publisher's RSS feed instead.

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

- **yt-dlp** — media downloading from social platforms and Spotify (with `--cookies-from-browser firefox` for authenticated access)
- **ffmpeg** + **ffprobe** — audio extraction, format conversion, podcast chunking (Path D), and duration probing (Step 1.5)
- **OpenAI Whisper** (`whisper` CLI) — speech-to-text transcription. Models: `small` (default, short content); `medium` (~1.5 GB, long podcasts); `large-v3` (~3 GB, opt-in via `[whisper-model: large-v3]`)
- **Tesseract OCR** — text extraction from images and thumbnails
- **Python stdlib** `xml.etree.ElementTree` — RSS/Atom feed parsing for podcast Mode N (no install needed)
- **Firefox** — cookie source for authenticated downloads (must be logged in to the social platforms you want to scrape from)
- **Playwright + Chromium** — required for Instagram image carousels (yt-dlp can't extract image URLs from image-only carousels even with auth). Install once: `pip3 install --user --break-system-packages playwright && playwright install chromium`
- **trafilatura** (optional) — preferred article-body extractor for `[article]` URLs (`pandoc` is the fallback)

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
├── ig_carousel_scraper.py        # Authenticated Playwright scraper for Instagram image carousels
├── watch_urls_archive.md         # Processed entries older than 30 days
└── truth-analyses/               # Generated analysis files (current 30d; older move to archive/YYYY-MM/)
    ├── archive/
    │   ├── 2026-03/
    │   └── 2026-04/
    └── YYYY-MM-DD-*.md
```

## License

Personal project. Not intended for redistribution.
