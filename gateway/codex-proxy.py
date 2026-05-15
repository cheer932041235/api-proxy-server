"""
Anthropic -> OpenAI Protocol Proxy

接收 Claude Code / Codex CLI 发出的 Anthropic Messages API 请求，
实时翻译为 OpenAI Chat Completions API 格式转发到上游，再将响应翻译回来。

核心能力：
  - 请求翻译：system prompt、messages、tools、tool_result 全量转换
  - 流式 SSE 翻译：OpenAI delta 事件流 → Anthropic 结构化事件流
  - 工具调用双向映射：tool_use ↔ function_call

Usage:
    python codex-proxy.py
    python codex-proxy.py --port 5678 --upstream https://api.vectorengine.ai --model claude-opus-4-6
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import uuid
from typing import Any

from aiohttp import web, ClientSession, ClientTimeout

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("codex-proxy")

# ── Secrets ─────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_secrets() -> dict[str, str]:
    """从 secrets.json 加载 API 密钥。文件不存在时返回空字典。"""
    path = os.path.join(_SCRIPT_DIR, "secrets.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    log.warning("secrets.json not found, API keys will be empty")
    return {}

_secrets = _load_secrets()

# ── Default Config ────────────────────────────
UPSTREAM_BASE = "https://api.vectorengine.ai"
UPSTREAM_KEY = _secrets.get("vectorengine_key", "")
DEFAULT_MODEL = "claude-opus-4-6"
UPSTREAM_FORMAT = "chat"  # 'chat' = /v1/chat/completions, 'responses' = /v1/responses
PORT = 5678


# ══════════════════════════════════════════════════════════
#  Request Translation: Anthropic -> OpenAI
# ══════════════════════════════════════════════════════════

def translate_request(body: dict[str, Any]) -> dict[str, Any]:
    """将 Anthropic Messages API 请求体转换为 OpenAI Chat Completions 格式。

    处理：system prompt 提升、消息格式转换、tool_use/tool_result 双向映射、
    工具定义 input_schema → parameters 转换。
    """
    messages = []

    # System message (Anthropic: top-level "system" field)
    system = body.get("system")
    if system:
        if isinstance(system, str):
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            text = "\n".join(
                b.get("text", "") for b in system if b.get("type") == "text"
            )
            if text:
                messages.append({"role": "system", "content": text})

    # Convert messages
    for msg in body.get("messages", []):
        role = msg["role"]
        content = msg.get("content", "")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            tool_results = [b for b in content if b.get("type") == "tool_result"]

            if tool_results:
                # tool_result blocks -> OpenAI "tool" role messages
                for tr in tool_results:
                    tc_content = tr.get("content", "")
                    if isinstance(tc_content, list):
                        tc_content = "\n".join(
                            b.get("text", "") for b in tc_content
                            if b.get("type") == "text"
                        )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tr.get("tool_use_id", ""),
                        "content": str(tc_content) if tc_content else "",
                    })
                # Include any accompanying text blocks
                text_blocks = [b for b in content if b.get("type") == "text"]
                if text_blocks:
                    text = "\n".join(b.get("text", "") for b in text_blocks)
                    messages.append({"role": "user", "content": text})
            else:
                # text + tool_use blocks (assistant messages)
                text_parts = []
                tool_calls = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": json.dumps(block.get("input", {})),
                            },
                        })

                assistant_msg = {
                    "role": role,
                    "content": "\n".join(text_parts) if text_parts else None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

    # Build OpenAI request
    result = {
        "model": DEFAULT_MODEL,  # Always use configured model
        "messages": messages,
        "stream": body.get("stream", False),
    }

    for key in ["max_tokens", "temperature", "top_p", "stop"]:
        if key in body:
            result[key] = body[key]

    # Tool definitions
    if "tools" in body:
        result["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in body["tools"]
        ]
        result["tool_choice"] = "auto"

    if body.get("stream"):
        result["stream_options"] = {"include_usage": True}

    return result


# ══════════════════════════════════════════════════════════
#  Non-streaming Response: OpenAI -> Anthropic
# ══════════════════════════════════════════════════════════

def translate_response(openai_resp: dict[str, Any]) -> dict[str, Any]:
    """将 OpenAI Chat Completions 响应转换为 Anthropic Messages 格式。

    处理：finish_reason 映射、function_call → tool_use 转换、usage 字段重命名。
    """
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})

    content = []
    text = message.get("content")
    if text:
        content.append({"type": "text", "text": text})

    for tc in message.get("tool_calls", []):
        func = tc.get("function", {})
        try:
            input_data = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            input_data = {}
        content.append({
            "type": "tool_use",
            "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
            "name": func.get("name", ""),
            "input": input_data,
        })

    finish = choice.get("finish_reason", "stop")
    stop_reason = "tool_use" if finish == "tool_calls" else "end_turn"
    usage = openai_resp.get("usage", {})

    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": content if content else [{"type": "text", "text": ""}],
        "model": DEFAULT_MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


# ══════════════════════════════════════════════════════════
#  Streaming Translation: OpenAI SSE -> Anthropic SSE
# ══════════════════════════════════════════════════════════

def sse(event: str, data: dict[str, Any]) -> bytes:
    """构造一条 SSE 事件。"""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


async def translate_stream(resp: Any, response: web.StreamResponse) -> None:
    """将 OpenAI 的扁平 delta SSE 流翻译为 Anthropic 的结构化事件流。

    维护状态机：跟踪 block_index、tool_buffers、text_block_closed，
    在流中实时判断何时开始/关闭内容块。
    """
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # message_start
    await response.write(sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": DEFAULT_MODEL,
            "stop_reason": None, "stop_sequence": None,
            "usage": {
                "input_tokens": 0, "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }))

    # content_block_start (text)
    await response.write(sse("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }))

    await response.write(sse("ping", {"type": "ping"}))

    block_index = 0
    tool_buffers = {}  # tc_id -> index
    finish_reason = "end_turn"
    output_tokens = 0
    text_block_closed = False

    buffer = ""
    async for chunk_bytes, _ in resp.content.iter_chunks():
        buffer += chunk_bytes.decode("utf-8", errors="replace")

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                continue

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # Handle usage chunk (stream_options.include_usage)
            if chunk.get("usage"):
                output_tokens = chunk["usage"].get("completion_tokens", output_tokens)

            choices = chunk.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            fr = choices[0].get("finish_reason")

            # Text content
            text = delta.get("content")
            if text:
                output_tokens = max(output_tokens, output_tokens + max(1, len(text) // 4))
                await response.write(sse("content_block_delta", {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                }))

            # Tool calls
            for tc in delta.get("tool_calls", []):
                tc_id = tc.get("id")
                func = tc.get("function", {})
                tc_name = func.get("name")
                tc_args = func.get("arguments", "")

                if tc_id and tc_id not in tool_buffers:
                    # Close text block before first tool
                    if not text_block_closed:
                        await response.write(sse("content_block_stop", {
                            "type": "content_block_stop", "index": 0,
                        }))
                        text_block_closed = True

                    block_index += 1
                    tool_buffers[tc_id] = block_index

                    await response.write(sse("content_block_start", {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {
                            "type": "tool_use",
                            "id": tc_id,
                            "name": tc_name or "",
                        },
                    }))

                if tc_args:
                    idx = tool_buffers.get(tc_id, block_index)
                    await response.write(sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": idx,
                        "delta": {"type": "input_json_delta", "partial_json": tc_args},
                    }))

            if fr:
                if fr == "tool_calls":
                    finish_reason = "tool_use"
                elif fr == "length":
                    finish_reason = "max_tokens"
                else:
                    finish_reason = "end_turn"

    # Close open blocks
    if tool_buffers:
        for tc_id, idx in tool_buffers.items():
            await response.write(sse("content_block_stop", {
                "type": "content_block_stop", "index": idx,
            }))
    if not text_block_closed:
        await response.write(sse("content_block_stop", {
            "type": "content_block_stop", "index": 0,
        }))

    # message_delta
    await response.write(sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": finish_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    }))

    # message_stop
    await response.write(sse("message_stop", {"type": "message_stop"}))


# ══════════════════════════════════════════════════════════
#  Responses API Translation: Anthropic <-> OpenAI Responses
# ══════════════════════════════════════════════════════════

def translate_request_responses(body: dict[str, Any]) -> dict[str, Any]:
    """将 Anthropic Messages API 请求体转换为 OpenAI Responses API 格式。

    处理：system → developer 角色、messages → input 项、
    tool_use → function_call、tool_result → function_call_output。
    """
    items: list[dict[str, Any]] = []

    # System message → developer role
    system = body.get("system")
    if system:
        if isinstance(system, str):
            items.append({"role": "developer", "content": system})
        elif isinstance(system, list):
            text = "\n".join(
                b.get("text", "") for b in system if b.get("type") == "text"
            )
            if text:
                items.append({"role": "developer", "content": text})

    # Convert messages
    for msg in body.get("messages", []):
        role = msg["role"]
        content = msg.get("content", "")

        if isinstance(content, str):
            items.append({"role": role, "content": content})
        elif isinstance(content, list):
            tool_results = [b for b in content if b.get("type") == "tool_result"]

            if tool_results:
                for tr in tool_results:
                    tc_content = tr.get("content", "")
                    if isinstance(tc_content, list):
                        tc_content = "\n".join(
                            b.get("text", "") for b in tc_content
                            if b.get("type") == "text"
                        )
                    items.append({
                        "type": "function_call_output",
                        "call_id": tr.get("tool_use_id", ""),
                        "output": str(tc_content) if tc_content else "",
                    })
                text_blocks = [b for b in content if b.get("type") == "text"]
                if text_blocks:
                    text = "\n".join(b.get("text", "") for b in text_blocks)
                    items.append({"role": "user", "content": text})
            else:
                text_parts: list[str] = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        if text_parts:
                            items.append({"role": role, "content": "\n".join(text_parts)})
                            text_parts = []
                        items.append({
                            "type": "function_call",
                            "call_id": block.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {})),
                        })

                if text_parts:
                    items.append({"role": role, "content": "\n".join(text_parts)})

    result: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "input": items,
        "stream": body.get("stream", False),
    }

    if "max_tokens" in body:
        result["max_output_tokens"] = body["max_tokens"]

    # Tool definitions (Responses API: flattened, no nested "function" key)
    if "tools" in body:
        result["tools"] = [
            {
                "type": "function",
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            }
            for t in body["tools"]
        ]

    return result


def translate_response_responses(resp_data: dict[str, Any]) -> dict[str, Any]:
    """将 OpenAI Responses API 响应转换为 Anthropic Messages 格式。"""
    content: list[dict[str, Any]] = []

    for item in resp_data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    content.append({"type": "text", "text": part.get("text", "")})
        elif item.get("type") == "function_call":
            try:
                input_data = json.loads(item.get("arguments", "{}"))
            except json.JSONDecodeError:
                input_data = {}
            content.append({
                "type": "tool_use",
                "id": item.get("call_id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": item.get("name", ""),
                "input": input_data,
            })

    has_tool = any(c.get("type") == "tool_use" for c in content)
    stop_reason = "tool_use" if has_tool else "end_turn"
    usage = resp_data.get("usage", {})

    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": content if content else [{"type": "text", "text": ""}],
        "model": DEFAULT_MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


async def translate_stream_responses(resp: Any, response: web.StreamResponse) -> None:
    """将 OpenAI Responses API 的 SSE 流翻译为 Anthropic 结构化事件流。

    事件映射：
      response.created         → message_start + content_block_start
      response.output_text.delta → content_block_delta (text_delta)
      response.output_item.added (function_call) → content_block_start (tool_use)
      response.function_call_arguments.delta → content_block_delta (input_json_delta)
      response.completed       → content_block_stop + message_delta + message_stop
    """
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # message_start
    await response.write(sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": DEFAULT_MODEL,
            "stop_reason": None, "stop_sequence": None,
            "usage": {
                "input_tokens": 0, "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }))

    # content_block_start (text, index 0)
    await response.write(sse("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }))

    await response.write(sse("ping", {"type": "ping"}))

    block_index = 0
    tool_blocks: dict[str, dict[str, Any]] = {}  # call_id -> {index, name}
    finish_reason = "end_turn"
    output_tokens = 0
    text_block_closed = False

    current_event = ""
    buffer = ""
    async for chunk_bytes, _ in resp.content.iter_chunks():
        buffer += chunk_bytes.decode("utf-8", errors="replace")

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()

            if not line:
                continue

            if line.startswith("event: "):
                current_event = line[7:]
                continue

            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            evt = data.get("type", current_event)

            # ── Text delta ──
            if evt == "response.output_text.delta":
                delta_text = data.get("delta", "")
                if delta_text:
                    await response.write(sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": delta_text},
                    }))

            # ── Function call start (from output_item.added) ──
            elif evt == "response.output_item.added":
                item = data.get("item", {})
                if item.get("type") == "function_call":
                    call_id = item.get("call_id", f"call_{uuid.uuid4().hex[:24]}")
                    if not text_block_closed:
                        await response.write(sse("content_block_stop", {
                            "type": "content_block_stop", "index": 0,
                        }))
                        text_block_closed = True

                    block_index += 1
                    tool_blocks[call_id] = {"index": block_index, "name": item.get("name", "")}

                    await response.write(sse("content_block_start", {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {
                            "type": "tool_use",
                            "id": call_id,
                            "name": item.get("name", ""),
                        },
                    }))

            # ── Function call arguments delta ──
            elif evt == "response.function_call_arguments.delta":
                call_id = data.get("call_id", "")
                args_delta = data.get("delta", "")
                if call_id in tool_blocks and args_delta:
                    idx = tool_blocks[call_id]["index"]
                    await response.write(sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": idx,
                        "delta": {"type": "input_json_delta", "partial_json": args_delta},
                    }))

            # ── Response completed ──
            elif evt == "response.completed":
                resp_data = data.get("response", {})
                usage = resp_data.get("usage", {})
                output_tokens = usage.get("output_tokens", 0)

                output = resp_data.get("output", [])
                has_tool = any(item.get("type") == "function_call" for item in output)
                finish_reason = "tool_use" if has_tool else "end_turn"

    # Close open blocks
    for _call_id, info in tool_blocks.items():
        await response.write(sse("content_block_stop", {
            "type": "content_block_stop", "index": info["index"],
        }))
    if not text_block_closed:
        await response.write(sse("content_block_stop", {
            "type": "content_block_stop", "index": 0,
        }))

    # message_delta
    await response.write(sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": finish_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    }))

    # message_stop
    await response.write(sse("message_stop", {"type": "message_stop"}))


# ══════════════════════════════════════════════════════════
#  HTTP Handlers
# ══════════════════════════════════════════════════════════

async def handle_messages(request: web.Request) -> web.StreamResponse:
    body = await request.json()
    is_stream = body.get("stream", False)

    # Choose translation path based on upstream format
    if UPSTREAM_FORMAT == "responses":
        openai_body = translate_request_responses(body)
        endpoint = f"{UPSTREAM_BASE}/v1/responses"
    else:
        openai_body = translate_request(body)
        endpoint = f"{UPSTREAM_BASE}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {UPSTREAM_KEY}",
        "Content-Type": "application/json",
    }

    session: ClientSession = request.app["session"]

    try:
        if is_stream:
            resp = await session.post(
                endpoint, json=openai_body, headers=headers,
            )

            response = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
            await response.prepare(request)
            if UPSTREAM_FORMAT == "responses":
                await translate_stream_responses(resp, response)
            else:
                await translate_stream(resp, response)
            await response.write_eof()
            resp.close()
            return response
        else:
            async with session.post(
                endpoint, json=openai_body, headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log.error("Upstream %d: %s", resp.status, error_text[:200])
                    return web.json_response(
                        {"error": {"type": "api_error", "message": "Upstream request failed"}},
                        status=resp.status,
                    )
                upstream_resp = await resp.json()
                if UPSTREAM_FORMAT == "responses":
                    return web.json_response(translate_response_responses(upstream_resp))
                else:
                    return web.json_response(translate_response(upstream_resp))

    except Exception as e:
        log.error("Upstream error: %s", e)
        return web.json_response(
            {"error": {"type": "api_error", "message": "Internal server error"}},
            status=500,
        )


async def handle_responses_passthrough(request: web.Request) -> web.StreamResponse:
    """直通转发 /v1/responses 请求到上游（供 Codex CLI OpenAI 模式使用）。

    仅替换 model 字段为 DEFAULT_MODEL，其余原样转发。
    """
    body = await request.json()
    body["model"] = DEFAULT_MODEL
    is_stream = body.get("stream", False)

    log.info("[passthrough] model=%s stream=%s", DEFAULT_MODEL, is_stream)

    headers = {
        "Authorization": f"Bearer {UPSTREAM_KEY}",
        "Content-Type": "application/json",
    }

    session: ClientSession = request.app["session"]

    try:
        if is_stream:
            resp = await session.post(
                f"{UPSTREAM_BASE}/v1/responses",
                json=body, headers=headers,
            )
            log.info("[passthrough] upstream status=%d content-type=%s",
                     resp.status, resp.headers.get("Content-Type", "?"))

            if resp.status != 200:
                error_body = await resp.text()
                log.error("[passthrough] upstream error: %s", error_body[:300])
                resp.close()
                return web.json_response(
                    {"error": {"message": error_body[:200], "type": "upstream_error"}},
                    status=resp.status,
                )

            response = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
            await response.prepare(request)

            try:
                async for chunk_bytes, _ in resp.content.iter_chunks():
                    await response.write(chunk_bytes)
                await response.write_eof()
            except ConnectionResetError:
                log.warning("[passthrough] client disconnected during stream")
            except Exception as e:
                log.warning("[passthrough] stream write error: %s", e)
            finally:
                resp.close()
            return response
        else:
            async with session.post(
                f"{UPSTREAM_BASE}/v1/responses",
                json=body, headers=headers,
            ) as resp:
                log.info("[passthrough] upstream status=%d", resp.status)
                data = await resp.read()
                return web.Response(
                    body=data,
                    status=resp.status,
                    content_type="application/json",
                )

    except Exception as e:
        log.error("[passthrough] error: %s", e)
        return web.json_response(
            {"error": {"message": str(e), "type": "proxy_error"}},
            status=502,
        )


async def handle_models(request: web.Request) -> web.Response:
    """转发 /v1/models 请求到上游。"""
    headers = {"Authorization": f"Bearer {UPSTREAM_KEY}"}
    session: ClientSession = request.app["session"]
    try:
        async with session.get(
            f"{UPSTREAM_BASE}/v1/models", headers=headers,
        ) as resp:
            data = await resp.read()
            return web.Response(
                body=data, status=resp.status,
                content_type="application/json",
            )
    except Exception as e:
        log.error("Models error: %s", e)
        return web.json_response(
            {"error": {"message": str(e), "type": "proxy_error"}},
            status=502,
        )


async def handle_health(request: web.Request):
    return web.json_response({"status": "ok"})


# ── App Lifecycle ───────────────────────────────────────

async def on_startup(app):
    app["session"] = ClientSession(timeout=ClientTimeout(total=300))


async def on_cleanup(app):
    await app["session"].close()


def main():
    global UPSTREAM_BASE, UPSTREAM_KEY, DEFAULT_MODEL, UPSTREAM_FORMAT

    parser = argparse.ArgumentParser(description="Anthropic -> OpenAI Protocol Proxy")
    parser.add_argument("--port", type=int, default=PORT, help="Local port (default: 5678)")
    parser.add_argument("--upstream", default=UPSTREAM_BASE, help="Upstream OpenAI-compatible base URL")
    parser.add_argument("--key", default=UPSTREAM_KEY, help="Upstream API key")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use (default: claude-opus-4-6)")
    parser.add_argument("--format", default=UPSTREAM_FORMAT, choices=["chat", "responses"],
                        help="Upstream API format: 'chat' = /v1/chat/completions, 'responses' = /v1/responses")
    args = parser.parse_args()

    UPSTREAM_BASE = args.upstream.rstrip("/")
    UPSTREAM_KEY = args.key
    DEFAULT_MODEL = args.model
    UPSTREAM_FORMAT = args.format

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_post("/v1/messages", handle_messages)
    app.router.add_post("/v1/responses", handle_responses_passthrough)
    app.router.add_post("/responses", handle_responses_passthrough)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_get("/models", handle_models)
    app.router.add_get("/", handle_health)

    fmt_label = "/v1/responses" if UPSTREAM_FORMAT == "responses" else "/v1/chat/completions"
    log.info("=== Anthropic -> OpenAI Protocol Proxy ===")
    bind_host = os.environ.get("PROXY_HOST", "127.0.0.1")
    log.info("Listen:   http://%s:%d", bind_host, args.port)
    log.info("Upstream: %s (%s)", UPSTREAM_BASE, fmt_label)
    log.info("Model:    %s", DEFAULT_MODEL)

    web.run_app(app, host=bind_host, port=args.port, print=None)


if __name__ == "__main__":
    main()
