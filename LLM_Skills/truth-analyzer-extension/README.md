# Truth Analyzer — Firefox Extension + Local Backend

One-click scientific fact-checking for any social media post directly from your browser.

## What it does

Click the 🔍 toolbar icon (or right-click any link) while browsing Instagram, YouTube, Facebook, or LinkedIn → a new tab opens with live progress as the post is downloaded, transcribed, searched, and analyzed by Claude.

The analysis applies:
- **EBM SORT** grading (A/B/C) for medical/health content — safety, outcomes, bias, and total-evidence lenses
- **Claim validation** for general science — supported / contested / refuted with citations

Output includes a **Share?** recommendation, full analysis, evidence links, verdict, and an ELI5 summary.

## Architecture

```
Firefox Extension
      │
      ▼
POST /api/analyze ──► Flask server (localhost:5757)
                              │
              ┌───────────────┼───────────────────┐
              │               │                   │
           yt-dlp          Whisper /          Claude via
         (download)        Tesseract          AWS Bedrock
                           (transcribe)       (analyze)
              │               │                   │
              └───────────────┴───────────────────┘
                              │
                    SSE stream → results.html
                    (live progress + final analysis)
```

## Quick Setup

### Prerequisites

| Tool | Install |
|------|---------|
| `yt-dlp` | `brew install yt-dlp` |
| `whisper` | `pip install openai-whisper` |
| `tesseract` | `brew install tesseract` |
| Python 3.9+ | `brew install python` |
| Firefox | [firefox.com](https://firefox.com) |

### 1. Create the virtual environment (once)

```bash
cd backend
./setup.sh
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` — pick one LLM path:

| Path | What to set |
|------|-------------|
| **AWS Bedrock** (recommended if you have AWS access) | `USE_BEDROCK=true` + AWS credentials via `./refresh.sh` |
| **Anthropic API** | `ANTHROPIC_API_KEY=sk-ant-...` |

Optionally set `TAVILY_API_KEY` for live web evidence search (free: 1000/month at [tavily.com](https://tavily.com)).

### 3. Start the server

```bash
./start.sh
```

### 4. Load the Firefox extension

1. Firefox → `about:debugging` → **This Firefox** → **Load Temporary Add-on…**
2. Select `extension/manifest.json`
3. The 🔍 icon appears in your toolbar

## Daily Use

| Action | How |
|--------|-----|
| Analyze current page | Click 🔍 toolbar icon |
| Analyze any link | Right-click → "Analyze link with Truth Analyzer" |
| Manual URL entry | Go to `http://localhost:5757` |

## AWS Bedrock Credential Refresh

Session tokens expire periodically. When they do:

```bash
# Interactive (prompts for each value)
./refresh.sh

# Paste the three export lines from your AWS console at once
./refresh.sh --paste

# Pass directly from your shell environment
./refresh.sh "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" "$AWS_SESSION_TOKEN"
```

`refresh.sh` writes credentials to `.env` and automatically restarts the server.

## File Structure

```
truth-analyzer-extension/
├── backend/
│   ├── server.py          # Flask: /api/analyze, /results/<id>, SSE stream, /api/save
│   ├── analyzer.py        # Pipeline: download → transcribe → search → LLM
│   ├── prompts.py         # EBM SORT + claim validation system prompts
│   ├── setup.sh           # One-time venv + dependency install
│   ├── start.sh           # Start server (uses venv)
│   ├── refresh.sh         # Refresh AWS credentials + restart server
│   ├── requirements.txt
│   ├── .env.example
│   └── templates/
│       ├── index.html     # Manual URL entry page
│       └── results.html   # Live SSE progress + analysis display
└── extension/
    ├── manifest.json      # Firefox WebExtension (MV2)
    ├── background.js      # Toolbar click + context menu → POST → open tab
    └── icons/
```

## Supported Platforms

Instagram (reels, image carousels), YouTube (videos, Shorts), Facebook (reels, videos), LinkedIn (videos), Twitter/X, and any yt-dlp supported URL.
