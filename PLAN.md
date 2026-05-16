# API 中转站 — 资产清单 & 规划文档

> 维护时间：2026-05-15
> 目标：搭建完整的 AI API 中转站，支持自用 + 未来对外服务

---

## 一、现有资产

### 服务器

| 名称 | IP | 地域 | 配置 | 到期 | 用途 |
|------|---|------|------|------|------|
| OpenClaw(龙虾)-4KQB | 170.106.65.175 | 硅谷 | 2核4GB 60GB Ubuntu | 2027-04-07 | 主节点：反代 + 中转 |

**云控制台**: https://console.cloud.tencent.com/lighthouse （腾讯云轻量应用服务器）

### 已部署服务

| 服务 | 端口 | 状态 | 用途 |
|------|------|------|------|
| AIClient-2-API | 3000 | ✅ 运行中 | 免费 OAuth 账号池（Gemini/Kiro/Codex） |
| New-API | 3001 | ✅ 运行中 | API 管理/分发/计费中转站（MikuAPI 同款） |
| chatgpt2api | 3002 | ✅ 运行中 | ChatGPT Plus/Pro 反代（文本 + GPT-Image-2 出图） |
| AI Studio 配图 | 8088 | ✅ 运行中 | GPT-Image-2 双号池并行出图 Web 工具 |

### 账号资产

| 编号 | 邮箱 | 等级 | 号池状态 | 备注 |
|------|------|------|----------|------|
| A | 932041235@qq.com | Plus | ✅ 已导入 | 号池 Pool-A |
| B | cheershuyang@163.com | Plus | ✅ 已导入 | 号池 Pool-B |
| - | 待购买 | Pro ($200/月) | 未来 | 高端模型 o1-pro 等 |

---

## 二、完整架构

```
┌─────────────────────────────────────────────────────────────┐
│              海外 VPS (170.106.65.175)                  │
│                                                             │
│  ┌────────────────┐    ┌────────────────┐              │
│  │  chatgpt2api    │    │  AIClient2API  │              │
│  │  (端口 3002)    │    │  (端口 3000)    │              │
│  │                │    │                │              │
│  │ ChatGPT Plus   │    │ Gemini OAuth   │              │
│  │ ChatGPT Pro(*) │    │ Kiro OAuth     │              │
│  │ GPT-Image-2    │    │ Codex OAuth    │              │
│  └────────┬───────┘    └────────┬───────┘              │
│           │                    │                       │
│           └──────────┬─────────┘                       │
│                    ▼                                      │
│           ┌──────────────────┐                       │
│           │     New-API      │                       │
│           │   (端口 3001)    │                       │
│           │                  │                       │
│           │ • 多渠道聚合     │                       │
│           │ • 负载均衡       │                       │
│           │ • Token 计费     │                       │
│           │ • 用户管理       │                       │
│           │ • API Key 分发   │                       │
│           └────────┬─────────┘                       │
│                    │                                      │
└────────────────────┼─────────────────────────┘
                     │
                     ▼
            ┌──────────────────┐
            │     用户端        │
            │ Cherry Studio    │
            │ Cursor / Windsurf│
            │ 自己 / 朋友 / 客户 │
            └──────────────────┘

(*) 未来购买
```

---

## 三、反代工具对比

主流 GPT 反代方案（Codex 反代 vs 网页反代）：

| 项目 | 类型 | 特点 | 推荐度 |
|------|------|------|--------|
| **[chatgpt2api](https://github.com/basketikun/chatgpt2api)** | 网页反代 | 号池 Web 面板、GPT-Image-2 出图、导入 CPA/sub2api | ⭐ 已部署 |
| [Recodex](https://github.com/adryfish/recodex) | Codex 镜像 | 中转站主流，自动 Token 刷新，故障转移 | ⭐⭐⭐⭐⭐ |
| [codexProapi](https://github.com/violettoolssite/codexProapi) | Codex 反代 | Web 配置面板 + OAuth 登录，多账号轮询 | ⭐⭐⭐⭐ |
| [CLIProxyAPI](https://github.com/luispater/CLIProxyAPI) | 多家统一 | Codex + Claude Code + Gemini CLI 统一代理 | ⭐⭐⭐⭐ |
| [chat2api](https://github.com/lanqian528/chat2api) | 网页反代 | 轻量稳定、多 Token 轮询、官网镜像 | ⭐⭐⭐ |

### 当前选择：chatgpt2api

**选择原因**: 唯一同时支持文本模型 + GPT-Image-2 出图 + 号池管理 Web 面板

**可用模型**:
- 文本: auto, gpt-5, gpt-5-1, gpt-5-2, gpt-5-3, gpt-5-3-mini, gpt-5-5, gpt-5-mini
- 出图: gpt-image-2, codex-gpt-image-2

**未来考虑**: 若需专业 Codex 反代，可加部署 Recodex；若需 Claude/Gemini 反代，可加 CLIProxyAPI

---

## 四、实施路线图

### 第一阶段：自用跑通 ✅

- [x] VPS 部署 New-API (端口 3001)
- [x] VPS 保留 AIClient-2-API (端口 3000)
- [x] 部署 chatgpt2api (端口 3002) — 替换了 chat2api
- [x] 获取 ChatGPT Plus AccessToken 并导入号池
- [x] 文本 API 测试通过 (gpt-5-mini)
- [x] 将 chatgpt2api 作为渠道接入 New-API
- [x] 端到端验证通过（文本 gpt-5-mini ✅ + 出图 gpt-image-2 ✅）
- [x] New-API 开启自用模式
- [x] 导入第 2 个 Plus 账号到号池（cheershuyang@163.com）
- [ ] 本地工具 (Cherry Studio 等) 接入

### 第二阶段：稳定运营

- [ ] 配置域名 + HTTPS (Nginx 反代)
- [ ] 设置模型定价倍率
- [ ] 配置渠道健康监控和自动故障转移
- [ ] 测试稳定性（持续运行 1周+）

### 第三阶段：扩展号池

- [ ] 购买 GPT Pro 账号 → 加入 chatgpt2api 号池
- [ ] 购买更多 Plus 账号 → 多账号轮询
- [ ] 加部署 Recodex (Codex 专用反代) 或 CLIProxyAPI (多家)
- [ ] 开放用户注册 + 充值体系（如需对外）

---

## 五、关键操作记录

### New-API 管理后台

- 地址: http://170.106.65.175:3001
- 账号: `root` / `Proxy2026!`
- 模式: 自用模式已开启

### chatgpt2api → New-API 渠道配置（已完成）

| 配置项 | 值 |
|--------|----|
| 渠道类型 | OpenAI (type=0) |
| 渠道名称 | chatgpt2api |
| 代理地址 | `http://172.17.0.1:3002` (Docker 内网) |
| 密钥 | `sk-gpt2api-secret` |
| 模型 | gpt-5, gpt-5-mini, gpt-5-5, gpt-5-1, gpt-5-2, gpt-5-3, gpt-5-3-mini, gpt-image-2, codex-gpt-image-2 |

### 客户端接入

```
API Base URL: http://170.106.65.175:3001/v1
API Key:      sk-MxTbv9KDEiD4OXTJgZ7pO6RgbmnVmUPs3PCiXpFqfcWsi8OL
```

### 端口分配 & 云防火墙

| 端口 | 服务 | 状态 | 云防火墙 |
|------|------|------|----------|
| 22 | SSH | ✅ | ✅ 已放行 |
| 3000 | AIClient-2-API | ✅ 运行中 | ✅ 已放行 |
| 3001 | New-API | ✅ 运行中 | ✅ 已放行 |
| 3002 | chatgpt2api | ✅ 运行中 | ✅ 已放行 |
| 1455 | AIClient-2-API 服务端口 | ✅ | ✅ 已放行 |
| 8088 | AI Studio 配图 | ✅ 运行中 | ✅ 已放行 |
| 8085-8086 | TLS Sidecar | ✅ | ✅ 已放行 |
| 19876-19880 | AIClient-2-API 数外端口 | ✅ | ✅ 已放行 |
| ICMP | Ping | ✅ | ✅ 已放行 |

> ⚠️ 说明：云控制台防火墙 ≠ VPS 内部 iptables，**两层都要放行**才能外部访问

---

## 六、成本估算

| 项目 | 月费用 | 说明 |
|------|--------|------|
| VPS 硅谷 | ~¥50/月 | 已付到2027年 |
| ChatGPT Plus ×2 | $40/月 | 932041235@qq.com + cheershuyang@163.com |
| ChatGPT Pro (未来) | $200/月 | 高端模型o1-pro等 |
| 域名 (可选) | ~¥60/年 | HTTPS + 品牌 |

---

## 七、运维指南

### 数据持久化路径

| 服务 | VPS 路径 | 内容 |
|------|----------|------|
| New-API | /root/new-api-data | SQLite DB、配置 |
| chatgpt2api | /root/chatgpt2api-data | 号池账号 JSON |
| AIClient-2-API | Docker 内置 | OAuth 账号 |

### Docker 容器管理

```bash
# 查看所有容器
docker ps -a

# 重启单个服务
docker restart chatgpt2api
docker restart new-api
docker restart aiclient2api

# 查看日志
docker logs chatgpt2api --tail 50
docker logs new-api --tail 50

# 更新容器（以 chatgpt2api 为例）
docker pull ghcr.io/basketikun/chatgpt2api:latest
docker stop chatgpt2api && docker rm chatgpt2api
# 重新运行 docker run 命令（数据已持久化）
```

### 号池管理

```bash
# 查看所有账号状态和额度
curl -s http://localhost:3002/api/accounts \
  -H 'Authorization: Bearer sk-gpt2api-secret' | python3 -m json.tool

# 导入新 Token
curl -s -X POST http://localhost:3002/api/accounts \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-gpt2api-secret' \
  -d '{"tokens": ["ACCESS_TOKEN_HERE"]}'
```

### 注意事项

1. **Token 安全**: AccessToken 泄露 = 账号被盗，必须妥善保管
2. **使用频率**: Plus 有速率限制，号池越多越稳定
3. **IP 风险**: 单 IP 大量请求可能触发 OpenAI 风控，必要时加代理轮换
4. **备份**: 定期备份 /root/new-api-data 和 /root/chatgpt2api-data
5. **更新**: chatgpt2api 和 New-API 需定期拉取最新镜像以适配 OpenAI 变化
8. **AI Studio**: 配图服务限速 6次/5分钟/IP，缓存 5 分钟自动清理
6. **云防火墙**: 新增端口需同时在腾讯云控制台 + VPS iptables 放行
7. **Docker 重启**: Docker daemon 重启后可能需手动补 FORWARD 链规则（见第八节）

---

## 七(b)、缓存架构

| 路径 | 缓存机制 | 状态 |
|------|----------|------|
| Codex CLI → codex-proxy:8080 → OpenAI | prompt_cache_key + SessionAffinity → 服务端 prompt caching（输入 token 5 折） | ✅ 已内置 |
| 学员文本 API → New-API:3001 → chatgpt2api:3002 | New-API 内存缓存（相同请求直接返回） | ✅ 已开启 (MEMORY_CACHE_ENABLED=true) |
| AI Studio 配图 → chatgpt2api:3002 | 生成结果内存缓存 5 分钟 | ✅ 已实现 |
| chatgpt2api 自身 | 无 prompt caching 支持 | ❌ 已知限制 |

**关键概念**: OpenAI 服务端 Prompt Caching 要求同一会话的请求路由到同一账号（sticky session）且传递 `prompt_cache_key`。codex-proxy 已内置此能力；chatgpt2api 作为网页反代不支持。

---

## 八、已知问题 & 解决方案

### Docker FORWARD 链规则丢失

**现象**: 外部无法访问 Docker 容器端口，SSH 正常
**原因**: Docker daemon 重启后未正确注入 iptables FORWARD 规则
**修复**:
```bash
iptables -I FORWARD 2 -o docker0 -j DOCKER
iptables -I FORWARD 2 -o docker0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -I FORWARD 2 -i docker0 ! -o docker0 -j ACCEPT
iptables -I FORWARD 2 -i docker0 -o docker0 -j ACCEPT
```

---

## 九、AI Studio 配图工具

### 功能
- 双号池（Pool-A/B）并行调用 GPT-Image-2，一次生成两张图
- 智能增强（LLM 润色 prompt）+ 7 种风格预设 + 5 种尺寸
- 答题解锁（课程老师是？→ 疏锦行），localStorage 持久
- 速率限制 6 次/5分钟/IP，请求体上限 10KB
- 图片缓存 5 分钟自动清理
- 图到图编辑（上传参考图，4MB 限制）
- 过期提示横幅 + 浏览器缓存治理

### 部署
```bash
cd /root/image-gen
docker build -t image-gen .
docker run -d --name image-gen --restart unless-stopped \
  -p 8088:8088 \
  --add-host=host.docker.internal:host-gateway \
  image-gen
```

### 更新
```bash
# 本地修改后 SCP 上传
scp image-gen/* vps:/root/image-gen/
# VPS 重建
ssh vps "docker stop image-gen && docker rm image-gen && cd /root/image-gen && docker build -t image-gen . && docker run -d --name image-gen --restart unless-stopped -p 8088:8088 --add-host=host.docker.internal:host-gateway image-gen"
```
