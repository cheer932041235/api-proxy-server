# codex-proxy

Codex CLI / OpenCode 专用反代，走 OpenAI **Responses API**。

## 基本信息

| 项目 | 值 |
|------|---|
| 端口 | 8080 |
| 类型 | Docker 容器 |
| 协议 | Responses API (`/v1/responses`) |
| 账号池 | 2 × Plus（OAuth 自动续期） |
| VPS 数据 | `/root/codex-proxy/data/` |
| 管理面板 | http://<YOUR_VPS_IP>:8080 |
| 公开端点 | `https://<YOUR_DOMAIN>/codex/v1` |
| API Key | `pwd` |

## 为什么独立于 New-API？

New-API 不支持 Responses API，请求经过 New-API 会退化为 Chat Completions 并**丢失 prompt caching**。因此 codex-proxy 由 Nginx 直接反代，不走 New-API。

## 核心特性

- **Prompt Caching**：`prompt_cache_key` + `SessionAffinity`，命中时输入 token 打 5 折
- **Reasoning Effort**：支持 low / medium / high / xhigh 精细控制
- **OAuth 自动续期**：有 refreshToken 时无需手动干预

## 续期

正常情况自动续期。异常时：
1. 管理面板 → "刷新过期"
2. 失败 → "+ 添加账户" 走 OAuth

详见 [../../docs/04-token-renewal.md](../../docs/04-token-renewal.md)

## 客户端配置

```json
{
  "codex-proxy": {
    "npm": "@ai-sdk/openai",
    "options": {
      "baseURL": "https://<YOUR_DOMAIN>/codex/v1",
      "apiKey": "pwd"
    }
  }
}
```

## 相关脚本

- `scripts/proxy-health-check.py` — 账号健康检查 + 邮件告警
- `scripts/codex-log-sync/` — 日志同步到 New-API（用量统计）
