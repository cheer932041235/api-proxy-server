"""
协议转换单元测试

测试 Anthropic ↔ OpenAI 格式的双向转换逻辑，覆盖：
  - 请求翻译（system prompt、消息、图片、工具定义、工具结果）
  - 响应翻译（文本、工具调用、停止原因、用量统计）
  - proxy.py 的消息构建和图片检测
"""

from __future__ import annotations

import json
import sys
import os

import pytest

# 将项目根目录加入 path，以便 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════
#  codex-proxy.py: translate_request 测试
# ══════════════════════════════════════════════════════════

class TestTranslateRequest:
    """测试 Anthropic → OpenAI 请求转换。"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        # 动态导入，避免模块级 secrets.json 依赖
        import importlib
        spec = importlib.util.spec_from_file_location(
            "codex_proxy",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "codex-proxy.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.translate_request = mod.translate_request
        self.translate_response = mod.translate_response

    def test_basic_message(self):
        """基础文本消息转换。"""
        body = {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "你好"}],
            "max_tokens": 1024,
        }
        result = self.translate_request(body)
        assert result["messages"] == [{"role": "user", "content": "你好"}]
        assert result["max_tokens"] == 1024

    def test_system_prompt_string(self):
        """字符串格式 system prompt 提升为 system 角色消息。"""
        body = {
            "model": "claude-3-sonnet",
            "system": "你是一个助手",
            "messages": [{"role": "user", "content": "你好"}],
        }
        result = self.translate_request(body)
        assert result["messages"][0] == {"role": "system", "content": "你是一个助手"}
        assert result["messages"][1] == {"role": "user", "content": "你好"}

    def test_system_prompt_blocks(self):
        """Block 数组格式 system prompt 合并为单条 system 消息。"""
        body = {
            "model": "claude-3-sonnet",
            "system": [
                {"type": "text", "text": "第一段"},
                {"type": "text", "text": "第二段"},
            ],
            "messages": [{"role": "user", "content": "你好"}],
        }
        result = self.translate_request(body)
        assert result["messages"][0]["content"] == "第一段\n第二段"

    def test_tool_definitions(self):
        """Anthropic 工具定义 → OpenAI function 定义。"""
        body = {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "读取文件"}],
            "tools": [
                {
                    "name": "read_file",
                    "description": "读取文件内容",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                }
            ],
        }
        result = self.translate_request(body)
        assert len(result["tools"]) == 1
        tool = result["tools"][0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "read_file"
        assert tool["function"]["parameters"]["type"] == "object"
        assert result["tool_choice"] == "auto"

    def test_tool_use_in_assistant_message(self):
        """Assistant 消息中的 tool_use block → OpenAI tool_calls。"""
        body = {
            "model": "claude-3-sonnet",
            "messages": [
                {"role": "user", "content": "读取 /tmp/a.txt"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "我来读取文件"},
                        {
                            "type": "tool_use",
                            "id": "call_abc123",
                            "name": "read_file",
                            "input": {"path": "/tmp/a.txt"},
                        },
                    ],
                },
            ],
        }
        result = self.translate_request(body)
        assistant_msg = result["messages"][1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] == "我来读取文件"
        assert len(assistant_msg["tool_calls"]) == 1
        tc = assistant_msg["tool_calls"][0]
        assert tc["id"] == "call_abc123"
        assert tc["function"]["name"] == "read_file"
        assert json.loads(tc["function"]["arguments"]) == {"path": "/tmp/a.txt"}

    def test_tool_result(self):
        """tool_result block → OpenAI tool 角色消息。"""
        body = {
            "model": "claude-3-sonnet",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_abc123",
                            "content": "文件内容：hello world",
                        }
                    ],
                }
            ],
        }
        result = self.translate_request(body)
        tool_msg = result["messages"][0]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "call_abc123"
        assert tool_msg["content"] == "文件内容：hello world"

    def test_streaming_options(self):
        """stream=True 时自动添加 stream_options。"""
        body = {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "你好"}],
            "stream": True,
        }
        result = self.translate_request(body)
        assert result["stream"] is True
        assert result["stream_options"] == {"include_usage": True}

    def test_optional_params_forwarded(self):
        """temperature、top_p、stop 等可选参数正确转发。"""
        body = {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "你好"}],
            "temperature": 0.7,
            "top_p": 0.9,
            "stop": ["\n"],
        }
        result = self.translate_request(body)
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9
        assert result["stop"] == ["\n"]


# ══════════════════════════════════════════════════════════
#  codex-proxy.py: translate_response 测试
# ══════════════════════════════════════════════════════════

class TestTranslateResponse:
    """测试 OpenAI → Anthropic 响应转换。"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import importlib
        spec = importlib.util.spec_from_file_location(
            "codex_proxy",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "codex-proxy.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.translate_response = mod.translate_response

    def test_basic_text_response(self):
        """基础文本响应转换。"""
        openai_resp = {
            "id": "chatcmpl-abc123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "你好！"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        result = self.translate_response(openai_resp)
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "你好！"
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5

    def test_tool_call_response(self):
        """工具调用响应转换（function_call → tool_use）。"""
        openai_resp = {
            "id": "chatcmpl-abc123",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_xyz",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path": "/tmp/a.txt"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15},
        }
        result = self.translate_response(openai_resp)
        assert result["stop_reason"] == "tool_use"
        assert len(result["content"]) == 1
        tool_block = result["content"][0]
        assert tool_block["type"] == "tool_use"
        assert tool_block["id"] == "call_xyz"
        assert tool_block["name"] == "read_file"
        assert tool_block["input"] == {"path": "/tmp/a.txt"}

    def test_text_plus_tool_response(self):
        """同时包含文本和工具调用的响应。"""
        openai_resp = {
            "id": "chatcmpl-abc123",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "让我来读取文件",
                        "tool_calls": [
                            {
                                "id": "call_xyz",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path": "/tmp"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15},
        }
        result = self.translate_response(openai_resp)
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"

    def test_finish_reason_mapping(self):
        """停止原因映射：stop→end_turn, tool_calls→tool_use。"""
        for openai_reason, expected in [("stop", "end_turn"), ("tool_calls", "tool_use")]:
            openai_resp = {
                "choices": [{"message": {"content": "ok"}, "finish_reason": openai_reason}],
                "usage": {},
            }
            result = self.translate_response(openai_resp)
            assert result["stop_reason"] == expected, f"{openai_reason} should map to {expected}"

    def test_malformed_tool_arguments(self):
        """工具参数 JSON 解析失败时返回空 dict 而不是崩溃。"""
        openai_resp = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_bad",
                                "function": {"name": "test", "arguments": "not-valid-json{"},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {},
        }
        result = self.translate_response(openai_resp)
        assert result["content"][0]["input"] == {}

# 注：原 TestProxyHelpers 测试类已在 v2.1.0 一并移除，
# 因 proxy.py 中的 _build_openai_messages / _extract_user_text / _IMAGE_PATTERN
# 是 aiproxies 路由的专属 helper，aiproxies 提供商下线后这些函数也跟着删除。
