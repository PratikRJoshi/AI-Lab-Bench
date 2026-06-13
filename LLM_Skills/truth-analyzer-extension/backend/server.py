import json
import logging
import os
import queue
import threading
import time
import uuid
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

from analyzer import run_skill_analysis

app = Flask(__name__)
# Pick up template edits (e.g. results.html) on next request without a server
# restart. Restarting kills in-flight jobs (which live in this process's
# memory), so this is a real UX win during iteration.
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Maximum number of analyses that may be in flight at once. Each job spawns its
# own `claude --print` subprocess and runs the full skill pipeline (yt-dlp,
# Whisper, OCR), so 3 is a sane default for a developer laptop. Bump via env if
# you want more concurrency.
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

# In-memory store: id -> {"status", "events": list, "cond": Condition, "done": bool}
# Events are stored as {"event": str, "data": str} and never discarded.
# Any number of SSE subscribers can replay from position 0 at any time.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _make_job(job_id: str) -> dict:
    return {
        "id": job_id,
        "status": "queued",
        "events": [],
        "cond": threading.Condition(threading.Lock()),
        "done": False,
        "result": None,
        "error": None,
        "transcript": "",
    }


def _worker(job_id: str, url: str) -> None:
    job = _jobs[job_id]
    log = logging.getLogger(f"job.{job_id[:8]}")

    def emit(event: str, data: str) -> None:
        with job["cond"]:
            if event == "transcript":
                job["transcript"] = data  # store separately, don't stream to browser
                return
            job["events"].append({"event": event, "data": data})
            job["cond"].notify_all()
        if event == "progress":
            log.info(data)
        elif event == "error":
            log.error(data)

    try:
        log.info("▶  Starting analysis for %s", url)
        job["status"] = "running"
        result_md = run_skill_analysis(url, emit)
        job["result"] = result_md
        job["status"] = "done"
        log.info("✅ Analysis complete (%d chars)", len(result_md))
        emit("done", result_md)
    except Exception as exc:
        log.exception("❌ Analysis failed: %s", exc)
        job["error"] = str(exc)
        job["status"] = "error"
        # Include transcript in error payload if available, so UI can show it
        error_payload = {"message": str(exc), "transcript": job.get("transcript", "")}
        emit("error", json.dumps(error_payload))
    finally:
        with job["cond"]:
            job["done"] = True
            job["cond"].notify_all()


@app.post("/api/analyze")
def api_analyze():
    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    # Cap concurrent analyses. Each job is heavy (claude subprocess + yt-dlp +
    # Whisper); without a cap, a few impatient clicks can pin the whole machine.
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] in ("queued", "running")]
        if len(running) >= MAX_CONCURRENT_JOBS:
            return jsonify({
                "error": "limit_exceeded",
                "message": (
                    f"Already running {len(running)} of {MAX_CONCURRENT_JOBS} "
                    "allowed concurrent analyses. Wait for one to finish."
                ),
                "running": len(running),
                "limit": MAX_CONCURRENT_JOBS,
                "running_ids": [j["id"] for j in running],
            }), 429

        job_id = uuid.uuid4().hex
        _jobs[job_id] = _make_job(job_id)

    thread = threading.Thread(target=_worker, args=(job_id, url), daemon=True)
    thread.start()

    return jsonify({"id": job_id})


@app.get("/api/status/<job_id>")
def api_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return Response("event: error\ndata: unknown job id\n\n", status=404,
                        content_type="text/event-stream")

    def generate():
        cond = job["cond"]
        cursor = 0  # index into job["events"] — replay from start on reconnect
        while True:
            with cond:
                # Wait until there are new events or the job is done
                while cursor >= len(job["events"]) and not job["done"]:
                    notified = cond.wait(timeout=15)
                    if not notified:
                        # Timeout — emit keepalive comment and loop
                        yield ": keepalive\n\n"

                # Drain any new events
                while cursor < len(job["events"]):
                    item = job["events"][cursor]
                    cursor += 1
                    event = item["event"]
                    data = json.dumps(item["data"])
                    yield f"event: {event}\ndata: {data}\n\n"
                    if event in ("done", "error"):
                        return

                # If job finished and no more events, we're done
                if job["done"]:
                    return

    return Response(generate(), content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/results/<job_id>")
def results_page(job_id: str):
    # /tmp/truth-analyzer.log is where start.sh redirects nohup output. The
    # template uses this to render a copy-able tail command on the progress
    # panel. The user can override via env if they redirect logs elsewhere.
    log_path = os.getenv("LOG_PATH", "/tmp/truth-analyzer.log")
    return render_template("results.html", job_id=job_id, log_path=log_path)


@app.post("/api/save/<job_id>")
def api_save(job_id: str):
    import datetime, re
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or not job.get("result"):
        return jsonify({"error": "job not found or not complete"}), 404

    md = job["result"]
    date_str = datetime.date.today().isoformat()
    title_match = re.search(r"^# Truth Analysis:\s*(.+)", md, re.MULTILINE)
    title_raw = title_match.group(1).strip() if title_match else "analysis"
    slug = re.sub(r"[^a-z0-9]+", "-", title_raw.lower()).strip("-")[:60]
    filename = f"{date_str}-{slug}.md"

    save_dir = Path.home() / "Documents" / "truth-analyses"
    save_dir.mkdir(parents=True, exist_ok=True)
    dest = save_dir / filename
    dest.write_text(md, encoding="utf-8")

    # Also mirror into AI-Lab-Bench repo if it exists
    repo_dir = Path.home() / "AI-Lab-Bench" / "LLM_Skills" / "url-truth-analyzer" / "truth-analyses"
    if (Path.home() / "AI-Lab-Bench" / ".git").exists():
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / filename).write_text(md, encoding="utf-8")

    return jsonify({"path": str(dest)})


@app.post("/api/open")
def api_open():
    """Open a saved analysis file (or reveal in Finder) on the user's machine.

    Browsers block file:// navigation from an http:// page, so the front-end
    asks the server to do it via macOS `open`. The server only allows paths
    inside ~/Documents/truth-analyses/ or the repo's truth-analyses dir, so
    this can't be turned into an arbitrary-file open primitive.
    """
    import subprocess
    body = request.get_json(force=True, silent=True) or {}
    raw_path = (body.get("path") or "").strip()
    mode = body.get("mode") or "open"  # "open" | "reveal"
    if not raw_path:
        return jsonify({"error": "path is required"}), 400

    target = Path(raw_path).expanduser().resolve()
    allowed_roots = [
        (Path.home() / "Documents" / "truth-analyses").resolve(),
        (Path.home() / "AI-Lab-Bench" / "LLM_Skills" / "url-truth-analyzer" / "truth-analyses").resolve(),
    ]
    if not any(_is_within(target, root) for root in allowed_roots):
        return jsonify({"error": "path not in an allowed directory"}), 403
    if not target.exists():
        return jsonify({"error": "file does not exist"}), 404

    args = ["open", "-R", str(target)] if mode == "reveal" else ["open", str(target)]
    try:
        subprocess.run(args, check=True, timeout=5)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        return jsonify({"error": f"open failed: {e}"}), 500
    return jsonify({"ok": True})


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    with _jobs_lock:
        running = sum(1 for j in _jobs.values() if j["status"] in ("queued", "running"))
        total = len(_jobs)
    return jsonify({
        "ok": True,
        "running": running,
        "total": total,
        "limit": MAX_CONCURRENT_JOBS,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5757))
    print(f"Truth Analyzer backend running on http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
