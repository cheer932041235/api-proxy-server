# TODO & 变更日志

> 最后更新：2026-05-23

## 待做

### P0 — 近期
- [ ] 学员客户端接入图文教程（Cherry Studio / ChatBox）

### P1 — 中期
- [ ] 模型定价倍率配置
- [ ] 渠道健康监控 + 自动故障转移
- [ ] 学员额度批量充值脚本（>5 人时做）

### P2 — 长期
- [ ] 接入 Claude / Gemini 渠道
- [ ] 账号池扩容（更多 Plus / Pro）
- [ ] 计费体系（按模型差异化定价）

---

## 已完成

- [x] chatgpt2api 部署 + 双 Plus 号池（<YOUR_PLUS_EMAIL_A>、<YOUR_PLUS_EMAIL_B>）
- [x] New-API 部署 + 渠道配置 + 用户体系 + SMTP 邮件
- [x] codex-proxy 部署（Responses API + OAuth 自动续期 + prompt caching）
- [x] image-gen / AI Studio 配图工具（双号池并行 GPT-Image-2，答题解锁）
- [x] codex-log-viewer 日志面板（Nginx JSON log + Flask）
- [x] HTTPS + 域名（<YOUR_DOMAIN>，Let's Encrypt）
- [x] 云防火墙放行 + Docker iptables 自动修复 systemd
- [x] 数据自动备份（cron 02:00，保留 7 天）
- [x] 每日 Token 报告（cron 09:00 → <YOUR_PLUS_EMAIL_A>）
- [x] 账号健康检查 + 异常告警（cron 09:00 → <YOUR_ALERT_EMAIL>）
- [x] 项目文档重构：README + docs/（架构 / 运维 / 续期 / 故障 / 调优）+ services/X/README.md
- [x] 退役 aiclient2api 和 Claude Desktop 网关（2026-05-23）

---

## 已知问题

| 问题 | 解决方案 | 状态 |
|------|----------|------|
| Docker 重启后外部访问失效 | systemd 自动修复 | ✅ 已解决 |
| New-API DB 文件名是 `one-api.db` | 备忘：用 `one-api.db` 不是 `new-api.db` | 已记录 |
| chatgpt2api Pool-A 偶尔 400 | Pool-B 兜底，不影响 | 观察中 |
| chatgpt2api 不支持 Token 自动续 | 手动 ~10 天续一次（健康检查提前 3 天告警） | 已知限制 |

详细排查见 `docs/05-troubleshooting.md`。

---

## 学员使用方式

### 方式一：网页聊天
1. 浏览器打开 https://<YOUR_DOMAIN>
2. 邮箱注册 → 管理员分配额度 → "令牌"页面聊天

### 方式二：API 客户端
- API Base: `https://<YOUR_DOMAIN>/v1`
- API Key: 自己的令牌
- 模型: gpt-5-mini / gpt-5 等

### 方式三：AI 配图
- 地址: https://<YOUR_DOMAIN>/studio/
- 答题解锁后即可使用

---

## 变更日志

### 2026-05-23
- 项目结构重组：所有服务移到 `services/`，文档移到 `docs/`
- 退役 `aiclient2api`（端口 3000，已备份至 `/root/_archive/aiclient2api-20260523`）
- 退役 Claude Desktop 网关（gateway/ 目录全部清理）
- 重写 README.md，新增 6 篇 docs/ 文档
- 每个 services/X/ 下创建 README.md
- scripts/README.md 整理运维脚本

### 2026-05-19
- codex-proxy + 日志面板上线（Responses API + prompt caching + Nginx JSON log）
- 添加 codex-proxy 健康检查脚本

### 2026-05-16
- HTTPS + 域名（<YOUR_DOMAIN>，Nginx + Let's Encrypt）
- Docker iptables 自动修复 systemd
- 每日数据备份 + 每日 Token 报告 + msmtp
- 清理旧版 Flask proxy 代码
- 加速率限制（6 次/5 分钟/IP）+ 请求体上限（10KB）
- AI Studio 图到图编辑 + 缓存缩短 + 速率限制器清理
- 开启 New-API 内存缓存（`MEMORY_CACHE_ENABLED=true`）

### 2026-05-15
- 部署 AI Studio 配图工具（双号池并行 GPT-Image-2，答题解锁）
- 修复 502 错误（print lambda 多线程不安全 → 改 logging）
