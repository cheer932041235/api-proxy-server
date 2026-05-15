"""
API Reverse Proxy Server
请求转发 + 逐条 token/费用日志 + 缓存命中率监控
"""

import os
import csv
import json
import time
import logging
from datetime import datetime
from flask import Flask, request, Response
import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# === 配置 ===
UPSTREAM_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
UPSTREAM_KEY = os.getenv("OPENAI_API_KEY", "")
PROXY_KEY = os.getenv("PROXY_API_KEY", "")
PROXY_PORT = int(os.getenv("PROXY_PORT", "3001"))
LOG_FILE = os.getenv("LOG_FILE", "logs/usage.csv")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# === 模型定价表（$/M tokens）===
PRICING = {
    # OpenAI
    "gpt-4o":           {"input": 2.50,  "output": 10.00, "cached": 1.25},
    "gpt-4o-mini":      {"input": 0.15,  "output": 0.60,  "cached": 0.075},
    "gpt-4.1":          {"input": 2.00,  "output": 8.00,  "cached": 0.50},
    "gpt-4.1-mini":     {"input": 0.40,  "output": 1.60,  "cached": 0.10},
    "gpt-4.1-nano":     {"input": 0.10,  "output": 0.40,  "cached": 0.025},
    "o3":               {"input": 2.00,  "output": 8.00,  "cached": 0.50},
    "o3-mini":          {"input": 1.10,  "output": 4.40,  "cached": 0.275},
    "o4-mini":          {"input": 1.10,  "output": 4.40,  "cached": 0.275},
    "codex-mini":       {"input": 1.50,  "output": 6.00,  "cached": 0.375},
    # Anthropic
    "claude-sonnet-4-20250514":    {"input": 3.00,  "output": 15.00, "cached": 0.30},
    "claude-opus-4-20250514":      {"input": 5.00,  "output": 25.00, "cached": 0.50},
    "claude-haiku-3.5":            {"input": 0.80,  "output": 4.00,  "cached": 0.08},
}

# 默认定价（未知模型）
DEFAULT_PRICING = {"input": 2.00, "output": 8.00, "cached": 0.50}


def init_log_file():
    """初始化 CSV 日志文件"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "timestamp", "model", "endpoint",
                "input_tokens", "output_tokens", "cached_tokens",
                "cache_hit_rate", "cost_usd", "latency_ms",
                "status_code"
            ])


def calc_cost(model: str, input_t: int, output_t: int, cached_t: int) -> float:
    """根据模型定价计算美元费用"""
    p = PRICING.get(model, DEFAULT_PRICING)
    fresh_input = input_t - cached_t
    cost = (
        fresh_input * p["input"] / 1_000_000
        + cached_t * p["cached"] / 1_000_000
        + output_t * p["output"] / 1_000_000
    )
    return cost


def log_usage(model: str, endpoint: str, usage: dict, latency_ms: float, status_code: int):
    """记录单条请求的 token 用量和费用"""
    input_t = usage.get("prompt_tokens", 0)
    output_t = usage.get("completion_tokens", 0)

    # OpenAI 格式的缓存 token
    cached_t = 0
    details = usage.get("prompt_tokens_details", {})
    if details:
        cached_t = details.get("cached_tokens", 0)

    cache_rate = (cached_t / input_t * 100) if input_t > 0 else 0
    cost = calc_cost(model, input_t, output_t, cached_t)

    with open(LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().isoformat(),
            model, endpoint,
            input_t, output_t, cached_t,
            f"{cache_rate:.1f}",
            f"{cost:.6f}",
            f"{latency_ms:.0f}",
            status_code
        ])

    # 终端实时输出
    cache_icon = "🟢" if cache_rate > 80 else ("🟡" if cache_rate > 50 else "🔴")
    logger.info(
        f"{cache_icon} [{model}] in={input_t} out={output_t} "
        f"cached={cached_t}({cache_rate:.0f}%) "
        f"cost=${cost:.4f} latency={latency_ms:.0f}ms"
    )


def check_auth():
    """验证请求携带的 Proxy Key"""
    if not PROXY_KEY:
        return True  # 未设置 Key 则不鉴权
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "")
    return token == PROXY_KEY


def build_upstream_headers():
    """构建转发给上游 API 的 headers"""
    headers = {}
    for key, value in request.headers:
        lower = key.lower()
        if lower in ("host", "content-length", "transfer-encoding"):
            continue
        headers[key] = value
    # 替换为上游 API Key
    headers["Authorization"] = f"Bearer {UPSTREAM_KEY}"
    headers["Host"] = UPSTREAM_URL.replace("https://", "").replace("http://", "")
    return headers


@app.route("/v1/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    """核心代理路由"""
    # 鉴权
    if not check_auth():
        return {"error": "Invalid proxy API key"}, 401

    url = f"{UPSTREAM_URL}/v1/{path}"
    headers = build_upstream_headers()
    body = request.get_json(silent=True)

    start = time.time()

    # 判断是否为流式请求
    is_stream = body and body.get("stream", False)

    try:
        resp = http_requests.request(
            method=request.method,
            url=url,
            headers=headers,
            json=body,
            stream=is_stream,
            timeout=300
        )
    except http_requests.exceptions.RequestException as e:
        logger.error(f"Upstream request failed: {e}")
        return {"error": f"Upstream connection failed: {str(e)}"}, 502

    latency_ms = (time.time() - start) * 1000

    # 流式响应：透传 SSE
    if is_stream:
        def generate():
            full_content = ""
            usage_data = {}
            for chunk in resp.iter_lines():
                if chunk:
                    yield chunk.decode("utf-8") + "\n\n"
                    # 尝试从最后的 chunk 解析 usage
                    try:
                        line = chunk.decode("utf-8")
                        if line.startswith("data: ") and line != "data: [DONE]":
                            data = json.loads(line[6:])
                            if "usage" in data:
                                usage_data = data["usage"]
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
            # 流结束后记录日志
            if usage_data:
                model = body.get("model", "unknown")
                log_usage(model, path, usage_data, latency_ms, resp.status_code)

        return Response(
            generate(),
            status=resp.status_code,
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # 非流式响应：解析 usage 并记录
    try:
        data = resp.json()
    except ValueError:
        return Response(resp.content, status=resp.status_code, headers=dict(resp.headers))

    usage = data.get("usage", {})
    if usage:
        model = data.get("model", body.get("model", "unknown") if body else "unknown")
        log_usage(model, path, usage, latency_ms, resp.status_code)

    return Response(
        json.dumps(data, ensure_ascii=False),
        status=resp.status_code,
        content_type="application/json"
    )


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return {"status": "ok", "upstream": UPSTREAM_URL}


@app.route("/stats", methods=["GET"])
def stats():
    """简易统计接口 — 返回今日用量摘要"""
    if not check_auth():
        return {"error": "Invalid proxy API key"}, 401

    today = datetime.now().strftime("%Y-%m-%d")
    total_cost = 0
    total_input = 0
    total_output = 0
    total_cached = 0
    total_requests = 0

    try:
        with open(LOG_FILE, newline="") as f:
            for row in csv.DictReader(f):
                if row["timestamp"].startswith(today):
                    total_cost += float(row["cost_usd"])
                    total_input += int(row["input_tokens"])
                    total_output += int(row["output_tokens"])
                    total_cached += int(row["cached_tokens"])
                    total_requests += 1
    except FileNotFoundError:
        pass

    cache_rate = (total_cached / total_input * 100) if total_input > 0 else 0

    return {
        "date": today,
        "requests": total_requests,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cached_tokens": total_cached,
        "cache_hit_rate": f"{cache_rate:.1f}%",
        "total_cost_usd": f"${total_cost:.4f}"
    }


if __name__ == "__main__":
    init_log_file()
    logger.info(f"API Proxy starting on port {PROXY_PORT}")
    logger.info(f"Upstream: {UPSTREAM_URL}")
    logger.info(f"Log file: {LOG_FILE}")
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=False)
