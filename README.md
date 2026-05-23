# API Proxy Server

> **自建 AI API 中转站** — 一台海外 VPS + ChatGPT Plus，搭一个属于自己的 OpenAI 反代 + 网关。
>
> ¥50/月 VPS + $20/月 Plus，做完后 Codex CLI / OpenCode / Cherry Studio / Cursor 全能用。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 这个项目是什么

把"ChatGPT Plus 网页订阅"变成"标准 OpenAI API"，部署到自己海外 VPS 上 24/7 运行。包含：

- **2 个反代**（直接对接 AI 服务）：`codex-proxy` / `chatgpt2api`
- **1 个网关**（聚合 + 计费 + 用户体系）：`new-api`
- **2 个工具**（衍生功能）：`image-gen` / `codex-log-viewer`

## 为什么自建（而不是买中转站）

| | 自建 | 买中转站 |
|---|---|---|
| 成本 | ¥50 VPS + $20 Plus = 约 ¥190/月 | $20-100/月起，按量计费 |
| Token 单价 | 几乎零（Plus 套餐内） | 商业溢价 |
| Prompt Caching | ✅ 支持（codex-proxy 内置） | 多数中转站不支持 Responses API |
| 数据隐私 | 自己机器，自己 log | 经过第三方 |
| 可控性 | 完全可控 + 可定制 | 取决于服务商 |
| 学习价值 | ⭐⭐⭐⭐⭐ Docker / Nginx / OAuth | ⭐ |

## 服务清单

| 端口 | 服务 | 类型 | 用途 | 续期 |
|------|------|------|------|------|
| 8080 | **codex-proxy** | 反代 | Codex CLI / OpenCode，Responses API + prompt caching | OAuth 自动 |
| 3002 | **chatgpt2api** | 反代 | ChatGPT Plus 文本 + GPT-Image-2 出图 | 手动续 token（~10 天） |
| 3001 | **new-api** | 网关 | 多渠道聚合、Token 计费、用户管理 | - |
| 8088 | **image-gen** | 工具 | GPT-Image-2 双号池并行出图 Web | 复用 chatgpt2api |
| 8089 | **codex-log-viewer** | 工具 | codex-proxy 调用日志面板 | - |

## 架构

```
                    ┌─ 反代: codex-proxy (:8080) ─────────┐
                    │   Codex CLI 专用                     │
                    │   OAuth 自动续期 + Responses API     │
用户/客户端 ──→ Nginx ┤                                      ├──→ OpenAI
                    ├─ 反代: chatgpt2api (:3002) ─────────┤
                    │   ChatGPT Plus 文本 + 出图           │
                    │   手动续 access_token (~10 天)       │
                    ├─ 网关: new-api (:3001) ──────────────┤
                    │   统一入口 / 计费 / 聚合两个反代     │
                    ├─ 工具: image-gen (:8088)              │
                    └─ 工具: codex-log-viewer (:8089)      │
```

## 快速开始

### 你需要什么

- 一台**海外 VPS**（推荐 2C4G，Ubuntu 22.04+，¥50/月级别）
- 一个**域名**（解析到 VPS）
- 至少 **1 个 ChatGPT Plus** 账号
- 本机 Linux/macOS/WSL（Windows 用 Git Bash 也行）

### 一键部署

```bash
# 1. 克隆仓库
git clone https://github.com/cheer932041235/api-proxy-server.git
cd api-proxy-server

# 2. 复制环境变量并填入你的值
cp .env.example .env
vim .env                              # 改 VPS_HOST / DOMAIN / 各种密码

# 3. 首次安装（在新 VPS 上跑一次）
make setup                            # 装 Docker / Nginx / SSL / 部署所有容器

# 4. 后续更新
make deploy                           # 同步本地修改 + 重启对应服务
make logs                             # 看日志
make status                           # 查状态
```

详细步骤见 [docs/00-quickstart.md](docs/00-quickstart.md)。

## 公开端点（部署后）

| 端点 | 用途 | 鉴权 |
|------|------|------|
| `https://${DOMAIN}/v1` | New-API 主入口 | API Key |
| `https://${DOMAIN}/codex/v1` | Codex Proxy（绕过 New-API） | `${CODEX_PUBLIC_KEY}` |
| `https://${DOMAIN}/img/v1` | chatgpt2api 直通 | `${CHATGPT2API_AUTH_KEY}` |
| `https://${DOMAIN}/studio/` | 配图工具 | 答题/密码解锁 |
| `https://${DOMAIN}/codex/log/` | 日志面板 | URL token |

## 文档导航

| 文档 | 内容 |
|------|------|
| **[docs/00-quickstart.md](docs/00-quickstart.md)** | **★ 30 分钟跑通** |
| [docs/01-architecture.md](docs/01-architecture.md) | 完整架构 + 数据流 + 端口表 |
| [docs/02-services.md](docs/02-services.md) | 每服务详情（容器、数据路径） |
| [docs/03-operations.md](docs/03-operations.md) | 日常运维（重启、日志、备份） |
| **[docs/04-token-renewal.md](docs/04-token-renewal.md)** | **★ 续期 SOP** |
| **[docs/05-troubleshooting.md](docs/05-troubleshooting.md)** | **★ 故障速查** |
| **[docs/06-network-tuning.md](docs/06-network-tuning.md)** | **★ 链路稳定性** |

每个服务的部署细节在 `services/<服务名>/README.md`。

## 目录结构

```
api-proxy-server/
├── README.md / LICENSE / Makefile
├── .env.example              ← 环境变量模板（.env 由你创建，已 gitignore）
├── docs/                     ← 架构 / 运维 / 续期 / 故障 / 调优
├── services/                 ← 各服务文档与源码
│   ├── codex-proxy/          ← Codex CLI 反代（用上游公开镜像）
│   ├── chatgpt2api/          ← ChatGPT Plus 反代（用上游公开镜像）
│   ├── new-api/              ← API 网关（用上游公开镜像）
│   ├── image-gen/            ← 配图工具（自建源码）
│   └── codex-log-viewer/     ← 日志面板（自建源码）
├── nginx/
│   ├── api.example.com.conf.template   ← Nginx 模板（用 envsubst 渲染）
│   └── rendered/                       ← 渲染产物（gitignore）
└── scripts/                  ← 部署 / 运维 / 健康检查
    ├── setup.sh / deploy.sh / render-nginx.sh
    ├── daily-backup.sh / daily-report.sh
    ├── proxy-health-check.py
    └── ...
```

## 上游开源项目致谢

| 项目 | 作用 | 镜像 |
|------|------|------|
| [chatgpt2api](https://github.com/basketikun/chatgpt2api) | ChatGPT Plus 网页反代 | `ghcr.io/basketikun/chatgpt2api:latest` |
| [New-API](https://github.com/QuantumNous/new-api) | API 管理/分发网关 | `calciumion/new-api:latest` |
| [codex-proxy](https://github.com/icebear0828/codex-proxy) | Codex CLI 反代 | `ghcr.io/icebear0828/codex-proxy:latest` |
| Let's Encrypt + certbot | SSL 证书自动续期 | - |
| Nginx | 反向代理 + SSL 终端 | - |

`image-gen` 和 `codex-log-viewer` 是本仓库自带源码，MIT 协议。

## 安全提醒

⚠️ 部署前务必：
- 把 `.env` 中所有 `ChangeMe_*` 改成强随机值
- 不要把 `.env` 提交到 GitHub（已在 `.gitignore`）
- VPS 防火墙只放行必要端口（22/80/443，其他端口仅 localhost）
- 定期检查 `docker logs` 中的异常请求

⚠️ 关于 ChatGPT 账号：
- access_token 泄露 = 账号被盗
- 单 IP 大量请求可能触发 OpenAI 风控
- 号池越多越稳定（建议 ≥2 个 Plus）

## License

[MIT](LICENSE) — 自由使用，欢迎 PR。
