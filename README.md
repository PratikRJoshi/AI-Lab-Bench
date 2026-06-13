# AI-Lab-Bench

A collection of AI/LLM skills, benchmarks, and lab experiments.

## Quickstart — Truth Analyzer browser extension

Set up the Firefox extension that fact-checks any URL with one click:

```bash
git clone https://github.com/PratikRJoshi/AI-Lab-Bench.git ~/AI-Lab-Bench
cd ~/AI-Lab-Bench
./bootstrap.sh
```

The script installs system tools (yt-dlp, ffmpeg, tesseract, pandoc), Python deps (whisper, trafilatura, playwright + Chromium), registers the `url-truth-analyzer` skill in `~/.claude/skills/`, and starts the backend. Then load `LLM_Skills/truth-analyzer-extension/extension/manifest.json` in Firefox via `about:debugging`. macOS only.

See [LLM_Skills/truth-analyzer-extension/README.md](./LLM_Skills/truth-analyzer-extension/README.md) for usage details and configuration.

## Contents

- **[LLM_Skills](./LLM_Skills/)** — Cursor-compatible skills for AI coding assistants (e.g., URL truth analysis, EBM SORT evaluation)
- **[browser-automation](./browser-automation/)** — Playwright scripts for automating browser tasks (e.g., Chase Offers auto-clicker)
- **[bogleheads-mcp-server](./bogleheads-mcp-server/)** — MCP server for Bogleheads forum search and context

## License

MIT (or specify your preferred license)
