"""
Analysis pipeline: download → transcribe → search → LLM analyze → cleanup.
Each step calls emit(event, message) to stream progress to the SSE endpoint.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import requests

from prompts import build_analysis_prompt, build_system_prompt

EmitFn = Callable[[str, str], None]

WORK_DIR = Path(tempfile.gettempdir()) / "truth-analyzer"
WORK_DIR.mkdir(exist_ok=True)

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "anthropic.claude-sonnet-4-5-20250929-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
USE_BEDROCK = os.getenv("USE_BEDROCK", "false").lower() == "true"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_CLAUDE_CLI = os.getenv("USE_CLAUDE_CLI", "false").lower() == "true"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

# Path to the AI-Lab-Bench repo root, used as cwd for `claude --print` so the
# url-truth-analyzer project skill resolves correctly.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# How many recent posts to enumerate when the user clicks the extension on a
# channel/profile home page. Capped at 25 by the skill itself.
CHANNEL_BATCH_SIZE = int(os.getenv("CHANNEL_BATCH_SIZE", "10"))


# ── VPN / connectivity resilience ──────────────────────────────────────────
# The analysis runs through the corporate Claude gateway, which is only
# reachable on VPN. If the VPN drops mid-analysis we don't want to hard-fail:
# pause, wait (bounded) for connectivity to return, then resume the Claude
# session via `claude --resume` (best-effort) or re-run.
RESUME_MAX_WAIT = int(os.getenv("RESUME_MAX_WAIT", "600"))          # total secs to wait for VPN
RESUME_POLL_INTERVAL = int(os.getenv("RESUME_POLL_INTERVAL", "20"))  # secs between connectivity probes
RESUME_MAX_ATTEMPTS = int(os.getenv("RESUME_MAX_ATTEMPTS", "3"))     # resume/retry cycles per job
CLAUDE_IDLE_TIMEOUT = int(os.getenv("CLAUDE_IDLE_TIMEOUT", "120"))   # secs of PTY silence before a connectivity check
# Optional cheap connectivity probe (HEAD/GET). Defaults to ANTHROPIC_BASE_URL
# when set; if empty, _check_connectivity falls back to a short `claude --print`
# ping (tests the real dependency, but costs a small model call per probe).
CONNECTIVITY_PROBE_URL = os.getenv("CONNECTIVITY_PROBE_URL", "") or os.getenv("ANTHROPIC_BASE_URL", "")

# Stream Claude's full stream-json activity (every assistant turn, tool call, and
# tool result) to the UI as "activity" SSE events. The browser keeps these behind
# a "Show detailed activity" toggle. Set to "false" to disable the firehose.
STREAM_CLAUDE_ACTIVITY = os.getenv("STREAM_CLAUDE_ACTIVITY", "true").lower() == "true"


def _render_claude_activity(evt: dict) -> list[str]:
    """Turn one stream-json event into human-readable activity line(s).

    Firehose: includes full tool inputs and full tool results, mirroring what
    you'd see in the Claude CLI. Returns an empty list for events with nothing
    worth showing.
    """
    out: list[str] = []
    etype = evt.get("type")
    if etype == "system":
        sub = evt.get("subtype") or "system"
        model = evt.get("model")
        out.append(f"⚙️  system: {sub}" + (f" ({model})" if model else ""))
    elif etype == "assistant":
        for block in (evt.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            bt = block.get("type")
            if bt == "text":
                txt = (block.get("text") or "").strip()
                if txt:
                    out.append(txt)
            elif bt == "thinking":
                txt = (block.get("thinking") or "").strip()
                if txt:
                    out.append("💭 " + txt)
            elif bt == "tool_use":
                name = block.get("name") or "tool"
                try:
                    inp = json.dumps(block.get("input") or {}, ensure_ascii=False)
                except Exception:
                    inp = str(block.get("input"))
                out.append(f"🔧 {name}: {inp}")
    elif etype == "user":
        for block in (evt.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            content = block.get("content")
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        parts.append(c.get("text") or "")
                    else:
                        parts.append(json.dumps(c, ensure_ascii=False))
                text = "\n".join(parts)
            elif isinstance(content, str):
                text = content
            else:
                text = json.dumps(content, ensure_ascii=False)
            prefix = "❌ result" if block.get("is_error") else "←  result"
            out.append(f"{prefix}: {text}")
    elif etype == "result":
        out.append("✅ run finished")
    return out


class _ConnectivityError(RuntimeError):
    """Raised when a claude --print run fails because the network/VPN is down."""


# Channel/profile home pages we want to auto-expand. The skill enumerates
# these via channel_enumerator.py and analyzes the top-N most-recent posts.
# Mirrors the patterns the skill itself recognizes (see SKILL.md, "channel
# entry"), but applied client-side here so we can pass a [channel:N] hint
# and surface the longer expected runtime in progress events.
_YOUTUBE_CHANNEL_RE = re.compile(
    r"^https?://(?:www\.)?youtube\.com/(?:@[^/?#]+|c/[^/?#]+|user/[^/?#]+|channel/UC[^/?#]+)/?$",
    re.IGNORECASE,
)
_INSTAGRAM_PROFILE_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?!p/|reel/|reels/|tv/|stories/|explore/|accounts/|direct/)"
    r"([^/?#]+)/?$",
    re.IGNORECASE,
)
_TWITTER_PROFILE_RE = re.compile(
    r"^https?://(?:www\.)?(?:twitter\.com|x\.com)/(?!i/|home$|search$|explore$|notifications$|messages$|compose$)"
    r"([A-Za-z0-9_]{1,15})/?$",
    re.IGNORECASE,
)
_TIKTOK_PROFILE_RE = re.compile(
    r"^https?://(?:www\.)?tiktok\.com/@[^/?#]+/?$",
    re.IGNORECASE,
)


def _is_channel_url(url: str) -> bool:
    """True for handle/profile home pages that should expand to a batch."""
    return bool(
        _YOUTUBE_CHANNEL_RE.match(url)
        or _INSTAGRAM_PROFILE_RE.match(url)
        or _TWITTER_PROFILE_RE.match(url)
        or _TIKTOK_PROFILE_RE.match(url)
    )


# The skill narrates its process across many assistant turns; we keep only the
# final deliverable by asking it to fence the analysis with these markers, then
# extracting the fenced span(s). Falls back to the full transcript if absent.
_ANALYSIS_MARKER_INSTRUCTION = (
    "IMPORTANT — output format: wrap ONLY your final analysis markdown between "
    "two marker lines, `<<<ANALYSIS>>>` on its own line immediately before it and "
    "`<<<END_ANALYSIS>>>` on its own line immediately after it. Put no preamble, "
    "status updates, or commentary inside those markers — only the analysis itself."
)
_ANALYSIS_SENTINEL_RE = re.compile(
    r"<<<ANALYSIS>>>\s*(.*?)\s*<<<END_ANALYSIS>>>", re.DOTALL
)


def _extract_analysis(text: str) -> str:
    """Return only the analysis the skill fenced in <<<ANALYSIS>>> markers.

    Concatenates every fenced span (channel batches may fence each item). If no
    markers are present — older skill, refusal, or a malformed stream — fall
    back to the full text so nothing is ever lost.
    """
    spans = [
        m.group(1).strip()
        for m in _ANALYSIS_SENTINEL_RE.finditer(text)
        if m.group(1).strip()
    ]
    return "\n\n".join(spans) if spans else text


def run_skill_analysis(url: str, emit: EmitFn, raw_log_path: str | None = None) -> str:
    """Delegate URL analysis to the local Claude Code CLI's url-truth-analyzer skill.

    For a single post/article URL, the skill returns one analysis. For a
    handle/profile home page, the URL is annotated with `[channel:N]` so the
    skill enumerates the top-N most-recent posts and analyzes each one. In both
    cases the inline-URL convention implies `[display-only]` — no files are
    written and watch-urls.md is untouched.
    """
    clean_url = _strip_tracking(url)
    is_channel = _is_channel_url(clean_url)
    emit("progress", f"🔗 Cleaned URL: {clean_url}")

    if is_channel:
        emit(
            "progress",
            f"📺 Channel page detected — analyzing the top {CHANNEL_BATCH_SIZE} most-recent posts. "
            "This typically takes 30–60+ minutes; keep this tab open.",
        )
        skill_input = f"{clean_url} [channel:{CHANNEL_BATCH_SIZE}]"
        prompt = (
            "Use the url-truth-analyzer skill on this channel/profile entry. "
            "Enumerate the most-recent posts via Phase 0 Step 0 (channel expansion), "
            "then run the full analysis pipeline on each enumerated permalink and "
            "return every per-item analysis concatenated, with clear headings.\n\n"
            + _ANALYSIS_MARKER_INSTRUCTION
            + f"\n\nEntry: {skill_input}"
        )
        heartbeats = [
            (30,   "📥 Enumerating posts on the channel …"),
            (90,   "📝 Item 1 in flight (download + transcribe) …"),
            (300,  "🌐 Several items processed; still going through the batch …"),
            (900,  "⏳ ~15 min in. Channel batches commonly run 30–60 min."),
            (1800, "⏳ Still working — long batches can take an hour. Don't close the tab."),
        ]
        timeout = 60 * 90  # 90 min hard ceiling for a 10-item batch
    else:
        emit("progress", "🤖 Handing off to local Claude Code (url-truth-analyzer skill) …")
        prompt = (
            f"Use the url-truth-analyzer skill to analyze this URL: {clean_url}\n\n"
            "Return the full analysis markdown as your final response.\n\n"
            + _ANALYSIS_MARKER_INSTRUCTION
        )
        heartbeats = [
            (15,  "📥 Skill is downloading content (yt-dlp / article fetch / OCR) …"),
            (60,  "📝 Transcribing or extracting text …"),
            (150, "🌐 Searching for supporting / refuting evidence …"),
            (240, "🧠 Analyzing claims — almost there …"),
            (360, "⏳ Still working (long videos can take 5+ minutes) …"),
        ]
        timeout = 900

    output = _run_claude_resilient(
        prompt, emit, heartbeats=heartbeats, timeout=timeout, cwd=_REPO_ROOT,
        raw_log_path=raw_log_path,
    )
    if not output.strip():
        raise RuntimeError(
            "claude --print returned empty output. Check that the url-truth-analyzer "
            "skill is available (`claude` interactively → /skills) and that you are logged in."
        )
    # Strip the skill's step-by-step narration; keep only the final analysis the
    # skill wrapped in <<<ANALYSIS>>> … <<<END_ANALYSIS>>> markers.
    return _extract_analysis(output)


def run_analysis(url: str, emit: EmitFn) -> str:
    """Run the full pipeline for *url*, streaming progress via *emit*.

    Returns the final analysis markdown string.
    """
    clean_url = _strip_tracking(url)
    job_slug = _slugify(clean_url)[:40]
    work = WORK_DIR / job_slug
    work.mkdir(exist_ok=True)

    try:
        emit("progress", f"🔍 Detecting content type for {clean_url} …")
        platform = _detect_platform(clean_url)
        emit("progress", f"📡 Platform detected: {platform}")

        # ------------------------------------------------------------------
        # Step 1 — Download
        # ------------------------------------------------------------------
        emit("progress", "⬇️  Downloading content …")
        content_type, media_files = _download(clean_url, work, platform, emit)
        emit("progress", f"✅ Download complete ({content_type}, {len(media_files)} file(s))")

        # ------------------------------------------------------------------
        # Step 2 — Transcribe / OCR
        # ------------------------------------------------------------------
        emit("progress", "📝 Extracting text …")
        transcript = _extract_text(content_type, media_files, work, job_slug, emit)
        word_count = len(transcript.split())
        emit("progress", f"✅ Text extracted ({word_count} words)")
        emit("transcript", transcript)  # save for error fallback

        # ------------------------------------------------------------------
        # Step 3 — Web search for claim validation
        # ------------------------------------------------------------------
        emit("progress", "🌐 Searching for supporting / refuting evidence …")
        search_context = _search(transcript, emit)
        emit("progress", "✅ Search complete")

        # ------------------------------------------------------------------
        # Step 4 — LLM analysis
        # ------------------------------------------------------------------
        emit("progress", "🧠 Analyzing claims (LLM) …")
        analysis_md = _analyze(clean_url, transcript, search_context, emit)
        emit("progress", "✅ Analysis complete")

        return analysis_md

    finally:
        # ------------------------------------------------------------------
        # Step 5 — Cleanup
        # ------------------------------------------------------------------
        try:
            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Step 0 — Helpers
# ---------------------------------------------------------------------------

# Matches CSI sequences (ESC [ … final-byte) and OSC sequences (ESC ] … BEL/ST).
# claude --print runs through a PTY, which adds terminal-mode setup/teardown
# bytes that markdown renderers shouldn't see. Plain ESC and stray \r are also
# scrubbed so they don't break the rendered output.
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][\x20-\x7e]|\x1b[78]|\x0e|\x0f")


def _strip_terminal_escapes(text: str) -> str:
    return _ANSI_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")


def _strip_tracking(url: str) -> str:
    """Remove common tracking params (igsh=, utm_*, fbclid=, etc.)."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    keep_keys = {"v", "t", "list", "index"}
    tracking_prefixes = ("utm_", "igsh", "fbclid", "gclid", "ref", "s", "si")
    cleaned = {
        k: v for k, v in params.items()
        if k in keep_keys or not any(k.startswith(p) for p in tracking_prefixes)
    }
    new_query = urllib.parse.urlencode(cleaned, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def _slugify(text: str) -> str:
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    return text.strip("-").lower()


def _detect_platform(url: str) -> str:
    u = url.lower()
    if "instagram.com" in u:
        return "instagram"
    if "facebook.com" in u or "fb.watch" in u:
        return "facebook"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "linkedin.com" in u or "licdn.com" in u:
        return "linkedin"
    if "twitter.com" in u or "x.com" in u:
        return "twitter"
    return "other"


# ---------------------------------------------------------------------------
# Step 1 — Download
# ---------------------------------------------------------------------------

def _download(url: str, work: Path, platform: str, emit: EmitFn):
    """Returns (content_type, [list of media file paths])."""
    slug = work.name

    # Try audio download first
    audio_out = work / f"{slug}.%(ext)s"
    cmd = [
        "yt-dlp", "--cookies-from-browser", "firefox",
        "-x", "--audio-format", "mp3",
        "-o", str(audio_out), url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    mp3_files = list(work.glob("*.mp3"))
    if mp3_files:
        return "audio", mp3_files

    combined_output = result.stdout + result.stderr

    # Image-only post — yt-dlp explicitly says no video formats
    if "No video formats found" in combined_output:
        emit("progress", "🖼️  Image post detected — downloading thumbnails …")
        return _download_images(url, work, slug)

    # yt-dlp may have downloaded a non-mp3 audio file (m4a, opus, etc.)
    audio_files = (
        list(work.glob("*.m4a")) + list(work.glob("*.opus")) +
        list(work.glob("*.ogg")) + list(work.glob("*.wav"))
    )
    if audio_files:
        return "audio", audio_files

    # Fallback: try downloading as a thumbnail/image
    emit("progress", "🖼️  No audio found — trying image/thumbnail download …")
    thumb_cmd = [
        "yt-dlp", "--cookies-from-browser", "firefox",
        "--skip-download", "--write-thumbnail", "--convert-thumbnails", "jpg",
        "-o", str(work / f"{slug}.%(ext)s"), url,
    ]
    subprocess.run(thumb_cmd, capture_output=True, text=True)
    img_files = sorted(
        list(work.glob("*.jpg")) + list(work.glob("*.jpeg")) + list(work.glob("*.png"))
    )
    if img_files:
        return "image", img_files

    # Last resort: treat as image post even without the explicit error
    emit("progress", "🖼️  Attempting image extraction from metadata …")
    return _download_images(url, work, slug)


def _download_images(url: str, work: Path, slug: str):
    """Download carousel / image post thumbnails."""
    cmd = [
        "yt-dlp", "--cookies-from-browser", "firefox",
        "--skip-download", "--write-thumbnail", "--convert-thumbnails", "jpg",
        "-o", str(work / f"{slug}.%(autonumber)s.%(ext)s"), url,
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    img_files = sorted(
        list(work.glob("*.jpg")) + list(work.glob("*.jpeg")) + list(work.glob("*.png"))
    )
    if img_files:
        return "image", img_files

    # Extract image URLs from JSON metadata and curl-download them
    meta_cmd = ["yt-dlp", "--cookies-from-browser", "firefox", "-J", url]
    meta_result = subprocess.run(meta_cmd, capture_output=True, text=True)
    try:
        meta = json.loads(meta_result.stdout)
    except json.JSONDecodeError:
        # Metadata unavailable — fall through to browser automation below
        meta = None

    if meta is None:
        browser_result = _download_images_browser(url, work, slug)
        if browser_result:
            return browser_result
        raise RuntimeError(
            "Could not download content from this post. "
            "It may be a static image post — try opening the post in Firefox first "
            "so your session is active, then retry."
        )

    raw_entries = meta.get("entries") or [meta]
    # Filter out None placeholders yt-dlp sometimes inserts for unavailable items
    entries = [e for e in raw_entries if isinstance(e, dict)]
    if not entries:
        entries = [meta] if isinstance(meta, dict) else []

    img_urls = []
    for entry in entries:
        thumbs = [t for t in (entry.get("thumbnails") or []) if isinstance(t, dict)]
        if thumbs:
            # Pick the largest by area; fall back to last in list
            best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
            if best.get("url"):
                img_urls.append(best["url"])

    downloaded = []
    for n, img_url in enumerate(img_urls, 1):
        dest = work / f"{slug}-{n}.jpg"
        r = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        downloaded.append(dest)

    if not downloaded:
        # Final fallback: Playwright browser automation (handles Instagram image posts)
        browser_result = _download_images_browser(url, work, slug)
        if browser_result:
            return browser_result
        raise RuntimeError(
            "Could not download content from this post. "
            "It may be a static image post — try opening the post in Firefox first "
            "so your session is active, then retry."
        )

    return "image", downloaded


def _download_images_browser(url: str, work: Path, slug: str):
    """Playwright-based fallback for Instagram image posts that yt-dlp can't handle."""
    scraper = Path.home() / ".cursor" / "skills" / "url-truth-analyzer" / "instagram_scraper.py"
    if not scraper.exists():
        return None

    try:
        # Use venv python if available so playwright is found
        venv_python = Path(__file__).parent / "truth-analyzer-env" / "bin" / "python3"
        python_bin = str(venv_python) if venv_python.exists() else "python3"
        result = subprocess.run(
            [python_bin, str(scraper), url],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        # scraper returns {"success": true, "images": ["url1", "url2", ...]}
        img_urls = data.get("images") or []
    except Exception:
        return None

    if not img_urls:
        return None

    downloaded = []
    for n, img_url in enumerate(img_urls, 1):
        dest = work / f"{slug}-browser-{n}.jpg"
        try:
            r = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            r.raise_for_status()
            dest.write_bytes(r.content)
            downloaded.append(dest)
        except Exception:
            continue

    return ("image", downloaded) if downloaded else None


# ---------------------------------------------------------------------------
# Step 2 — Transcribe / OCR
# ---------------------------------------------------------------------------

def _extract_text(content_type: str, media_files: list, work: Path, slug: str, emit: EmitFn) -> str:
    if content_type == "audio":
        return _whisper_transcribe(media_files[0], work, emit)
    return _ocr_and_describe(media_files, emit)


def _whisper_transcribe(mp3_path: Path, work: Path, emit: EmitFn) -> str:
    emit("progress", f"🎙️  Transcribing audio with Whisper ({WHISPER_MODEL} model) …")
    cmd = [
        "whisper", str(mp3_path),
        "--model", WHISPER_MODEL,
        "--output_format", "txt",
        "--output_dir", str(work),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    txt_files = list(work.glob("*.txt"))
    if txt_files:
        return txt_files[0].read_text(encoding="utf-8")
    raise RuntimeError(f"Whisper failed: {result.stderr[-500:]}")


def _ocr_and_describe(img_files: list, emit: EmitFn) -> str:
    parts = []
    for n, img_path in enumerate(img_files, 1):
        emit("progress", f"🔎  OCR on image {n}/{len(img_files)} …")
        result = subprocess.run(
            ["tesseract", str(img_path), "stdout", "--dpi", "300"],
            capture_output=True, text=True,
        )
        ocr_text = result.stdout.strip()
        parts.append(f"=== Image {n} ===\nOCR Text: {ocr_text or '(no text detected)'}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Step 3 — Brave Search
# ---------------------------------------------------------------------------

def _search(transcript: str, emit: EmitFn) -> str:
    if TAVILY_API_KEY:
        return _search_tavily(transcript, emit)
    if BRAVE_API_KEY:
        return _search_brave(transcript, emit)
    emit("progress", "⚠️  No search API key — skipping web search (set TAVILY_API_KEY in .env)")
    return ""


def _generate_search_queries(transcript: str) -> list[str]:
    # Strip OCR structural markers, get plain text
    plain = re.sub(r"=== Image \d+ ===", "", transcript)
    plain = re.sub(r"(OCR Text:|Visual Content:|Claims:|Source:)[^\n]*", "", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    # Take first 120 chars as the base query
    base = plain[:120].rsplit(" ", 1)[0]
    if not base:
        base = plain[:80]
    return [
        f"{base} fact check",
        f"{base} scientific evidence",
        f"{base} research study",
    ]


def _search_tavily(transcript: str, emit: EmitFn) -> str:
    summary = transcript[:300].replace("\n", " ").strip()
    queries = _generate_search_queries(summary)
    all_results = []
    for q in queries[:3]:
        emit("progress", f"🔎  Searching (Tavily): {q[:60]} …")
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": q,
                    "max_results": 5,
                    "search_depth": "basic",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("results", []):
                all_results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "description": r.get("content", "")[:200],
                })
            time.sleep(0.3)
        except Exception as e:
            emit("progress", f"⚠️  Tavily search error: {e}")

    return _format_search_results(all_results)


def _search_brave(transcript: str, emit: EmitFn) -> str:
    summary = transcript[:300].replace("\n", " ").strip()
    queries = _generate_search_queries(summary)
    all_results = []
    for q in queries[:3]:
        emit("progress", f"🔎  Searching (Brave): {q[:60]} …")
        try:
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": q, "count": 5},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("web", {}).get("results", []):
                all_results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                })
            time.sleep(0.5)
        except Exception as e:
            emit("progress", f"⚠️  Brave search error: {e}")

    return _format_search_results(all_results)


def _format_search_results(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["### Web search results for claim validation\n"]
    seen: set[str] = set()
    for r in results:
        url = r.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        lines.append(f"- **{r.get('title', '')}** — {r.get('description', '')}\n  {url}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 4 — LLM analysis
# ---------------------------------------------------------------------------

def _analyze(url: str, transcript: str, search_context: str, emit: EmitFn) -> str:
    system = build_system_prompt()
    user = build_analysis_prompt(url, transcript, search_context)

    if ANTHROPIC_API_KEY and not USE_CLAUDE_CLI:
        return _analyze_anthropic(system, user, emit)
    if USE_BEDROCK:
        return _analyze_bedrock(system, user, emit)
    if USE_CLAUDE_CLI:
        return _analyze_claude_cli(system, user, emit)
    raise RuntimeError(
        "No LLM configured. Set USE_BEDROCK=true in .env (AWS credentials from your active session), "
        "or set ANTHROPIC_API_KEY, or set USE_CLAUDE_CLI=true."
    )


def _analyze_bedrock(system: str, user: str, emit: EmitFn) -> str:
    import boto3, json as _json
    emit("progress", f"🤖  Calling Claude via AWS Bedrock ({BEDROCK_MODEL}) …")

    # Credentials come from .env (written by refresh.sh) or ambient AWS env/profile
    session_kwargs: dict = {"region_name": BEDROCK_REGION}
    aws_key    = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_token  = os.getenv("AWS_SESSION_TOKEN", "")
    if aws_key and aws_secret:
        session_kwargs["aws_access_key_id"]     = aws_key
        session_kwargs["aws_secret_access_key"] = aws_secret
        if aws_token:
            session_kwargs["aws_session_token"] = aws_token

    client = boto3.client("bedrock-runtime", **session_kwargs)
    body = _json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    })
    response = client.invoke_model(modelId=BEDROCK_MODEL, body=body)
    result = _json.loads(response["body"].read())
    return result["content"][0]["text"]


def _analyze_anthropic(system: str, user: str, emit: EmitFn) -> str:
    import anthropic
    emit("progress", "🤖  Calling Claude API …")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _analyze_claude_cli(system: str, user: str, emit: EmitFn) -> str:
    """Legacy path: run claude --print with a one-shot prompt for the bundled prompt template."""
    emit("progress", "🤖  Calling Claude CLI (PTY mode) …")
    prompt = f"{system}\n\n---\n\n{user}"
    out, _ = _run_claude_cli(prompt, emit, timeout=600)
    return out


# ---------------------------------------------------------------------------
# Connectivity / VPN-resilience helpers
# ---------------------------------------------------------------------------

def _check_connectivity() -> bool:
    """Best-effort check that the Claude gateway is reachable.

    Uses CONNECTIVITY_PROBE_URL (a cheap HEAD/GET) when configured; otherwise
    falls back to a short, self-watchdog'd ``claude --print`` ping that tests
    the real dependency. Returns True when reachable.
    """
    if CONNECTIVITY_PROBE_URL:
        try:
            requests.head(CONNECTIVITY_PROBE_URL, timeout=5, allow_redirects=True)
            return True
        except Exception:
            try:
                requests.get(CONNECTIVITY_PROBE_URL, timeout=5)
                return True
            except Exception:
                return False

    # Fallback: ping the real dependency. `claude --print ok` returns fast when
    # online and hangs when offline, so we kill it after a short watchdog.
    try:
        proc = subprocess.Popen(
            ["claude", "--print", "ok"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            return proc.returncode == 0
        time.sleep(0.5)
    proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    return False


def _wait_for_connectivity(emit: EmitFn, max_wait: int) -> bool:
    """Poll for connectivity up to *max_wait* seconds.

    Emits a periodic progress note so the results tab shows we're waiting, not
    stuck. Returns True as soon as connectivity returns, False if the bound is
    exceeded.
    """
    start = time.time()
    deadline = start + max_wait
    next_note = start + 30
    while time.time() < deadline:
        if _check_connectivity():
            return True
        now = time.time()
        if now >= next_note:
            elapsed_m = int((now - start) / 60)
            remaining_m = max(0, int((deadline - now) / 60))
            emit("progress",
                 f"⏳ Still waiting for the VPN to return "
                 f"({elapsed_m}m elapsed, ~{remaining_m}m left) …")
            next_note = now + 30
        time.sleep(RESUME_POLL_INTERVAL)
    return _check_connectivity()


def _run_claude_resilient(
    prompt: str,
    emit: EmitFn,
    *,
    heartbeats: list[tuple[int, str]] | None = None,
    timeout: int = 600,
    cwd: Path | None = None,
    raw_log_path: str | None = None,
) -> str:
    """Run the Claude analysis, surviving temporary VPN/connectivity drops.

    On a connectivity-class failure, waits (bounded by RESUME_MAX_WAIT) for the
    network to return, then resumes the same Claude session via ``--resume``
    (best-effort) or, if no session id was captured, re-runs from scratch.
    Genuine (non-network) failures propagate immediately.
    """
    # Capture the session id as soon as Claude emits it, so we can --resume even
    # when the *first* run is the one that drops mid-analysis.
    captured: dict[str, str | None] = {"sid": None}

    def _capture(sid: str) -> None:
        if not captured["sid"]:
            captured["sid"] = sid

    cur_prompt = prompt
    cur_resume: str | None = None
    attempt = 0

    while True:
        try:
            output, _ = _run_claude_cli(
                cur_prompt, emit,
                # Don't replay the time-based heartbeats on a resume run.
                heartbeats=heartbeats if cur_resume is None else None,
                timeout=timeout, cwd=cwd,
                resume_session=cur_resume,
                on_session_id=_capture,
                raw_log_path=raw_log_path,
            )
            return output
        except Exception as exc:
            # Probe connectivity to classify: a non-network failure while we're
            # online is a genuine error and should fail like before.
            online = _check_connectivity()
            if online and not isinstance(exc, _ConnectivityError):
                raise

            attempt += 1
            wait_m = max(1, RESUME_MAX_WAIT // 60)
            if attempt > RESUME_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Giving up after {RESUME_MAX_ATTEMPTS} reconnect attempt(s). "
                    f"Last error: {exc}"
                )
            emit("progress",
                 f"⚠️  Connection lost — waiting up to {wait_m} min for the VPN to "
                 f"return (attempt {attempt}/{RESUME_MAX_ATTEMPTS}). "
                 "The analysis will resume automatically.")
            if not _wait_for_connectivity(emit, RESUME_MAX_WAIT):
                raise RuntimeError(
                    f"VPN did not return within {wait_m} min — aborting analysis."
                )
            if captured["sid"]:
                emit("progress",
                     "🔄 Reconnected — resuming the Claude session where it left off …")
                cur_resume = captured["sid"]
                cur_prompt = (
                    "Continue the url-truth-analyzer analysis you were running and "
                    "return the full analysis markdown as your final response.\n\n"
                    + _ANALYSIS_MARKER_INSTRUCTION
                )
            else:
                emit("progress", "🔄 Reconnected — restarting the analysis …")
                cur_resume = None
                cur_prompt = prompt


def _run_claude_cli(
    prompt: str,
    emit: EmitFn,
    *,
    heartbeats: list[tuple[int, str]] | None = None,
    timeout: int = 600,
    cwd: Path | None = None,
    resume_session: str | None = None,
    on_session_id: Callable[[str], None] | None = None,
    raw_log_path: str | None = None,
) -> tuple[str, str | None]:
    """Run `claude --print --output-format=stream-json` via a PTY and return a
    ``(full_transcript, session_id)`` tuple. ``full_transcript`` is every
    assistant text turn concatenated in order; ``session_id`` is Claude's
    session id (parsed from the stream), used to ``--resume`` after a drop.

    When *resume_session* is set, the run continues that existing Claude
    session via ``--resume`` instead of starting fresh. *on_session_id* is
    invoked as soon as the session id is first seen in the stream — even if the
    run later fails — so a caller can resume the right session after a drop.

    Why stream-json instead of plain text: with the default text format, claude
    --print returns ONLY the final assistant message. The url-truth-analyzer
    skill emits the analysis several turns before its housekeeping/cleanup
    summary, so the final-turn-only mode dropped the analysis on the floor.
    Parsing stream-json lets us capture every text block from every assistant
    turn and stitch them together.

    The PTY is still required so the corporate Claude Code CLI can complete
    its OAuth handshake without writing to /dev/tty. *prompt* is fed on stdin.
    *heartbeats* is an optional list of (elapsed_seconds, message) pairs; each
    is emitted once when its threshold is crossed.
    """
    import pty, select, fcntl

    heartbeats = sorted(heartbeats or [], key=lambda hb: hb[0])
    next_hb = 0

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_path = f.name

    master_fd: int | None = None
    # Optional per-job raw stream-json sink. Appended across resume runs so a
    # `tail -f` shows Claude's full live activity (tool calls + every turn).
    raw_log_fh = None
    if raw_log_path:
        try:
            raw_log_fh = open(raw_log_path, "a", encoding="utf-8")
            raw_log_fh.write(json.dumps({
                "_meta": "claude-run-start",
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "resume": bool(resume_session),
            }) + "\n")
            raw_log_fh.flush()
        except Exception:
            raw_log_fh = None
    try:
        master_fd, slave_fd = pty.openpty()
        fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        cmd = [
            "claude", "--print", "--dangerously-skip-permissions",
            "--output-format=stream-json", "--verbose",
        ]
        if resume_session:
            cmd += ["--resume", resume_session]
        with open(prompt_path, "rb") as stdin_f:
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_f,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                cwd=str(cwd) if cwd else None,
            )
        os.close(slave_fd)

        # Line-buffered byte accumulator. stream-json emits one JSON object per
        # line; we parse on each newline and discard non-JSON noise (PTY tty
        # escape junk, occasional warnings).
        line_buf = bytearray()
        assistant_text_parts: list[str] = []
        result_text: str | None = None  # final "result" event's "result" field
        result_is_error = False
        result_error_msg: str | None = None
        session_id: str | None = None  # captured from the stream, for --resume
        raw_chunks: list[str] = []  # for diagnostics if no JSON ever parses

        def _handle_line(raw_line: bytes) -> None:
            nonlocal result_text, result_is_error, result_error_msg, session_id
            stripped = _strip_terminal_escapes(
                raw_line.decode("utf-8", errors="replace")
            ).strip()
            if not stripped or not stripped.startswith("{"):
                return
            try:
                evt = json.loads(stripped)
            except json.JSONDecodeError:
                return
            if raw_log_fh is not None:
                try:
                    raw_log_fh.write(stripped + "\n")
                    raw_log_fh.flush()
                except Exception:
                    pass
            # Firehose the rendered activity to the UI (behind a toggle there).
            if STREAM_CLAUDE_ACTIVITY:
                try:
                    for line in _render_claude_activity(evt):
                        emit("activity", line)
                except Exception:
                    pass
            # session_id appears on the init/system event and is echoed on most
            # subsequent events — capture it wherever it shows up first.
            sid = evt.get("session_id")
            if sid and session_id is None:
                session_id = sid
                if on_session_id is not None:
                    try:
                        on_session_id(sid)
                    except Exception:
                        pass
            etype = evt.get("type")
            if etype == "assistant":
                msg = evt.get("message") or {}
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text") or ""
                        if text:
                            assistant_text_parts.append(text)
            elif etype == "result":
                result_text = evt.get("result")
                result_is_error = bool(evt.get("is_error"))
                result_error_msg = evt.get("api_error_status") or None

        start = time.time()
        deadline = start + timeout
        last_rx = start  # wall-clock of the most recent byte from Claude
        eof = False
        while not eof and time.time() < deadline:
            elapsed = int(time.time() - start)
            while next_hb < len(heartbeats) and elapsed >= heartbeats[next_hb][0]:
                emit("progress", heartbeats[next_hb][1])
                next_hb += 1

            r, _, _ = select.select([master_fd], [], [], 5.0)
            if r:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    eof = True
                    data = b""
                if data:
                    last_rx = time.time()
                    raw_chunks.append(data.decode("utf-8", errors="replace"))
                    line_buf.extend(data)
                    while b"\n" in line_buf:
                        line, _, rest = line_buf.partition(b"\n")
                        line_buf[:] = rest
                        _handle_line(bytes(line))
                else:
                    eof = True
            elif proc.poll() is not None:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        raw_chunks.append(data.decode("utf-8", errors="replace"))
                        line_buf.extend(data)
                except OSError:
                    pass
                eof = True

            # Idle-stall guard: prolonged silence from Claude is either deep
            # thinking (fine) or a silent network/VPN stall. Probe connectivity
            # WITHOUT killing Claude; only abort if we're actually offline, so a
            # legitimately slow run is never cut short.
            if (not eof and CLAUDE_IDLE_TIMEOUT > 0
                    and (time.time() - last_rx) > CLAUDE_IDLE_TIMEOUT):
                if _check_connectivity():
                    last_rx = time.time()  # healthy, just slow — keep waiting
                else:
                    emit("progress",
                         "⚠️  No response from Claude and the network looks down — "
                         "pausing this analysis.")
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    raise _ConnectivityError(
                        "network unreachable during claude --print (idle stall)"
                    )

        # Drain any final partial line (rare — stream-json normally ends with \n).
        if line_buf:
            _handle_line(bytes(line_buf))

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

        if result_is_error:
            raise RuntimeError(
                f"claude --print reported error: {result_error_msg or 'unspecified'}"
            )

        # Prefer concatenated assistant turns (this is the skill's full output).
        # Fall back to the "result" field only if we didn't parse any assistant
        # text — which means the JSON stream was malformed or the run was a
        # single-turn refusal.
        full = "\n\n".join(p.strip() for p in assistant_text_parts if p.strip())
        if not full and result_text:
            full = result_text.strip()

        if not full:
            raw_preview = _strip_terminal_escapes("".join(raw_chunks))[:500]
            raise RuntimeError(
                f"claude CLI returned no parseable output (exit={proc.returncode}). "
                f"Raw head: {raw_preview!r}"
            )
        return full, session_id
    finally:
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        try:
            os.unlink(prompt_path)
        except OSError:
            pass
        if raw_log_fh is not None:
            try:
                raw_log_fh.close()
            except Exception:
                pass
