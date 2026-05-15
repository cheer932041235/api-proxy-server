# API Proxy Server

**统一代理工具集** — 所有 AI 代理、中转、协议转换服务集中管理，部署到海外 VPS 24/7 运行，告别"电脑必须开着"。

## VPS 上运行的服务

| 服务 | 端口 | 用途 | 状态 |
|------|------|------|------|
| **AIClient-2-API** | 3000 | 免费 OAuth 账号池（Gemini/Kiro/Codex） | ✅ 运行中 |
| **New-API** | 3001 | API 管理/分发/计费中转站 | ✅ 运行中 |
| **chatgpt2api** | 3002 | ChatGPT Plus/Pro 反代（文本 + GPT-Image-2 出图） | ✅ 运行中 |

## 架构

```
用户端（Cherry Studio / Cursor / Windsurf / 浏览器）
  │
  └───────> VPS:3001 New-API（统一 API 入口、计费、多渠道聚合）
                  │
         ┌───────┼───────┐
         ▼              ▼
  VPS:3002           VPS:3000
  chatgpt2api        AIClient-2-API
  (文本 + 出图)      (免费 OAuth)
         │              │
    ChatGPT Plus     Gemini/Kiro/Codex
    GPT-Image-2

海外 VPS 170.106.65.175（硅谷 24/7）
```

## 目录结构

```
api-proxy-server/
├── new-api/                # New-API 中转站
│   └── README.md           # 部署命令 + 配置步骤
├── chatgpt2api/            # ChatGPT Plus/Pro 反代（文本 + 出图）
│   └── README.md           # 部署命令 + Token 导入 + 接入方式
├── aiclient2api/           # AIClient-2-API 免费 OAuth
│   ├── README.md
│   ├── config.json         # 主配置（gitignore）
│   └── provider_pools.json # 账号池（gitignore）
├── PLAN.md                 # 资产清单 + 架构规划 + 路线图
├── .gitignore
└── README.md
```

## 快速接入

通过 New-API 获取统一 API Key 后，任何支持 OpenAI 格式的客户端都可接入：

```
API Base URL: http://170.106.65.175:3001/v1
API Key:      在 New-API 管理后台「令牌」中生成
```

## 管理面板

| 面板 | 地址 | 用途 |
|------|------|------|
| New-API | http://170.106.65.175:3001 | 渠道/令牌/用户管理 |
| chatgpt2api | http://170.106.65.175:3002 | 号池管理、账号状态 |
| AIClient-2-API | http://170.106.65.175:3000 | 免费 OAuth 配置 |

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
