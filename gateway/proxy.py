"""
Claude Desktop <-> Multi-Provider Gateway Proxy

本地代理层，让 Claude Desktop 通过 3P 模式接入多个第三方模型提供商。

核心功能：
  - 多提供商路由（按模型名自动分发）
  - 浏览器控制面板实时切换模型

Usage:
  python proxy.py
  Gateway:       http://127.0.0.1:8082
  Control Panel: http://127.0.0.1:8083
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
from typing import Dict

import requests as req_lib
from flask import Flask, request, Response

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("proxy")

# ── Secrets ─────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_secrets() -> Dict[str, str]:
    """从 secrets.json 加载 API 密钥。文件不存在时返回空字典。"""
    path = os.path.join(_SCRIPT_DIR, "secrets.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    log.warning("secrets.json not found, API keys will be empty")
    return {}

_secrets = _load_secrets()

# ── Config ──────────────────────────────────────────────
PROXY_PORT = 8082
PANEL_PORT = 8083
BIND_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
SOPHNET_BASE = "https://www.sophnet.com/api/open-apis/anthropic"

# Xiaomi MiMo — Anthropic 兼容格式
MIMO_BASE = "https://token-plan-cn.xiaomimimo.com/anthropic"
MIMO_KEY = _secrets.get("mimo_key", "")

# SophNet 模型（走 Anthropic 格式）
SOPHNET_MODELS = {
    "DeepSeek-V4-Flash":  {"price": "¥1/¥2 per Mt",  "desc": "DeepSeek V4 快速版，性价比最高"},
    "DeepSeek-V4-Pro":    {"price": "¥9/¥18 per Mt",  "desc": "DeepSeek V4 专业版，能力最强"},
    "gpt-4o-mini":        {"price": "$0.15/$0.6 per Mt", "desc": "OpenAI GPT-4o-mini（SophNet）"},
    "Doubao-Seed-1.6":    {"price": "¥0.8/¥2 per Mt", "desc": "字节豆包 Seed 1.6"},
    "MiniMax-M2.7":       {"price": "¥2.1/¥8.4 per Mt", "desc": "MiniMax 最新模型，Agent 能力强"},
    "Kimi-K2.6":          {"price": "¥6.5/¥27 per Mt", "desc": "月之暗面 Kimi，原生多模态"},
    "GLM-5.1":            {"price": "¥6/¥24 per Mt",  "desc": "智谱 GLM 5.1，国产旗舰"},
}

# Xiaomi MiMo 模型（走 Anthropic 格式，自带 API Key）
MIMO_MODELS = {
    "MiMo-V2.5-Pro":      {"price": "2x credits", "desc": "⭐ 小米 MiMo V2.5 Pro，最强旗舰"},
    "MiMo-V2.5":          {"price": "1x credits", "desc": "小米 MiMo V2.5，性价比之王"},
    "MiMo-V2-Pro":        {"price": "2x credits", "desc": "小米 MiMo V2 Pro"},
}
# 显示名 → API 名映射（MiMo API 要求小写）
MIMO_API_NAMES = {k: k.lower() for k in MIMO_MODELS}

# 合并所有模型
MODELS = {**SOPHNET_MODELS, **MIMO_MODELS}

# ── State ───────────────────────────────────────────────
state = {
    "current_model": "DeepSeek-V4-Flash",
    "request_count": 0,
    "last_request": None,
}

# ══════════════════════════════════════════════════════════
#  Proxy App (port 8082) — Claude Desktop connects here
# ══════════════════════════════════════════════════════════
proxy_app = Flask("proxy")

@proxy_app.errorhandler(Exception)
def handle_exception(e):
    """全局异常捕获，防止进程崩溃"""
    log.error("Unhandled exception: %s", e)
    return Response(
        json.dumps({"type": "error", "error": {"type": "internal_error", "message": "Internal server error"}}, ensure_ascii=False).encode("utf-8"),
        status=500, content_type="application/json; charset=utf-8"
    )

@proxy_app.route("/<path:path>", methods=["POST"])
def proxy_post(path):
    data = request.get_json(force=True, silent=True) or {}
    original_model = data.get("model", "unknown")
    # If the model name is already a known SophNet model, keep it; otherwise use panel selection
    if original_model in MODELS:
        target_model = original_model
    else:
        target_model = state["current_model"]
    data["model"] = target_model

    state["request_count"] += 1
    state["last_request"] = time.strftime("%H:%M:%S")
    suffix = "" if original_model == target_model else f" (mapped from {original_model})"
    log.info("#%d /%s | %s%s", state['request_count'], path, target_model, suffix)

    # ── 路由分发：SophNet (Anthropic) vs MiMo (Anthropic) ──
    if target_model in MIMO_MODELS:
        return _proxy_via_mimo(data, path)
    else:
        return _proxy_via_sophnet(data, path)

def _proxy_via_sophnet(data, path):
    """原有逻辑：直接转发 Anthropic 格式到 SophNet"""
    target_url = f"{SOPHNET_BASE}/{path}"
    api_key = request.headers.get("x-api-key", "")
    if not api_key:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            api_key = auth[7:]

    fwd_headers = {"Content-Type": "application/json"}
    if api_key:
        fwd_headers["x-api-key"] = api_key
    for h in ["anthropic-version", "anthropic-beta"]:
        v = request.headers.get(h)
        if v:
            fwd_headers[h] = v

    try:
        resp = req_lib.post(
            target_url, json=data, headers=fwd_headers,
            timeout=120, proxies={"http": None, "https": None}
        )
        log.info("SophNet -> %d (%d bytes)", resp.status_code, len(resp.content))
        excluded = {"transfer-encoding", "connection", "content-encoding", "content-length"}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        return Response(resp.content, status=resp.status_code, headers=headers)
    except Exception as e:
        log.error("SophNet: %s", e)
        return Response(
            json.dumps({"type": "error", "error": {"type": "proxy_error", "message": "Upstream request failed"}}),
            status=502, content_type="application/json"
        )

def _proxy_via_mimo(data, path):
    """Xiaomi MiMo：Anthropic 兼容格式，自带 API Key"""
    # 显示名转 API 名
    data["model"] = MIMO_API_NAMES.get(data.get("model", ""), data.get("model", ""))
    target_url = f"{MIMO_BASE}/{path}"
    fwd_headers = {
        "Content-Type": "application/json",
        "x-api-key": MIMO_KEY,
    }
    for h in ["anthropic-version", "anthropic-beta"]:
        v = request.headers.get(h)
        if v:
            fwd_headers[h] = v

    try:
        resp = req_lib.post(
            target_url, json=data, headers=fwd_headers,
            timeout=120, proxies={"http": None, "https": None}
        )
        log.info("MiMo -> %d (%d bytes)", resp.status_code, len(resp.content))
        excluded = {"transfer-encoding", "connection", "content-encoding", "content-length"}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        return Response(resp.content, status=resp.status_code, headers=headers)
    except Exception as e:
        log.error("MiMo: %s", e)
        return Response(
            json.dumps({"type": "error", "error": {"type": "proxy_error", "message": "Upstream request failed"}}),
            status=502, content_type="application/json"
        )

@proxy_app.route("/v1/models", methods=["GET"])
def list_models():
    """返回模型列表，供 Claude Desktop 3p 模式自动发现"""
    model_list = []
    for name, info in MODELS.items():
        model_list.append({
            "id": name,
            "type": "model",
            "display_name": name,
            "created_at": "2025-01-01T00:00:00Z",
        })
    return Response(
        json.dumps({"data": model_list, "has_more": False, "first_id": model_list[0]["id"], "last_id": model_list[-1]["id"]}),
        content_type="application/json"
    )

@proxy_app.route("/", methods=["GET"])
@proxy_app.route("/<path:path>", methods=["GET"])
def proxy_get(path=""):
    return Response(json.dumps({"status": "ok", "model": state["current_model"]}), content_type="application/json")

# ══════════════════════════════════════════════════════════
#  Control Panel (port 8083) — Open in browser to switch
# ══════════════════════════════════════════════════════════
panel_app = Flask("panel")

PANEL_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Gateway 控制面板</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }
  .container { max-width: 640px; margin: 40px auto; padding: 0 20px; }
  h1 { font-size: 22px; margin-bottom: 8px; }
  .subtitle { color: #888; font-size: 13px; margin-bottom: 24px; }
  .stats { display: flex; gap: 16px; margin-bottom: 24px; }
  .stat { background: #fff; border-radius: 10px; padding: 16px; flex: 1; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .stat-label { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-value { font-size: 20px; font-weight: 600; margin-top: 4px; }
  .stat-value.active { color: #10b981; }
  .models { display: flex; flex-direction: column; gap: 10px; }
  .model-card {
    background: #fff; border-radius: 10px; padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); cursor: pointer;
    border: 2px solid transparent; transition: all 0.15s;
    display: flex; justify-content: space-between; align-items: center;
  }
  .model-card:hover { border-color: #ddd; }
  .model-card.selected { border-color: #10b981; background: #f0fdf4; }
  .model-name { font-weight: 600; font-size: 15px; }
  .model-desc { font-size: 12px; color: #888; margin-top: 2px; }
  .model-price { font-size: 12px; color: #666; background: #f0f0f0; padding: 3px 8px; border-radius: 6px; white-space: nowrap; }
  .model-card.selected .model-price { background: #dcfce7; color: #16a34a; }
  .check { display: none; color: #10b981; font-weight: bold; font-size: 18px; margin-left: 12px; }
  .model-card.selected .check { display: inline; }
  .footer { margin-top: 20px; font-size: 11px; color: #bbb; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <h1>Claude Gateway 控制面板</h1>
  <p class="subtitle">切换模型后，Claude Desktop 下一条消息就会用新模型</p>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">当前模型</div>
      <div class="stat-value active" id="current">-</div>
    </div>
    <div class="stat">
      <div class="stat-label">已处理请求</div>
      <div class="stat-value" id="count">0</div>
    </div>
    <div class="stat">
      <div class="stat-label">最近请求</div>
      <div class="stat-value" id="last">-</div>
    </div>
  </div>

  <div class="models" id="models"></div>
  <div class="footer">Gateway: http://127.0.0.1:{{PROXY_PORT}} &nbsp;|&nbsp; Panel: http://127.0.0.1:{{PANEL_PORT}}</div>
</div>
<script>
const MODELS = {{MODELS_JSON}};
const modelsDiv = document.getElementById('models');

function render(currentModel) {
  modelsDiv.innerHTML = '';
  for (const [name, info] of Object.entries(MODELS)) {
    const card = document.createElement('div');
    card.className = 'model-card' + (name === currentModel ? ' selected' : '');
    card.innerHTML = `
      <div>
        <div class="model-name">${name}</div>
        <div class="model-desc">${info.desc}</div>
      </div>
      <div style="display:flex;align-items:center">
        <span class="model-price">${info.price}</span>
        <span class="check">✓</span>
      </div>`;
    card.onclick = () => switchModel(name);
    modelsDiv.appendChild(card);
  }
}

async function fetchStatus() {
  const r = await fetch('/api/status');
  const d = await r.json();
  document.getElementById('current').textContent = d.current_model;
  document.getElementById('count').textContent = d.request_count;
  document.getElementById('last').textContent = d.last_request || '-';
  render(d.current_model);
}

async function switchModel(name) {
  await fetch('/api/switch', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model:name})});
  fetchStatus();
}

fetchStatus();
setInterval(fetchStatus, 3000);
</script>
</body>
</html>"""

@panel_app.route("/")
def panel_index():
    html = PANEL_HTML.replace("{{PROXY_PORT}}", str(PROXY_PORT))
    html = html.replace("{{PANEL_PORT}}", str(PANEL_PORT))
    html = html.replace("{{MODELS_JSON}}", json.dumps(MODELS, ensure_ascii=False))
    return Response(html, content_type="text/html; charset=utf-8")

@panel_app.route("/api/status")
def panel_status():
    return Response(json.dumps(state, ensure_ascii=False), content_type="application/json")

@panel_app.route("/api/switch", methods=["POST"])
def panel_switch():
    data = request.get_json(force=True, silent=True) or {}
    model = data.get("model", "")
    if model in MODELS:
        old = state["current_model"]
        state["current_model"] = model
        log.info("Model switch: %s -> %s", old, model)
        return Response(json.dumps({"ok": True, "model": model}), content_type="application/json")
    return Response(json.dumps({"ok": False, "error": "unknown model"}), status=400, content_type="application/json")

# ══════════════════════════════════════════════════════════
#  Start both servers
# ══════════════════════════════════════════════════════════
def _port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

if __name__ == "__main__":
    if _port_in_use(PROXY_PORT):
        log.info("Port %d in use. Waiting for it to free up...", PROXY_PORT)
        for _ in range(30):  # 最多等 30 秒
            time.sleep(1)
            if not _port_in_use(PROXY_PORT):
                break
        else:
            log.warning("Port %d still in use after 30s — another instance running.", PROXY_PORT)
            sys.exit(0)
    log.info("=== API Gateway Proxy ===")
    log.info("Proxy:   http://%s:%d", BIND_HOST, PROXY_PORT)
    log.info("Panel:   http://%s:%d", BIND_HOST, PANEL_PORT)
    log.info("Model:   %s", state['current_model'])
    log.info("Models:  %s", ', '.join(MODELS.keys()))

    # Panel on background thread
    panel_thread = threading.Thread(
        target=lambda: panel_app.run(host=BIND_HOST, port=PANEL_PORT, debug=False),
        daemon=True
    )
    panel_thread.start()

    # Proxy on main thread — 自动重启循环
    while True:
        try:
            proxy_app.run(host=BIND_HOST, port=PROXY_PORT, debug=False)
        except Exception as e:
            log.error("Proxy crashed: %s. Restarting in 3s...", e)
            time.sleep(3)
        except KeyboardInterrupt:
            log.info("Shutting down.")
            break
