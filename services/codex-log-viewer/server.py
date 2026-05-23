"""
Codex Proxy Log Viewer — lightweight Flask app that reads Nginx JSON access log
and serves a dashboard at /codex/log/

Runs on port 8089, proxied by Nginx at /codex/log/
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

LOG_PATH = Path(os.getenv("CODEX_LOG_PATH", "/var/log/nginx/codex.access.log"))
STATIC_DIR = Path(__file__).parent / "static"
PASSWORD = os.getenv("LOG_VIEWER_PASSWORD", "pwd")

app = Flask(__name__, static_folder=str(STATIC_DIR))


def parse_model_from_body(body: str) -> str:
    """Extract model name from request body JSON."""
    if not body or body == "-":
        return "-"
    try:
        # Body might be truncated; try parsing as JSON
        data = json.loads(body)
        return data.get("model", "-")
    except (json.JSONDecodeError, TypeError):
        # Fallback: regex
        m = re.search(r'"model"\s*:\s*"([^"]+)"', body)
        return m.group(1) if m else "-"


def read_log_lines(n: int = 200) -> list[dict]:
    """Read last N lines from the codex access log."""
    if not LOG_PATH.exists():
        return []

    # Use tail for efficiency
    try:
        result = subprocess.run(
            ["tail", "-n", str(n), str(LOG_PATH)],
            capture_output=True, text=True, timeout=5
        )
        raw_lines = result.stdout.strip().split("\n")
    except Exception:
        raw_lines = LOG_PATH.read_text().strip().split("\n")[-n:]

    entries = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            # Extract model from request body
            entry["model"] = parse_model_from_body(entry.get("request_body", ""))
            # Clean up large fields
            entry.pop("request_body", None)
            entries.append(entry)
        except json.JSONDecodeError:
            continue

    return entries


@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/logs")
def api_logs():
    auth = request.headers.get("Authorization", "")
    token = request.args.get("token", "")
    if auth != f"Bearer {PASSWORD}" and token != PASSWORD:
        return jsonify({"error": "unauthorized"}), 401

    n = min(int(request.args.get("n", 200)), 2000)
    entries = read_log_lines(n)
    return jsonify(entries)


@app.route("/api/stats")
def api_stats():
    auth = request.headers.get("Authorization", "")
    token = request.args.get("token", "")
    if auth != f"Bearer {PASSWORD}" and token != PASSWORD:
        return jsonify({"error": "unauthorized"}), 401

    entries = read_log_lines(2000)
    total = len(entries)
    models: dict[str, int] = {}
    statuses: dict[str, int] = {}
    total_time = 0.0
    for e in entries:
        m = e.get("model", "-")
        models[m] = models.get(m, 0) + 1
        s = str(e.get("status", "-"))
        statuses[s] = statuses.get(s, 0) + 1
        try:
            total_time += float(e.get("request_time", 0))
        except (ValueError, TypeError):
            pass

    return jsonify({
        "total_requests": total,
        "models": models,
        "statuses": statuses,
        "avg_response_time": round(total_time / total, 2) if total else 0,
    })


if __name__ == "__main__":
    print(f"[codex-log-viewer] serving on http://127.0.0.1:8089", flush=True)
    print(f"[codex-log-viewer] reading log from {LOG_PATH}", flush=True)
    app.run(host="127.0.0.1", port=8089, debug=False, threaded=True)
