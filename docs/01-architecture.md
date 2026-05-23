# 架构文档

> 最后更新：2026-05-23

## 总体架构

```
                          海外 VPS (<YOUR_VPS_IP>, 硅谷)
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    Nginx (443/80)                             │    │
│  │  SSL 终端 · 路由分发 · JSON access log · HTTP→HTTPS 重定向  │    │
│  └────┬──────────┬──────────┬──────────┬──────────┬─────────────┘    │
│       │          │          │          │          │                   │
│       ▼          ▼          ▼          ▼          ▼                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ ┌──────────────┐   │
│  │ codex-  │ │chatgpt- │ │ new-api │ │ image- │ │codex-log-    │   │
│  │ proxy   │ │ 2api    │ │         │ │  gen   │ │  viewer      │   │
│  │ :8080   │ │ :3002   │ │ :3001   │ │ :8088  │ │ :8089        │   │
│  │         │ │         │ │         │ │        │ │              │   │
│  │ 反代    │ │ 反代    │ │ 网关    │ │ 工具   │ │ 工具         │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └───┬────┘ └──────────────┘   │
│       │          │          │          │                             │
│       │          │      ┌───┴───┐      │                             │
│       │          │      │ 聚合  │      │                             │
│       │          │◄─────┤ 两个  │      │                             │
│       │◄─────────│──────┤ 反代  │      │                             │
│       │          │      └───────┘      │                             │
└───────┼──────────┼─────────────────────┼─────────────────────────────┘
        │          │                     │
        ▼          ▼                     ▼
   ┌──────────────────────────────────────────┐
   │             OpenAI API                    │
   │  Responses API / Chat Completions / Images│
   └──────────────────────────────────────────┘
```

## 组件分类

| 类型 | 组件 | 端口 | 说明 |
|------|------|------|------|
| **反代** | codex-proxy | 8080 | Codex CLI / OpenCode 专用，走 Responses API |
| **反代** | chatgpt2api | 3002 | ChatGPT Plus 文本 + GPT-Image-2 出图 |
| **网关** | new-api | 3001 | 多渠道聚合、Token 计费、用户管理 |
| **工具** | image-gen | 8088 | GPT-Image-2 双号池并行出图 Web |
| **工具** | codex-log-viewer | 8089 | codex-proxy 调用日志面板 |

> 历史服务（已于 2026-05-23 退役）：`aiclient2api`（免费 OAuth 号池，端口 3000）、Claude Desktop 网关

## 数据流

### 路径 A：Codex CLI / OpenCode（Responses API）

```
Codex CLI / OpenCode
    ↓ HTTPS
https://<YOUR_DOMAIN>/codex/v1
    ↓ Nginx (SSL 终端 + codex_json access log)
http://127.0.0.1:8080 (codex-proxy Docker)
    ↓ Responses API + prompt_cache_key + SessionAffinity
OpenAI API (OAuth 账号池，自动续期)
```

**关键**：codex-proxy 走 Responses API（`/v1/responses`），**不能**经过 New-API 中转（New-API 不支持 Responses API，会退化为 chat/completions 并丢失 prompt caching）。

### 路径 B：学员/客户端（Chat Completions）

```
Cherry Studio / ChatBox / 网页聊天
    ↓ HTTPS
https://<YOUR_DOMAIN>/v1
    ↓ Nginx
http://127.0.0.1:3001 (New-API)
    ↓ 渠道路由（内网 Docker）
http://172.17.0.1:3002 (chatgpt2api)
    ↓ Chat Completions API
OpenAI (access_token 号池，手动续期)
```

### 路径 C：AI Studio 配图

```
浏览器
    ↓ HTTPS
https://<YOUR_DOMAIN>/studio/
    ↓ Nginx
http://127.0.0.1:8088 (image-gen Docker)
    ↓ 双号池并行
http://host.docker.internal:3002/v1/images/generations (chatgpt2api)
    ↓
OpenAI GPT-Image-2
```

### 路径 D：figure-tools 直接出图

```
figure_generator.py (本地)
    ↓ HTTPS
https://<YOUR_DOMAIN>/img/v1/images/generations
    ↓ Nginx
http://127.0.0.1:3002/v1/images/generations (chatgpt2api)
    ↓
OpenAI GPT-Image-2
```

## 端口分配

| 端口 | 服务 | Docker | 云防火墙 | 备注 |
|------|------|--------|----------|------|
| 22 | SSH | - | ✅ 已放行 | |
| 80 | Nginx HTTP | - | ✅ | 301 → HTTPS |
| 443 | Nginx HTTPS | - | ✅ | SSL 终端 |
| 3001 | New-API | ✅ | ✅ | API 网关 |
| 3002 | chatgpt2api | ✅ | ✅ | Plus 反代 |
| 8080 | codex-proxy | ✅ | ✅ | Codex 反代 |
| 8088 | image-gen | ✅ | ✅ | 配图工具 |
| 8089 | codex-log-viewer | systemd | ❌ 不需要 | 仅 localhost，Nginx 反代 |

> ⚠️ 云控制台防火墙 ≠ VPS 内部 iptables，**两层都要放行**才能外部访问

## Nginx 路由表

| 路径 | 后端 | 用途 |
|------|------|------|
| `/` (精确) | 静态 `/var/www/homepage/` | 品牌主页 |
| `/` (通配) | `127.0.0.1:3001` | New-API 网关 |
| `/codex/` | `127.0.0.1:8080` | codex-proxy API + 日志 |
| `/gpt2api/` | `127.0.0.1:3002` | chatgpt2api 管理面板 |
| `/img/v1/` | `127.0.0.1:3002/v1/` | chatgpt2api Images API 直通 |
| `/studio/` | `127.0.0.1:8088` | AI Studio 配图 |

## 缓存架构

| 数据路径 | 缓存机制 | 状态 |
|----------|----------|------|
| Codex CLI → codex-proxy → OpenAI | Responses API `prompt_cache_key` + `SessionAffinity` → 服务端 prompt caching（输入 token 5 折） | ✅ 已内置 |
| 学员 API → New-API → chatgpt2api | New-API 内存缓存（`MEMORY_CACHE_ENABLED=true`，相同请求直接返回） | ✅ 已开启 |
| AI Studio → chatgpt2api | 生成结果内存缓存 5 分钟 | ✅ 已实现 |
| chatgpt2api 自身 | 无 prompt caching 支持（网页反代架构限制） | ❌ 已知限制 |

**Prompt Caching 原理**：OpenAI 服务端要求同一会话的请求路由到同一账号（sticky session）且传递 `prompt_cache_key`。codex-proxy 已内置此能力；chatgpt2api 作为网页反代不支持。

## SSL / 域名

| 项目 | 值 |
|------|---|
| 域名 | `<YOUR_DOMAIN>` |
| 证书 | Let's Encrypt（certbot 自动续期） |
| 证书路径 | `/etc/letsencrypt/live/<YOUR_DOMAIN>/` |
| HTTP 重定向 | 80 → 443（301） |
| 配置文件 | `/etc/nginx/sites-enabled/<YOUR_DOMAIN>.conf` |
