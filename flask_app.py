import json
import os
import tempfile
import uuid
import hashlib
import time

from flask import Flask, Response, jsonify, request, stream_with_context, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import redis
from rq import Queue

from app_data import FULL_GRADES, GRADES
from models import AnalysisOptions
from run_analysis import run_analysis_engine

app = Flask(__name__, static_folder="html")
CORS(app, resources={r"/api/*": {"origins": "*"}})

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


def get_redis():
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    if os.environ.get("REDIS_TLS") == "1":
        return redis.from_url(url, ssl_cert_reqs=None)
    return redis.from_url(url)


def get_queue():
    return Queue("default", connection=get_redis())


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


def estimate_timeout(file_size_bytes: int | None) -> int:
    if not file_size_bytes or file_size_bytes <= 0:
        return JOB_TIMEOUT_BASE
    size_mb = file_size_bytes / (1024 * 1024)
    timeout = JOB_TIMEOUT_BASE + size_mb * JOB_TIMEOUT_PER_MB
    timeout = max(JOB_TIMEOUT_MIN, timeout)
    timeout = min(JOB_TIMEOUT_MAX, timeout)
    return int(timeout)


def get_queue_size(q) -> int:
    count = getattr(q, "count", None)
    if count is None:
        return 0
    if callable(count):
        return int(count())
    return int(count)


def ensure_score_path(payload, r):
    score_path = payload.get("score_path")
    file_key = payload.get("score_file_key")
    if not score_path and file_key:
        raw = r.get(file_key)
        if raw:
            ext = payload.get("score_ext", ".musicxml")
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=ext, dir=UPLOAD_DIR
            )
            tmp.write(raw)
            tmp.flush()
            tmp.close()
            score_path = tmp.name
    return score_path


@app.get("/")
def index():
    return send_from_directory("html", "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory("html", filename)


def _run_job(job_id, payload):
    r = get_redis()
    events_key = f"job:{job_id}:events"
    result_key = f"job:{job_id}:result"
    error_key = f"job:{job_id}:error"
    done_key = f"job:{job_id}:done"

    def progress_cb(event):
        r.rpush(events_key, json.dumps(make_json_safe(event)))
        r.expire(events_key, JOB_TTL_SECONDS)

    try:
        target_only = parse_bool(payload.get("target_only"))
        strings_only = parse_bool(payload.get("strings_only"))
        full_grade = parse_bool(payload.get("full_grade_analysis"))
        target_grade = float(payload.get("target_grade", 2))
        observed_grades = None

        if target_only is False:
            observed_grades = FULL_GRADES if full_grade else GRADES
        options = AnalysisOptions(
            run_observed=not target_only,
            string_only=strings_only,
            observed_grades=observed_grades,
        )

        score_path = ensure_score_path(payload, r)

        if not score_path:
            raise RuntimeError("Missing score file for analysis.")

        timeout_seconds = payload.get("timeout_seconds")
        deadline = (
            time.monotonic() + float(timeout_seconds)
            if timeout_seconds
            else None
        )
        result = run_analysis_engine(
            score_path,
            target_grade,
            analysis_options=options,
            progress_cb=progress_cb,
            deadline=deadline,
        )
        safe_result = make_json_safe(result)
        r.rpush(events_key, json.dumps({"type": "result", "data": safe_result}))
        r.expire(events_key, JOB_TTL_SECONDS)
        if parse_bool(payload.get("store_result", True)):
            r.set(result_key, json.dumps(safe_result))
            r.expire(result_key, JOB_TTL_SECONDS)
    except Exception as exc:
        r.set(error_key, str(exc))
        r.expire(error_key, JOB_TTL_SECONDS)
    finally:
        r.set(done_key, "1")
        r.expire(done_key, JOB_TTL_SECONDS)
        r.rpush(events_key, json.dumps({"type": "done"}))
        r.expire(events_key, JOB_TTL_SECONDS)


def _handle_analyze(*, force_inline: bool = False):
    payload = {}
    pending_upload = None
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        form = request.form
        uploaded = request.files.get("score_file")
        if uploaded:
            filename = secure_filename(uploaded.filename or "score.musicxml")
            ext = os.path.splitext(filename)[1] or ".musicxml"
            data = uploaded.read()
            if len(data) > MAX_UPLOAD_BYTES:
                return jsonify({"error": "Score too large"}), 413
            pending_upload = {
                "data": data,
                "ext": ext,
                "file_size": len(data),
            }
        payload["target_only"] = form.get("target_only") == "true"
        payload["strings_only"] = form.get("strings_only") == "true"
        payload["full_grade_analysis"] = form.get("full_grade_analysis") == "true"
        if form.get("debug_inline") is not None:
            payload["debug_inline"] = form.get("debug_inline")
        if form.get("target_grade"):
            payload["target_grade"] = float(form.get("target_grade"))
    else:
        payload = request.get_json(force=True, silent=True) or {}

    if not payload.get("score_file_key") and not payload.get("score_path") and not pending_upload:
        return jsonify({"error": "Missing score or target grade."}), 400
    if "target_grade" not in payload:
        return jsonify({"error": "Missing score or target grade."}), 400
    if pending_upload:
        payload["file_size"] = pending_upload["file_size"]
    if payload.get("score_path") and not payload.get("file_size"):
        try:
            payload["file_size"] = os.path.getsize(payload["score_path"])
        except OSError:
            payload["file_size"] = None
    if payload.get("file_size") and payload["file_size"] > MAX_UPLOAD_BYTES:
        return jsonify({"error": "Score too large"}), 413

    timeout_seconds = estimate_timeout(payload.get("file_size"))
    payload["timeout_seconds"] = timeout_seconds

    inline_requested = (
        force_inline
        or parse_bool(request.args.get("debug_inline"))
        or parse_bool(payload.get("debug_inline"))
        or os.environ.get("ANALYZE_INLINE") == "1"
    )
    host = request.host or ""
    is_local_request = host.startswith("127.0.0.1") or host.startswith("localhost")
    inline_allowed = inline_requested and (
        app.debug or os.environ.get("ALLOW_INLINE_ANALYSIS") == "1" or is_local_request
    )

    if inline_allowed:
        if pending_upload and not payload.get("score_path"):
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=pending_upload["ext"], dir=UPLOAD_DIR
            )
            tmp.write(pending_upload["data"])
            tmp.flush()
            tmp.close()
            payload["score_path"] = tmp.name
        r = None
        score_path = ensure_score_path(payload, r) if r else payload.get("score_path")
        if not score_path:
            return jsonify({"error": "Missing score file for analysis."}), 400
        target_only = parse_bool(payload.get("target_only"))
        strings_only = parse_bool(payload.get("strings_only"))
        full_grade = parse_bool(payload.get("full_grade_analysis"))
        target_grade = float(payload.get("target_grade", 2))
        observed_grades = None
        if target_only is False:
            observed_grades = FULL_GRADES if full_grade else GRADES
        options = AnalysisOptions(
            run_observed=not target_only,
            string_only=strings_only,
            observed_grades=observed_grades,
        )
        deadline = time.monotonic() + float(timeout_seconds)
        result = run_analysis_engine(
            score_path,
            target_grade,
            analysis_options=options,
            progress_cb=None,
            deadline=deadline,
        )
        return jsonify(make_json_safe(result))

    if pending_upload and not payload.get("score_file_key"):
        try:
            digest = hashlib.sha256(pending_upload["data"]).hexdigest()
            file_key = f"score:{digest}{pending_upload['ext']}"
            r = get_redis()
            r.set(file_key, pending_upload["data"], ex=JOB_TTL_SECONDS)
            payload["score_file_key"] = file_key
            payload["score_ext"] = pending_upload["ext"]
        except Exception:
            return (
                jsonify({"error": "Redis unavailable. Start Redis or use inline analysis."}),
                503,
            )

    job_id = str(uuid.uuid4())
    q = get_queue()
    if MAX_QUEUE_SIZE and get_queue_size(q) >= MAX_QUEUE_SIZE:
        return jsonify({"error": "Analysis queue full. Try again shortly."}), 429
    q.enqueue(
        _run_job,
        job_id,
        payload,
        job_id=job_id,
        job_timeout=int(timeout_seconds),
    )

    return jsonify({"job_id": job_id})


@app.post("/api/analyze")
def analyze():
    return _handle_analyze()


@app.post("/api/analyze_sync")
def analyze_sync():
    return _handle_analyze(force_inline=True)


@app.get("/api/progress/<job_id>")
def progress(job_id):
    r = get_redis()
    events_key = f"job:{job_id}:events"
    done_key = f"job:{job_id}:done"
    if not r.exists(events_key) and not r.exists(done_key):
        return jsonify({"error": "Unknown job"}), 404

    def generate():
        last_heartbeat = time.time()
        while True:
            item = r.blpop(events_key, timeout=1)
            if item:
                _, raw = item
                try:
                    event = json.loads(raw)
                except Exception:
                    event = {"type": "message", "raw": raw.decode("utf-8", "ignore")}
                yield f"data: {json.dumps(event)}\n\n"
                last_heartbeat = time.time()
                if event.get("type") == "done":
                    break
            else:
                if r.exists(done_key):
                    break
                now = time.time()
                if now - last_heartbeat >= 10:
                    last_heartbeat = now
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.get("/api/result/<job_id>")
def result(job_id):
    r = get_redis()
    result_key = f"job:{job_id}:result"
    error_key = f"job:{job_id}:error"
    done_key = f"job:{job_id}:done"
    if not r.exists(done_key) and not r.exists(result_key) and not r.exists(error_key):
        return jsonify({"error": "Unknown job"}), 404
    payload = {
        "done": bool(r.exists(done_key)),
        "error": r.get(error_key).decode("utf-8") if r.exists(error_key) else None,
        "result": json.loads(r.get(result_key)) if r.exists(result_key) else None,
    }
    return jsonify(make_json_safe(payload))


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
