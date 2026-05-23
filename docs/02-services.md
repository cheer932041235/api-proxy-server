# 服务详情

> 最后更新：2026-05-23

## 一、codex-proxy（反代）

| 项目 | 值 |
|------|---|
| 端口 | 8080 |
| 类型 | Docker 容器 |
| 用途 | Codex CLI / OpenCode 专用反代 |
| API 协议 | OpenAI Responses API (`/v1/responses`) |
| 账号池 | 2 个 Plus（OAuth 自动续期） |
| 续期 | OAuth refresh_token 自动刷新 |
| 数据路径 | `/root/codex-proxy/data/` |
| 日志 | `/var/log/nginx/codex.access.log`（JSON 格式） |
| 错误日志 | `/root/codex-proxy/data/error-log.jsonl` |
| 管理面板 | http://<YOUR_VPS_IP>:8080 |

### 核心优势

- **Responses API**：延迟更低，支持 `reasoning_effort` 精细控制（low/medium/high/xhigh）
- **Prompt Caching**：`prompt_cache_key` + `SessionAffinity`，命中缓存时输入 token 打 5 折
- **独立于 New-API**：New-API 不支持 Responses API，codex-proxy 必须由 Nginx 直接反代

### Docker 运行命令

```bash
# 查看具体 docker run 命令：
docker inspect codex-proxy --format='{{.Config.Cmd}}'
# 或查看 compose 文件（如有）
```

### 客户端配置（OpenCode）

```json
"codex-proxy": {
  "npm": "@ai-sdk/openai",
  "options": {
    "baseURL": "https://<YOUR_DOMAIN>/codex/v1",
    "apiKey": "pwd"
  }
}
```

---

## 二、chatgpt2api（反代）

| 项目 | 值 |
|------|---|
| 端口 | 3002 |
| 类型 | Docker 容器 |
| 镜像 | `ghcr.io/basketikun/chatgpt2api:latest` |
| 用途 | ChatGPT Plus 文本 + GPT-Image-2 出图 |
| API 协议 | OpenAI Chat Completions (`/v1/chat/completions`) + Images (`/v1/images/generations`) |
| 账号池 | 2 个 Plus（手动续 access_token，~10 天过期） |
| 续期 | **手动**（详见 [04-token-renewal.md](04-token-renewal.md)） |
| 数据路径 | `/root/chatgpt2api-data/` |
| 内部 API Key | `<YOUR_CHATGPT2API_AUTH_KEY>` |
| 管理面板 | http://<YOUR_VPS_IP>:3002 |
| GitHub | https://github.com/basketikun/chatgpt2api |

### 可用模型

- **文本**: auto, gpt-5, gpt-5-1, gpt-5-2, gpt-5-3, gpt-5-3-mini, gpt-5-5, gpt-5-mini
- **出图**: gpt-image-2, codex-gpt-image-2

### Docker 运行命令

```bash
docker run -d --name chatgpt2api --restart unless-stopped \
  -p 3002:3002 \
  -v /root/chatgpt2api-data:/data \
  ghcr.io/basketikun/chatgpt2api:latest
```

### 号池管理 API

```bash
# 查看账号
curl -s http://localhost:3002/api/accounts \
  -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' | python3 -m json.tool

# 导入新 Token
curl -s -X POST http://localhost:3002/api/accounts \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' \
  -d '{"tokens": ["ACCESS_TOKEN_HERE"]}'
```

---

## 三、new-api（网关）

| 项目 | 值 |
|------|---|
| 端口 | 3001 |
| 类型 | Docker 容器 |
| 用途 | 多渠道聚合、Token 计费、用户管理、API Key 分发 |
| 数据路径 | `/root/new-api-data/one-api.db`（SQLite） |
| 管理面板 | https://<YOUR_DOMAIN> |
| 管理账号 | `root` / `<YOUR_NEW_API_ADMIN_PASS>` |
| 模式 | 已开放注册（邮箱验证） |
| 内存缓存 | `MEMORY_CACHE_ENABLED=true` |

### 渠道配置

| 配置项 | 值 |
|--------|---|
| 渠道类型 | OpenAI (type=0) |
| 渠道名称 | chatgpt2api |
| 代理地址 | `http://172.17.0.1:3002`（Docker 内网） |
| 密钥 | `<YOUR_CHATGPT2API_AUTH_KEY>` |
| 模型列表 | gpt-5, gpt-5-mini, gpt-5-5, gpt-5-1, gpt-5-2, gpt-5-3, gpt-5-3-mini, gpt-image-2, codex-gpt-image-2 |

### 客户端接入

```
API Base URL: https://<YOUR_DOMAIN>/v1
API Key:      （用户自行在管理面板创建令牌）
```

管理员令牌：`<YOUR_NEW_API_KEY>`

---

## 四、image-gen（工具）

| 项目 | 值 |
|------|---|
| 端口 | 8088 |
| 类型 | Docker 容器（自建镜像） |
| 用途 | GPT-Image-2 双号池并行出图 Web 工具 |
| 源码 | `services/image-gen/` |
| 访问 | https://<YOUR_DOMAIN>/studio/ |
| 鉴权 | 答题解锁（<YOUR_STUDIO_QUIZ_QUESTION>→ <YOUR_STUDIO_QUIZ_ANSWER>），localStorage 持久 |

### 功能

- 双号池（Pool-A/B）并行调用 GPT-Image-2，一次生成两张图
- 智能增强（LLM 润色 prompt）+ 7 种风格预设 + 5 种尺寸
- 速率限制 6 次/5 分钟/IP，请求体上限 10KB
- 图片缓存 5 分钟自动清理
- 图到图编辑（上传参考图，4MB 限制）
- 过期提示横幅 + 浏览器缓存治理

### Docker 运行命令

```bash
cd /root/image-gen
docker build -t image-gen .
docker run -d --name image-gen --restart unless-stopped \
  -p 8088:8088 \
  --add-host=host.docker.internal:host-gateway \
  image-gen
```

### 更新流程

```bash
# 本地修改后上传
scp services/image-gen/* vps:/root/image-gen/

# VPS 重建
ssh vps "docker stop image-gen && docker rm image-gen && \
  cd /root/image-gen && docker build -t image-gen . && \
  docker run -d --name image-gen --restart unless-stopped \
  -p 8088:8088 --add-host=host.docker.internal:host-gateway image-gen"
```

---

## 五、codex-log-viewer（工具）

| 项目 | 值 |
|------|---|
| 端口 | 8089 |
| 类型 | systemd service（非 Docker） |
| 用途 | codex-proxy 调用日志面板 |
| 源码 | `services/codex-log-viewer/` |
| VPS 路径 | `/root/codex-log-viewer/server.py` |
| 访问 | https://<YOUR_DOMAIN>/codex/log/?token=pwd |
| systemd | `codex-log-viewer.service`（开机自启，崩溃自动重启） |

### 功能

- 实时刷新日志
- 模型统计（按模型分组计数）
- 状态码过滤
- 响应时间可视化

### 数据源

- 日志文件：`/var/log/nginx/codex.access.log`（JSON 格式，logrotate 自动轮转）
- Nginx 日志格式 `codex_json` 记录字段：`time_iso8601`, `remote_addr`, `method`, `uri`, `query`, `status`, `bytes_sent`, `request_time`, `upstream_response_time`, `user_agent`, `request_body`
- 从 `request_body` 中自动提取 `model` 字段

### API 端点

| 路径 | 用途 |
|------|------|
| `/codex/log/` | 日志面板 HTML |
| `/codex/log/api/logs` | 日志 JSON API |
| `/codex/log/api/stats` | 统计 JSON API |

---

## 已退役服务

| 服务 | 端口 | 退役日期 | 原因 | 备份位置 |
|------|------|----------|------|----------|
| aiclient2api | 3000 | 2026-05-23 | 完全不再使用 | `/root/_archive/aiclient2api-20260523` |
| Claude Desktop 网关 | - | 2026-05-23 | 不再使用 Claude Desktop | 已从仓库删除 |
