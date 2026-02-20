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


def get_redis():
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
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
        r.rpush(events_key, json.dumps(event))
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

        if not score_path:
            raise RuntimeError("Missing score file for analysis.")

        result = run_analysis_engine(
            score_path,
            target_grade,
            analysis_options=options,
            progress_cb=progress_cb,
        )
        r.set(result_key, json.dumps(make_json_safe(result)))
        r.expire(result_key, JOB_TTL_SECONDS)
    except Exception as exc:
        r.set(error_key, str(exc))
        r.expire(error_key, JOB_TTL_SECONDS)
    finally:
        r.set(done_key, "1")
        r.expire(done_key, JOB_TTL_SECONDS)
        r.rpush(events_key, json.dumps({"type": "done"}))
        r.expire(events_key, JOB_TTL_SECONDS)


@app.post("/api/analyze")
def analyze():
    payload = {}
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        form = request.form
        uploaded = request.files.get("score_file")
        if uploaded:
            filename = secure_filename(uploaded.filename or "score.musicxml")
            ext = os.path.splitext(filename)[1] or ".musicxml"
            data = uploaded.read()
            digest = hashlib.sha256(data).hexdigest()
            file_key = f"score:{digest}{ext}"
            r = get_redis()
            r.set(file_key, data, ex=JOB_TTL_SECONDS)
            payload["score_file_key"] = file_key
            payload["score_ext"] = ext
        payload["target_only"] = form.get("target_only") == "true"
        payload["strings_only"] = form.get("strings_only") == "true"
        payload["full_grade_analysis"] = form.get("full_grade_analysis") == "true"
        if form.get("target_grade"):
            payload["target_grade"] = float(form.get("target_grade"))
    else:
        payload = request.get_json(force=True, silent=True) or {}

    if not payload.get("score_file_key") and not payload.get("score_path"):
        return jsonify({"error": "Missing score or target grade."}), 400
    if "target_grade" not in payload:
        return jsonify({"error": "Missing score or target grade."}), 400

    job_id = str(uuid.uuid4())
    q = get_queue()
    q.enqueue(_run_job, job_id, payload, job_id=job_id)

    return jsonify({"job_id": job_id})


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
