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


def run_skill_analysis(url: str, emit: EmitFn) -> str:
    """Delegate URL analysis to the local Claude Code CLI's url-truth-analyzer skill.

    Builds a one-line prompt naming the skill, runs `claude --print`, and returns
    the final assistant markdown. The skill itself handles download, transcription,
    search, and analysis. Inline-URL invocation implies [display-only] in the
    skill, so no files are written and watch-urls.md is untouched.
    """
    clean_url = _strip_tracking(url)
    emit("progress", f"🔗 Cleaned URL: {clean_url}")
    emit("progress", "🤖 Handing off to local Claude Code (url-truth-analyzer skill) …")

    prompt = (
        f"Use the url-truth-analyzer skill to analyze this URL: {clean_url}\n\n"
        "Return the full analysis markdown as your final response."
    )

    heartbeats = [
        (15,  "📥 Skill is downloading content (yt-dlp / article fetch / OCR) …"),
        (60,  "📝 Transcribing or extracting text …"),
        (150, "🌐 Searching for supporting / refuting evidence …"),
        (240, "🧠 Analyzing claims — almost there …"),
        (360, "⏳ Still working (long videos can take 5+ minutes) …"),
    ]

    output = _run_claude_cli(
        prompt, emit, heartbeats=heartbeats, timeout=900, cwd=_REPO_ROOT
    )
    if not output.strip():
        raise RuntimeError(
            "claude --print returned empty output. Check that the url-truth-analyzer "
            "skill is available (`claude` interactively → /skills) and that you are logged in."
        )
    return output


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
    return _run_claude_cli(prompt, emit, timeout=600)


def _run_claude_cli(
    prompt: str,
    emit: EmitFn,
    *,
    heartbeats: list[tuple[int, str]] | None = None,
    timeout: int = 600,
    cwd: Path | None = None,
) -> str:
    """Run `claude --print --dangerously-skip-permissions` via a PTY and return stdout.

    The PTY is required so the corporate Claude Code CLI can complete its OAuth
    handshake without trying to write to /dev/tty. *prompt* is fed on stdin.
    *heartbeats* is an optional list of (elapsed_seconds, message) pairs; each
    is emitted once when its threshold is crossed, giving the browser visible
    progress while the skill runs (since claude --print only emits on completion).
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
    try:
        master_fd, slave_fd = pty.openpty()
        fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        with open(prompt_path, "rb") as stdin_f:
            proc = subprocess.Popen(
                ["claude", "--print", "--dangerously-skip-permissions"],
                stdin=stdin_f,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                cwd=str(cwd) if cwd else None,
            )
        os.close(slave_fd)

        chunks: list[str] = []
        start = time.time()
        deadline = start + timeout
        while time.time() < deadline:
            elapsed = int(time.time() - start)
            while next_hb < len(heartbeats) and elapsed >= heartbeats[next_hb][0]:
                emit("progress", heartbeats[next_hb][1])
                next_hb += 1

            r, _, _ = select.select([master_fd], [], [], 5.0)
            if r:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        chunks.append(data.decode("utf-8", errors="replace"))
                except OSError:
                    break
            elif proc.poll() is not None:
                break

        proc.wait(timeout=10)
        output = _strip_terminal_escapes("".join(chunks)).strip()
        if proc.returncode != 0 and not output:
            raise RuntimeError(
                f"claude CLI exited with code {proc.returncode}. "
                "Make sure you are logged in: run `claude` in a terminal first."
            )
        return output
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
