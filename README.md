# API Proxy Server

**AI 服务中转站** — 所有 AI 代理、中转、出图工具集中管理，部署到海外 VPS 24/7 运行。

## VPS 上运行的服务

| 服务 | 端口 | 用途 | 状态 |
|------|------|------|------|
| **AIClient-2-API** | 3000 | 免费 OAuth 账号池（Gemini/Kiro/Codex） | ✅ |
| **New-API** | 3001 | API 管理/分发/计费中转站 | ✅ |
| **chatgpt2api** | 3002 | ChatGPT Plus 反代（文本 + GPT-Image-2） | ✅ |
| **codex-proxy** | 8080 | Codex 原生 Responses API 代理（自用） | ✅ |
| **AI Studio 配图** | 8088 | GPT-Image-2 双号池并行出图 Web 工具 | ✅ |
| **Nginx** | 80/443 | HTTPS 反代 + SSL（api.shujinxing777.com） | ✅ |

## 架构

```
用户端（Cherry Studio / Cursor / Windsurf / 浏览器）
  │
  ├──────> VPS:3001 New-API（统一 API 入口、计费、多渠道聚合）
  │                │
  │       ┌───────┼───────┐
  │       ▼              ▼
  │   VPS:3002       VPS:3000
  │   chatgpt2api    AIClient-2-API
  │   (文本+出图)    (免费 OAuth)
  │
  └──────> VPS:8088 AI Studio 配图
                    双号池并行 GPT-Image-2
                    答题解锁 + 速率限制

海外 VPS 170.106.65.175（硅谷 24/7）
```

## 目录结构

```
api-proxy-server/
├── new-api/              # New-API 中转站配置和部署记录
├── chatgpt2api/          # ChatGPT Plus 反代配置和部署记录
├── aiclient2api/         # AIClient-2-API 免费 OAuth 配置
├── image-gen/            # AI Studio 配图 Web 工具
│   ├── server.py         # Python HTTP 服务端（双号池并行）
│   ├── index.html        # 前端页面
│   ├── style.css         # 样式
│   ├── script.js         # 前端逻辑（解锁+双图）
│   └── Dockerfile        # Docker 部署
├── gateway/              # Claude Desktop 多模型网关（本地运行）
├── nginx/                # Nginx 反代配置
│   └── api.shujinxing777.com.conf
├── scripts/              # 运维脚本
│   ├── fix-docker-iptables.sh   # Docker 重启 iptables 自动修复
│   ├── fix-docker-iptables.service
│   ├── daily-backup.sh          # 每日数据备份（02:00）
│   └── daily-report.sh          # 每日 Token 使用报告（09:00）
├── PLAN.md               # 资产清单 + 架构规划 + 运维指南
├── TODO.md               # 待办 & 已完成事项
└── README.md
```

## 快速接入

**API 方式**（Cherry Studio / Cursor 等）：
```
API Base URL: https://api.shujinxing777.com/v1
API Key:      在 New-API 管理后台「令牌」中生成
```

**配图工具**：https://api.shujinxing777.com/studio/（需答题解锁）

## 管理面板

| 面板 | 地址 | 用途 |
|------|------|------|
| New-API | https://api.shujinxing777.com | 渠道/令牌/用户管理 |
| chatgpt2api | https://api.shujinxing777.com/gpt2api/ | 号池管理、账号状态 |
| codex-proxy | http://170.106.65.175:8080 | Codex Proxy Dashboard |
| AIClient-2-API | http://170.106.65.175:3000 | 免费 OAuth 配置 |
| AI Studio | https://api.shujinxing777.com/studio/ | GPT-Image-2 配图 |

## 服务器信息

| 项目 | 值 |
|------|---|
| VPS IP | `170.106.65.175` |
| 名称 | OpenClaw(龙虾)-4KQB |
| 地域 | 硅谷 |
| 配置 | 2核 4GB 60GB |
| 系统 | Ubuntu (Linux 6.8) |
| Docker | 29.3.1 ✅ |
| 到期 | 2027-04-07 |
