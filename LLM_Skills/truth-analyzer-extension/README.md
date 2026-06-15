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

3. **The Firefox window opens automatically.** `start.sh` (called by `install.sh`) launches a dedicated Firefox window with the extension preloaded via Mozilla's `web-ext` CLI. The window uses a persistent profile at `~/.config/truth-analyzer/firefox-profile`, so IG logins, bookmarks, and cookies survive across runs.

   Want to load it into your main Firefox profile instead? Run with `SKIP_FIREFOX_AUTOLAUNCH=1 ./backend/start.sh` and load `extension/manifest.json` manually via `about:debugging`. Both can coexist — they hit the same backend.

4. **Use it:**
   - **Single post / article:** click the 🔍 toolbar icon (or right-click → *Analyze with Truth Analyzer*). A new tab opens with live progress, then the analysis renders with a sticky TOC.
   - **Channel / handle home page** (e.g. `instagram.com/<handle>/`, `youtube.com/@channel`, `x.com/<user>`, `tiktok.com/@user`): one click enumerates the top 10 most-recent posts and analyzes each one. Runtime is typically 30–60+ minutes — keep the tab open.

5. **Manage the backend / Firefox:**
   - Start both: `./backend/start.sh`
   - Stop backend: `kill $(cat /tmp/truth-analyzer.pid)`
   - Stop Firefox: `kill $(cat /tmp/truth-analyzer-webext.pid)` (or just close the window)
   - Logs: `tail -f /tmp/truth-analyzer.log` (backend) / `/tmp/truth-analyzer-webext.log` (Firefox)

## Configuration (`backend/.env`)

| Key | Default | Purpose |
|-----|---------|---------|
| `USE_CLAUDE_CLI` | `true` | Required — backend delegates to local `claude` |
| `MAX_CONCURRENT_JOBS` | `3` | How many analyses can run in parallel |
| `CHANNEL_BATCH_SIZE` | `10` | Posts to enumerate when clicked on a channel home page (skill caps at 25) |
| `PORT` | `5757` | Backend listen port |
| `RESUME_MAX_WAIT` | `600` | Seconds to wait for the VPN to return before failing a job |
| `RESUME_POLL_INTERVAL` | `20` | Seconds between connectivity probes while waiting |
| `RESUME_MAX_ATTEMPTS` | `3` | Max resume/retry cycles per job before giving up |
| `CLAUDE_IDLE_TIMEOUT` | `120` | Seconds of Claude silence before probing connectivity (detects a silent VPN stall) |
| `CONNECTIVITY_PROBE_URL` | _(empty)_ | Cheap HEAD/GET probe URL; defaults to `ANTHROPIC_BASE_URL`. Empty = short `claude --print` ping fallback |

Other keys in `.env.example` belong to the legacy in-process pipeline and are unused by the current `server.py`.

## Things that bite people

- **`claude` not logged in** → backend hangs. Run `claude` once interactively.
- **Backend not running** → extension shows an OS notification and an error tab. Run `./backend/start.sh`.
- **Instagram needs Firefox cookies** for `yt-dlp` access. Open the IG post in Firefox first while logged in.
- **Hit the concurrency cap** → extension shows a notification but does not open a tab. Wait for an analysis to finish, or raise `MAX_CONCURRENT_JOBS`.
- **Temporary add-on disappears on Firefox restart** — repeat step 3, or package as `.xpi` for permanent install.
- **VPN drops mid-analysis** → the job does *not* fail immediately. It pauses, shows "Connection lost — waiting for VPN…", and waits up to `RESUME_MAX_WAIT` (default 10 min). When the VPN returns it resumes the same Claude session via `claude --resume` (best-effort), falling back to a full re-run. Past the bound, it fails with a clear message. True byte-exact mid-call resume isn't possible — the analysis is one `claude --print` subprocess — so `--resume` continues the Claude *session*, not the exact byte where it stopped.
