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
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

from analyzer import run_analysis

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

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
        result_md = run_analysis(url, emit)
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

    # Only allow one analysis at a time — reject if one is already running
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
        if running:
            busy_id = running[0]["id"]
            return jsonify({
                "error": "busy",
                "message": "An analysis is already in progress. Wait for it to finish or open the existing result.",
                "existing_id": busy_id,
            }), 409

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
    return render_template("results.html", job_id=job_id)


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


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5757))
    print(f"Truth Analyzer backend running on http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
