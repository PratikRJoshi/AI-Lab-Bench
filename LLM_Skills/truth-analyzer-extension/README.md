# Truth Analyzer — Firefox Extension

One-click fact-check for any URL. The extension hands the URL to a tiny local
backend, which delegates to your Claude Code CLI's `url-truth-analyzer` skill.
Results stream back to a new Firefox tab with a clickable table of contents.

```
Firefox 🔍 toolbar  →  localhost:5757  →  claude --print (url-truth-analyzer skill)
                                           │
                                           └──→ analysis markdown streamed back
```

## Setup (5 steps)

1. **Install prerequisites:**
   ```bash
   brew install python yt-dlp tesseract
   pip install -U openai-whisper
   ```
   You also need the `claude` CLI on `PATH` and logged in — run `claude` once interactively if you haven't.

2. **Clone the repo and run the installer:**
   ```bash
   git clone https://github.com/PratikRJoshi/AI-Lab-Bench.git ~/AI-Lab-Bench
   cd ~/AI-Lab-Bench/LLM_Skills/truth-analyzer-extension
   ./install.sh
   ```
   The installer creates the venv, installs Python deps, copies `.env`, and starts the backend on `http://localhost:5757`.

3. **Load the Firefox extension** (one-time per Firefox profile):
   - Open `about:debugging` → **This Firefox** → **Load Temporary Add-on…**
   - Pick `extension/manifest.json` from this directory.

4. **Use it:** click the 🔍 toolbar icon on any page (or right-click → *Analyze with Truth Analyzer*). A new tab opens with live progress, then the analysis renders with a sticky TOC.

5. **Manage the backend:**
   - Start: `./backend/start.sh`
   - Stop: `kill $(cat /tmp/truth-analyzer.pid)`
   - Logs: `tail -f /tmp/truth-analyzer.log`

## Configuration (`backend/.env`)

| Key | Default | Purpose |
|-----|---------|---------|
| `USE_CLAUDE_CLI` | `true` | Required — backend delegates to local `claude` |
| `MAX_CONCURRENT_JOBS` | `3` | How many analyses can run in parallel |
| `PORT` | `5757` | Backend listen port |

Other keys in `.env.example` belong to the legacy in-process pipeline and are unused by the current `server.py`.

## Things that bite people

- **`claude` not logged in** → backend hangs. Run `claude` once interactively.
- **Backend not running** → extension shows an OS notification and an error tab. Run `./backend/start.sh`.
- **Instagram needs Firefox cookies** for `yt-dlp` access. Open the IG post in Firefox first while logged in.
- **Hit the concurrency cap** → extension shows a notification but does not open a tab. Wait for an analysis to finish, or raise `MAX_CONCURRENT_JOBS`.
- **Temporary add-on disappears on Firefox restart** — repeat step 3, or package as `.xpi` for permanent install.
