import json
import os
import queue
import threading
import tempfile
import uuid
import hashlib
import time

from flask import Flask, Response, jsonify, request, stream_with_context, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from app_data import FULL_GRADES, GRADES
from models import AnalysisOptions
from run_analysis import run_analysis_engine

app = Flask(__name__, static_folder="html")
CORS(app, resources={r"/api/*": {"origins": "*"}})

JOBS = {}
UPLOAD_DIR = tempfile.mkdtemp(prefix="score_uploads_")
JOB_TTL_SECONDS = 60 * 60 * 6


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


MAX_UPLOAD_BYTES = _env_int("MAX_UPLOAD_BYTES", 50_000_000)
MAX_QUEUE_SIZE = _env_int("MAX_QUEUE_SIZE", 8)
JOB_TIMEOUT_BASE = _env_int("JOB_TIMEOUT_BASE", 120)
JOB_TIMEOUT_PER_MB = _env_float("JOB_TIMEOUT_PER_MB", 8.0)
JOB_TIMEOUT_MIN = _env_int("JOB_TIMEOUT_MIN", 60)
JOB_TIMEOUT_MAX = _env_int("JOB_TIMEOUT_MAX", 900)


def estimate_timeout(file_size_bytes: int | None) -> int:
    if not file_size_bytes or file_size_bytes <= 0:
        return JOB_TIMEOUT_BASE
    size_mb = file_size_bytes / (1024 * 1024)
    timeout = JOB_TIMEOUT_BASE + size_mb * JOB_TIMEOUT_PER_MB
    timeout = max(JOB_TIMEOUT_MIN, timeout)
    timeout = min(JOB_TIMEOUT_MAX, timeout)
    return int(timeout)


def _active_job_count() -> int:
    return sum(1 for job in JOBS.values() if not job.get("done"))


def _cleanup_jobs():
    now = time.time()
    expired = [
        job_id
        for job_id, job in JOBS.items()
        if job.get("done_at") and now - job["done_at"] > JOB_TTL_SECONDS
    ]
    for job_id in expired:
        JOBS.pop(job_id, None)


def make_json_safe(value):
    if isinstance(value, dict):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return make_json_safe(vars(value))
    return str(value)


def parse_bool(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@app.get("/")
def index():
    return send_from_directory("html", "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory("html", filename)


def _run_job(job_id, payload):
    job = JOBS[job_id]
    q = job["queue"]

    def progress_cb(event):
        q.put(event)

    try:
        target_only = parse_bool(payload.get("target_only"))
        strings_only = parse_bool(payload.get("strings_only"))
        full_grade = parse_bool(payload.get("full_grade_analysis"))
        score_path = payload.get("score_path")
        target_grade = float(payload.get("target_grade", 2))
        timeout_seconds = payload.get("timeout_seconds")
        deadline = (
            time.monotonic() + float(timeout_seconds)
            if timeout_seconds
            else None
        )
        observed_grades = None

        if target_only is False:
            observed_grades = FULL_GRADES if full_grade else GRADES
        options = AnalysisOptions(
            run_observed=not target_only,
            string_only=strings_only,
            observed_grades=observed_grades,
        )

        result = run_analysis_engine(
            score_path,
            target_grade,
            analysis_options=options,
            progress_cb=progress_cb,
            deadline=deadline,
        )
        job["result"] = result
    except Exception as exc:
        job["error"] = str(exc)
    finally:
        job["done"] = True
        job["done_at"] = time.time()
        q.put({"type": "done"})


@app.post("/api/analyze")
def analyze():
    _cleanup_jobs()
    payload = {}
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        form = request.form
        uploaded = request.files.get("score_file")
        if uploaded:
            filename = secure_filename(uploaded.filename or "score.musicxml")
            ext = os.path.splitext(filename)[1] or ".musicxml"
            data = uploaded.read()
            if len(data) > MAX_UPLOAD_BYTES:
                return jsonify({"error": "Score too large"}), 413
            digest = hashlib.sha256(data).hexdigest()
            file_id = f"{digest}{ext}"
            save_path = os.path.join(UPLOAD_DIR, file_id)
            if not os.path.exists(save_path):
                with open(save_path, "wb") as f:
                    f.write(data)
            payload["score_path"] = save_path
            payload["file_size"] = len(data)
        payload["target_only"] = form.get("target_only") == "true"
        payload["strings_only"] = form.get("strings_only") == "true"
        payload["full_grade_analysis"] = form.get("full_grade_analysis") == "true"
        if form.get("target_grade"):
            payload["target_grade"] = float(form.get("target_grade"))
    else:
        payload = request.get_json(force=True, silent=True) or {}

    if not payload.get("score_path") or "target_grade" not in payload:
        return jsonify({"error": "Missing score or target grade."}), 400
    if payload.get("score_path") and not payload.get("file_size"):
        try:
            payload["file_size"] = os.path.getsize(payload["score_path"])
        except OSError:
            payload["file_size"] = None
    if payload.get("file_size") and payload["file_size"] > MAX_UPLOAD_BYTES:
        return jsonify({"error": "Score too large"}), 413

    if MAX_QUEUE_SIZE and _active_job_count() >= MAX_QUEUE_SIZE:
        return jsonify({"error": "Analysis queue full. Try again shortly."}), 429

    timeout_seconds = estimate_timeout(payload.get("file_size"))
    payload["timeout_seconds"] = timeout_seconds

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "queue": queue.Queue(),
        "result": None,
        "error": None,
        "done": False,
        "created_at": time.time(),
        "done_at": None,
    }

    thread = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.get("/api/progress/<job_id>")
def progress(job_id):
    _cleanup_jobs()
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    q = job["queue"]

    def generate():
        last_heartbeat = time.time()
        while True:
            try:
                event = q.get(timeout=0.5)
            except queue.Empty:
                if job.get("done"):
                    break
                now = time.time()
                if now - last_heartbeat >= 10:
                    last_heartbeat = now
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            last_heartbeat = time.time()
            if event.get("type") == "done":
                break

    resp = Response(stream_with_context(generate()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@app.get("/api/result/<job_id>")
def result(job_id):
    _cleanup_jobs()
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    payload = {
        "done": job["done"],
        "error": job["error"],
        "result": job["result"],
    }
    return jsonify(make_json_safe(payload))


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
