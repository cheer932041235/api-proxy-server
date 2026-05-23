"""
Codex Log Sync — tails codex-proxy Docker logs, extracts usage info,
and inserts records into New-API's SQLite database.

Parses two log patterns:
  [Responses] Account ... | model=gpt-5.5 | rid=xxx ... 
  [Responses] ... | rid=xxx | Usage: in=42659 (cached=42496 uncached=163) out=3 | hit=99.6%
  [Chat] Account ... | model=gpt-5.5 | rid=xxx ...
  [Chat] ... | rid=xxx | Usage: in=17 out=10 | hit=0.0%

And the structured JSON lines:
  {"ts":"...","level":"info","msg":"← POST /v1/responses 200 937ms","rid":"xxx",...}

Combines these by request ID to produce a complete log entry with:
  model, prompt_tokens, completion_tokens, cached_tokens, use_time, status, path
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

DB_PATH = os.getenv("NEWAPI_DB", "/root/new-api-data/one-api.db")
CONTAINER = os.getenv("CODEX_CONTAINER", "codex-proxy-codex-proxy-1")
# New-API internal config
NEWAPI_USER_ID = int(os.getenv("NEWAPI_USER_ID", "1"))
NEWAPI_USERNAME = os.getenv("NEWAPI_USERNAME", "root")
NEWAPI_TOKEN_NAME = os.getenv("NEWAPI_TOKEN_NAME", "codex-proxy")
NEWAPI_TOKEN_ID = int(os.getenv("NEWAPI_TOKEN_ID", "0"))
NEWAPI_CHANNEL_ID = int(os.getenv("NEWAPI_CHANNEL_ID", "99"))
NEWAPI_CHANNEL_NAME = os.getenv("NEWAPI_CHANNEL_NAME", "codex-proxy")
NEWAPI_GROUP = os.getenv("NEWAPI_GROUP", "default")
LOG_TYPE = 2  # consumption

# Model pricing (quota per 1K tokens, in New-API's internal units)
# These match New-API's default OpenAI pricing
MODEL_INPUT_RATIO = {
    "gpt-5.5": 1.5,
    "gpt-5.4": 1.0,
    "gpt-5.4-mini": 0.4,
    "gpt-5.3-codex": 0.8,
    "gpt-5.2": 0.5,
    "gpt-5-codex": 0.3,
}
COMPLETION_RATIO = 6  # output tokens cost 6x input

# 500000 quota = $1 in New-API
DOLLAR_TO_QUOTA = 500000


@dataclass
class RequestInfo:
    rid: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    use_time_ms: int = 0
    status: int = 0
    path: str = ""
    is_stream: bool = False
    timestamp: float = 0.0
    api_type: str = ""  # "Responses" or "Chat"
    account: str = ""
    complete: bool = False


def calc_quota(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int) -> int:
    """Calculate New-API quota based on model and token usage."""
    ratio = MODEL_INPUT_RATIO.get(model, 1.0)
    # Cached tokens cost 50% of normal input
    uncached = prompt_tokens - cached_tokens
    input_cost = (uncached * ratio + cached_tokens * ratio * 0.5) / 1000
    output_cost = completion_tokens * ratio * COMPLETION_RATIO / 1000
    # Convert to dollars then to quota
    total_dollars = (input_cost + output_cost) * 0.003  # $3/1M input tokens base
    return int(total_dollars * DOLLAR_TO_QUOTA)


def insert_log(db: sqlite3.Connection, info: RequestInfo):
    """Insert a log record into New-API's logs table."""
    created_at = int(info.timestamp) if info.timestamp else int(time.time())
    quota = calc_quota(info.model, info.prompt_tokens, info.completion_tokens, info.cached_tokens)
    use_time_s = max(1, info.use_time_ms // 1000)

    # Build other JSON
    other = json.dumps({
        "admin_info": {"use_channel": [str(NEWAPI_CHANNEL_ID)]},
        "billing_source": "codex-proxy",
        "cache_ratio": 0.5,
        "cache_tokens": info.cached_tokens,
        "completion_ratio": COMPLETION_RATIO,
        "group_ratio": 1,
        "model_ratio": MODEL_INPUT_RATIO.get(info.model, 1.0),
        "request_path": info.path,
        "api_type": info.api_type,
        "account": info.account,
    })

    db.execute("""
        INSERT INTO logs (
            user_id, created_at, type, content, username, token_name, model_name,
            quota, prompt_tokens, completion_tokens, use_time, is_stream,
            channel_id, channel_name, token_id, "group", ip, request_id, other
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        NEWAPI_USER_ID, created_at, LOG_TYPE, "", NEWAPI_USERNAME,
        NEWAPI_TOKEN_NAME, info.model, quota,
        info.prompt_tokens, info.completion_tokens, use_time_s,
        1 if info.is_stream else 0,
        NEWAPI_CHANNEL_ID, NEWAPI_CHANNEL_NAME, NEWAPI_TOKEN_ID,
        NEWAPI_GROUP, "", info.rid, other
    ))
    db.commit()
    print(f"[sync] Inserted: rid={info.rid} model={info.model} "
          f"in={info.prompt_tokens} out={info.completion_tokens} "
          f"cached={info.cached_tokens} time={use_time_s}s quota={quota}",
          flush=True)


# Regex patterns for codex-proxy log lines
RE_REQUEST_START = re.compile(
    r'\[(Responses|Chat)\] Account (\S+) \| model=(\S+) \| rid=(\S+)'
)
RE_USAGE = re.compile(
    r'\[(Responses|Chat)\] .+\| rid=(\S+) \| Usage: in=(\d+)(?:\s*\(cached=(\d+)\s+uncached=(\d+)\))?\s+out=(\d+)'
)
RE_RESPONSE_LINE = re.compile(
    r'\{"ts":"([^"]+)".*"msg":"← (POST|GET) (\S+) (\d+) (\d+)ms".*"rid":"([^"]+)"'
)


def tail_docker_logs():
    """Tail codex-proxy Docker logs and yield parsed RequestInfo when complete."""
    pending: dict[str, RequestInfo] = {}

    proc = subprocess.Popen(
        ["docker", "logs", "-f", "--tail", "0", CONTAINER],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )

    print(f"[sync] Tailing {CONTAINER} logs...", flush=True)

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        # Check for request start (model info)
        m = RE_REQUEST_START.search(line)
        if m:
            api_type, account, model, rid = m.groups()
            if rid not in pending:
                pending[rid] = RequestInfo(rid=rid)
            pending[rid].api_type = api_type
            pending[rid].account = account
            pending[rid].model = model
            continue

        # Check for usage info
        m = RE_USAGE.search(line)
        if m:
            api_type, rid, in_tok, cached, uncached, out_tok = m.groups()
            if rid not in pending:
                pending[rid] = RequestInfo(rid=rid)
            pending[rid].prompt_tokens = int(in_tok)
            pending[rid].completion_tokens = int(out_tok)
            pending[rid].cached_tokens = int(cached) if cached else 0

            # For Responses API: usage arrives AFTER the response line,
            # so check if we already have response info and can yield now
            info = pending[rid]
            if info.status == 200 and info.model and info.prompt_tokens > 0:
                info.complete = True
                yield info
                del pending[rid]
            continue

        # Check for response completion (JSON structured line)
        m = RE_RESPONSE_LINE.search(line)
        if m:
            ts, method, path, status, ms, rid = m.groups()
            if rid not in pending:
                pending[rid] = RequestInfo(rid=rid)
            info = pending[rid]
            info.path = path
            info.status = int(status)
            info.use_time_ms = int(ms)
            info.is_stream = "stream" in path  # heuristic
            try:
                info.timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                info.timestamp = time.time()

            # For Chat API: usage arrives BEFORE the response line,
            # so we can yield immediately if we have everything
            if info.model and info.prompt_tokens > 0 and int(status) == 200:
                info.complete = True
                yield info
                del pending[rid]
            elif int(status) != 200:
                # Error request, discard
                pending.pop(rid, None)

        # Cleanup stale entries (older than 5 minutes)
        now = time.time()
        stale = [rid for rid, info in pending.items()
                 if info.timestamp and now - info.timestamp > 300]
        for rid in stale:
            del pending[rid]


def main():
    print(f"[sync] Codex Log Sync starting", flush=True)
    print(f"[sync] DB: {DB_PATH}", flush=True)
    print(f"[sync] Container: {CONTAINER}", flush=True)

    # Verify DB exists
    if not os.path.exists(DB_PATH):
        print(f"[sync] ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")

    try:
        for info in tail_docker_logs():
            try:
                insert_log(db, info)
            except Exception as e:
                print(f"[sync] ERROR inserting rid={info.rid}: {e}", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        print("[sync] Shutting down", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
