# API 中转站 — 维护记录

> 最后更新：2026-05-16

---

## 已完成

- [x] chatgpt2api 部署 + 双 Plus 账号号池
- [x] New-API 部署 + 渠道配置
- [x] 云防火墙放行（3000/3001/3002/8088）
- [x] 关闭自用模式，启用正式用户体系
- [x] 管理员无限额度
- [x] SMTP 邮件服务（注册验证码 + 找回密码）
- [x] 注册功能开放（邮箱验证）
- [x] 网页端聊天功能（New-API 内置）
- [x] AI Studio 配图工具（双号池并行 GPT-Image-2，答题解锁 + 限速）
- [x] 代码整理：移除旧版 Flask proxy 死代码，统一文档
- [x] 图到图编辑（上传参考图 → /v1/images/edits，4MB 限制）
- [x] 图片缓存缩短至 5 分钟 + 过期提示横幅 + 速率限制器内存清理
- [x] 测试用例 tests.py（10 组 14 项，quick/full 两种模式）
- [x] 浏览器缓存治理（no-cache meta + CSS/JS 版本号）

---

## 待做

### P0 — 近期

- [x] **子域名 + HTTPS + 品牌化**
  - api.shujinxing777.com → Nginx 反代 + Let's Encrypt
  - 证书自动续期（certbot timer）

- [ ] **本地客户端接入指南**
  - 给学员写图文教程，配置 Cherry Studio / ChatBox

### P1 — 中期

- [ ] **学员额度管理**：批量充值脚本，学员超 5 人时做
- [ ] **服务健康监控**：healthcheck 脚本 + 异常告警
- [x] **数据自动备份**：cron 每日 02:00 备份，保留 7 天
- [x] **每日 Token 报告**：cron 09:00 发送到 932041235@qq.com
- [x] **Docker iptables 自动修复**：systemd service，开机自动补规则

### P2 — 长期

- [ ] **更多模型渠道**：Claude / Gemini 接入
- [ ] **账号池扩容**：更多 Plus/Pro 账号
- [ ] **计费体系**：按模型差异化定价

---

## 已知问题

| 问题 | 解决方案 | 状态 |
|------|----------|------|
| Docker 重启后外部访问失效 | systemd service 自动修复 | ✅ 已解决 |
| New-API 数据库文件是 one-api.db | 记住用 one-api.db 不是 new-api.db | 已记录 |
| chatgpt2api Pool-A 偶尔 400 | Pool-B 兜底，不影响使用 | 观察中 |

---

## 变更日志

### 2026-05-16
- **HTTPS + 域名**: api.shujinxing777.com，Nginx 反代 + Let's Encrypt SSL
- **Docker iptables 自动修复**: systemd service，开机自动补 FORWARD 规则
- **每日数据备份**: cron 02:00，保留 7 天
- **每日 Token 报告**: cron 09:00，邮件发送 codex-proxy 用量 + Docker 状态 + 磁盘信息
- 清理旧版 Flask proxy 代码（proxy/、scripts/、configs/、根 Dockerfile）
- server.py: print lambda → logging 模块，加全局异常捕获
- server.py: 加速率限制（6次/5分钟/IP）、请求体上限（10KB）
- script.js: XSS 防护（escapeHtml）、clipboard HTTP 兼容
- style.css: 清理 .preview-img/.revised-box 死样式
- AI Studio 图到图编辑 + 缓存缩短至 5 分钟 + 速率限制器清理
- **开启 New-API 内存缓存** (MEMORY_CACHE_ENABLED=true)
- 缓存架构调研：codex-proxy 已内置 prompt_cache_key + sticky session
- PLAN.md 添加缓存架构章节，修正过时信息
- 更新 README/PLAN/TODO 文档

### 2026-05-15
- 部署 AI Studio 配图工具（双号池并行 GPT-Image-2）
- 实现答题解锁、风格/尺寸选择、智能增强、历史记录
- 修复 502 错误（print lambda 多线程不安全）

---

## 学员使用方式

### 方式一：网页聊天
1. 浏览器打开 https://api.shujinxing777.com
2. 邮箱注册 → 管理员分配额度 → 「令牌」页面聊天

### 方式二：API 客户端
- API Base: `https://api.shujinxing777.com`
- API Key: 自己的令牌
- 模型: gpt-5-mini / gpt-5 等

### 方式三：AI 配图
- 地址: https://api.shujinxing777.com/studio/
- 答题解锁后即可使用
