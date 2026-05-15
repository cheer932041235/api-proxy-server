# AIClient-2-API 部署记录

已部署在海外 VPS `170.106.65.175` 上，Docker 运行中。

## 访问方式

| 项目 | 值 |
|------|---|
| Web UI | http://170.106.65.175:3000 |
| API Key | 见 config.json 中的 REQUIRED_API_KEY |
| API 端点 | http://170.106.65.175:3000/v1/chat/completions |

## 已配置的 Provider

- `gemini-cli-oauth` — Gemini 免费额度（2 个 Google 账号）
- `openai-qwen-oauth` — 通义千问（已配置）
- `claude-kiro-oauth` — Kiro Claude 额度（未配置）
- `openai-codex-oauth` — Codex（未配置）
- `grok-custom` — Grok（未配置）

## Docker 命令

```bash
docker run -d \
  -p 3000:3000 \
  -p 8085-8086:8085-8086 \
  -p 1455:1455 \
  -p 19876-19880:19876-19880 \
  --restart=always \
  -v /root/aiclient2api/configs:/app/configs \
  --name aiclient2api \
  justlikemaki/aiclient-2-api:latest
```

## 更新容器

```bash
docker pull justlikemaki/aiclient-2-api:latest
docker stop aiclient2api && docker rm aiclient2api
# 重新运行上面的 docker run 命令
```

## 本地配置备份

- `config.json` — 主配置（含 API Key，已 gitignore）
- `provider_pools.json` — 账号池配置（已 gitignore）
- `plugins.json` — 插件配置

## 接入工具

```bash
# Claude Code / Codex CLI
export ANTHROPIC_BASE_URL=http://170.106.65.175:3000/openai-qwen-oauth
export ANTHROPIC_API_KEY=sk-cd496b42731410f5bffe1656c46a212a

# 或 Gemini
export ANTHROPIC_BASE_URL=http://170.106.65.175:3000/gemini-cli-oauth
```
