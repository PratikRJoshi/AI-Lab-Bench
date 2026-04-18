# Truth Analyzer — Firefox Extension + Local Backend

One-click scientific fact-checking for any social media post.
Click the toolbar icon (or right-click any link) → analysis opens in a new tab with live progress.

## Architecture

```
Firefox Extension  →  POST /api/analyze  →  Flask server (localhost:5757)
                                                    │
                          ┌─────────────────────────┤
                          │                         │
                       yt-dlp                   Claude API
                       Whisper                  (or claude CLI)
                       Tesseract                Brave Search API
```

## Prerequisites

All of the following must already be installed:

| Tool | Install |
|------|---------|
| `yt-dlp` | `brew install yt-dlp` |
| `whisper` | `pip install openai-whisper` |
| `tesseract` | `brew install tesseract` |
| `claude` CLI | Cursor / Claude desktop install |
| Python 3.9+ | `brew install python` |

## Quick Setup

### 1. Install Python dependencies

```bash
cd ~/Documents/Learning/truth-analyzer-extension/backend
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in:

- **`ANTHROPIC_API_KEY`** — get one at [console.anthropic.com](https://console.anthropic.com)
  _OR_ set `USE_CLAUDE_CLI=true` to use your local `claude` CLI (no key needed)
- **`BRAVE_SEARCH_API_KEY`** — free tier (2000 queries/month) at [brave.com/search/api](https://brave.com/search/api/)
  Leave blank to skip web search — analysis still works.

### 3. Start the backend server

```bash
cd ~/Documents/Learning/truth-analyzer-extension/backend
python server.py
```

The server runs on `http://localhost:5757`. Keep this terminal open (or add it to macOS Login Items — see below).

### 4. Load the Firefox extension

1. Open Firefox → address bar → `about:debugging`
2. Click **"This Firefox"**
3. Click **"Load Temporary Add-on…"**
4. Navigate to `~/Documents/Learning/truth-analyzer-extension/extension/`
5. Select `manifest.json`

The 🔍 icon appears in your toolbar.

> **Permanent install**: Firefox extensions loaded via `about:debugging` are removed on browser restart.
> For a permanent install, package the extension:
> ```bash
> cd extension && zip -r truth-analyzer.xpi manifest.json background.js icons/
> ```
> Then install the `.xpi` file from `about:addons`.

## Using the Extension

| Action | How |
|--------|-----|
| Analyze current page | Click the 🔍 toolbar icon |
| Analyze any link | Right-click the link → "Analyze link with Truth Analyzer" |
| Analyze current page (context menu) | Right-click anywhere → "Analyze this page with Truth Analyzer" |
| Manual URL entry | Go to `http://localhost:5757` directly |

## Auto-start on boot (macOS)

Create a launchd plist:

```bash
cat > ~/Library/LaunchAgents/com.truth-analyzer.backend.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.truth-analyzer.backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOUR_USERNAME/Documents/Learning/truth-analyzer-extension/backend/server.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/YOUR_USERNAME/Documents/Learning/truth-analyzer-extension/backend</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/truth-analyzer.log</string>
  <key>StandardErrorPath</key><string>/tmp/truth-analyzer-err.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.truth-analyzer.backend.plist
```

Replace `YOUR_USERNAME` with your macOS username (`whoami`).

## Configuration Reference (`.env`)

| Key | Default | Description |
|-----|---------|-------------|
| `ANTHROPIC_API_KEY` | _(empty)_ | Anthropic API key for Claude |
| `USE_CLAUDE_CLI` | `false` | Use local `claude` CLI instead of API |
| `BRAVE_SEARCH_API_KEY` | _(empty)_ | Brave Search API key for evidence search |
| `PORT` | `5757` | Port for the local server |
| `WHISPER_MODEL` | `small` | Whisper model size (`tiny`/`base`/`small`/`medium`/`large`) |

## File Structure

```
truth-analyzer-extension/
├── backend/
│   ├── server.py          # Flask app — routes, SSE streaming
│   ├── analyzer.py        # Pipeline: download → transcribe → search → LLM
│   ├── prompts.py         # EBM SORT + claim validation system prompts
│   ├── requirements.txt
│   ├── .env.example
│   └── templates/
│       ├── index.html     # Manual URL entry page
│       └── results.html   # Live progress + analysis display
└── extension/
    ├── manifest.json      # Firefox WebExtension manifest (MV2)
    ├── background.js      # Toolbar click + context menu handler
    └── icons/
        ├── icon-16.png
        ├── icon-48.png
        └── icon-128.png
```

## Supported Platforms

| Platform | Content type | Method |
|----------|-------------|--------|
| Instagram | Reels, videos | yt-dlp audio |
| Instagram | Image posts, carousels | yt-dlp thumbnails |
| Facebook | Reels, videos | yt-dlp audio |
| YouTube | Videos, Shorts | yt-dlp captions → audio fallback |
| LinkedIn | Videos | yt-dlp / ffmpeg DASH |
| Twitter / X | Videos, images | yt-dlp |
| Other | Any yt-dlp supported URL | yt-dlp |
