# API Proxy Server — 资产清单 & 路线图

> 最后更新：2026-05-23
> 详细架构、运维、续期、故障速查请见 [docs/](docs/)

---

## 资产清单

### 服务器

| 名称 | IP | 地域 | 配置 | 到期 |
|------|---|------|------|------|
| <YOUR_VPS_INSTANCE_NAME> | <YOUR_VPS_IP> | 硅谷 | 2核 4GB 60GB Ubuntu | 2027-04-07 |

云控制台：https://console.cloud.tencent.com/lighthouse

### 已部署服务

| 服务 | 端口 | 类型 | 状态 |
|------|------|------|------|
| codex-proxy | 8080 | 反代 (Docker) | ✅ |
| chatgpt2api | 3002 | 反代 (Docker) | ✅ |
| new-api | 3001 | 网关 (Docker) | ✅ |
| image-gen | 8088 | 工具 (Docker) | ✅ |
| codex-log-viewer | 8089 | 工具 (systemd) | ✅ |

> 已退役（2026-05-23）：`aiclient2api` (3000)、Claude Desktop 网关。详见 `docs/02-services.md` 末尾。

### 账号资产

| 邮箱 | 等级 | 号池 |
|------|------|------|
| <YOUR_PLUS_EMAIL_A> | Plus | codex-proxy + chatgpt2api |
| <YOUR_PLUS_EMAIL_B> | Plus | codex-proxy + chatgpt2api |
| 待购买 | Pro ($200/月) | 未来：高端模型 o1-pro |

---

## 路线图

### 第一阶段：自用跑通 ✅

- [x] 部署 codex-proxy / chatgpt2api / new-api / image-gen / codex-log-viewer
- [x] 双 Plus 账号导入 codex-proxy + chatgpt2api 号池
- [x] HTTPS + 域名（<YOUR_DOMAIN>，Let's Encrypt）
- [x] Codex CLI / OpenCode 接入 codex-proxy
- [x] AI Studio 配图工具上线
- [x] 日志面板 + 健康检查 + 自动备份 + 每日报告

### 第二阶段：稳定运营（进行中）

- [x] 自动备份 + 每日报告 + 健康检查告警
- [x] Docker iptables 开机自动修复
- [x] 完整文档（README + docs/ + services/X/README.md）
- [ ] 设置模型定价倍率
- [ ] 渠道健康监控 + 自动故障转移
- [ ] 学员客户端接入图文教程（Cherry Studio / ChatBox）

### 第三阶段：扩展（按需）

- [ ] 购买 GPT Pro → 加入号池
- [ ] 接入 Claude / Gemini（CLIProxyAPI 或独立反代）
- [ ] 学员额度批量充值脚本（>5 人时做）
- [ ] 计费体系 + 充值（如对外开放）

---

## 反代工具对比（备忘）

| 项目 | 类型 | 当前选择 |
|------|------|---------|
| **chatgpt2api** | 网页反代（Plus） | ✅ 已部署：唯一同时支持文本 + GPT-Image-2 + 号池 Web 面板 |
| **codex-proxy** | Codex 反代 | ✅ 已部署：自建（Responses API + prompt caching） |
| Recodex | Codex 镜像 | 未来备选（中转站主流） |
| CLIProxyAPI | 多家统一 | 未来备选（Claude/Gemini 接入） |
| chat2api | 网页反代 | 已弃用（被 chatgpt2api 替代） |

---

## 成本估算

| 项目 | 月费用 | 说明 |
|------|--------|------|
| VPS 硅谷 | ~¥50/月 | 已付到 2027-04 |
| ChatGPT Plus ×2 | $40/月 | <YOUR_PLUS_EMAIL_A> + <YOUR_PLUS_EMAIL_B> |
| 域名 | ~¥60/年 | 任选一个你拥有的域名 |
| ChatGPT Pro（未来） | $200/月 | 高端模型 |

---

## 历史

完整变更记录见 `TODO.md`。
