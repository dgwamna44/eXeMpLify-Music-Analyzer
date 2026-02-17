import json
import os
import queue
import threading
import tempfile
import uuid
import hashlib

from flask import Flask, Response, jsonify, request, stream_with_context, send_from_directory
from werkzeug.utils import secure_filename

from app_data import FULL_GRADES, GRADES
from models import AnalysisOptions
from run_analysis import run_analysis_engine

app = Flask(__name__, static_folder="html")

JOBS = {}
UPLOAD_DIR = tempfile.mkdtemp(prefix="score_uploads_")


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
        )
        job["result"] = result
    except Exception as exc:
        job["error"] = str(exc)
    finally:
        job["done"] = True
        q.put({"type": "done"})


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
            file_id = f"{digest}{ext}"
            save_path = os.path.join(UPLOAD_DIR, file_id)
            if not os.path.exists(save_path):
                with open(save_path, "wb") as f:
                    f.write(data)
            payload["score_path"] = save_path
        payload["target_only"] = form.get("target_only") == "true"
        payload["strings_only"] = form.get("strings_only") == "true"
        payload["full_grade_analysis"] = form.get("full_grade_analysis") == "true"
        if form.get("target_grade"):
            payload["target_grade"] = float(form.get("target_grade"))
    else:
        payload = request.get_json(force=True, silent=True) or {}

    if not payload.get("score_path") or "target_grade" not in payload:
        return jsonify({"error": "Missing score or target grade."}), 400

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"queue": queue.Queue(), "result": None, "error": None, "done": False}

    thread = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.get("/api/progress/<job_id>")
def progress(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    q = job["queue"]

    def generate():
        while True:
            try:
                event = q.get(timeout=0.5)
            except queue.Empty:
                if job.get("done"):
                    break
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "done":
                break

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.get("/api/result/<job_id>")
def result(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    payload = {
        "done": job["done"],
        "error": job["error"],
        "result": job["result"],
    }
    return jsonify(make_json_safe(payload))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
