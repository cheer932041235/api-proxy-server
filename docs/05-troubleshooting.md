# ★ 故障速查

> 最后更新：2026-05-23

## 快速诊断流程

```
服务不可用?
    ├─ SSH 能连上 VPS 吗?
    │   └─ 不能 → 检查代理 / VPS 控制台 / 是否欠费
    ├─ Docker 容器在运行吗?  docker ps
    │   └─ 容器 Exited → docker start <name>
    ├─ Nginx 在运行吗?  systemctl status nginx
    │   └─ 不在 → systemctl start nginx
    ├─ 端口能访问吗?  curl -I http://localhost:PORT
    │   └─ 不能 → 检查防火墙 / iptables
    └─ API 返回错误?
        ├─ 401/403 → Token 过期，见 04-token-renewal.md
        ├─ 502/504 → 后端容器挂了或超时
        └─ 429 → 速率限制，等待或扩号池
```

---

## 常见问题

### 1. Docker 重启后外部访问失效

**现象**：所有 Docker 容器端口从外部无法访问，SSH 正常

**原因**：Docker daemon 重启后未正确注入 iptables FORWARD 规则

**修复**：
```bash
# 手动修复
iptables -I FORWARD 2 -o docker0 -j DOCKER 2>/dev/null || true
iptables -I FORWARD 2 -o docker0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 2 -i docker0 ! -o docker0 -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 2 -i docker0 -o docker0 -j ACCEPT 2>/dev/null || true
```

**已有自动修复**：`fix-docker-iptables.service`（systemd，开机自动执行）

```bash
# 检查 systemd service 状态
systemctl status fix-docker-iptables
```

---

### 2. chatgpt2api 返回 401 / Token 过期

**现象**：API 调用返回 401 Unauthorized 或 "token expired"

**原因**：chatgpt2api 的 access_token 约 10 天过期，不支持自动续期

**修复**：按 [04-token-renewal.md](04-token-renewal.md) 中 chatgpt2api 续期步骤操作

**快速检查**：
```bash
# 查看号池状态
curl -s http://localhost:3002/api/accounts \
  -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' | python3 -c "
import json, sys, base64, time
data = json.load(sys.stdin)
for acc in data.get('items', []):
    email = acc.get('email', '?')
    token = acc.get('access_token', '')
    if token:
        try:
            payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
            hrs = (payload.get('exp', 0) - time.time()) / 3600
            print(f'{email}: {hrs:.1f}h 剩余')
        except: print(f'{email}: token 解析失败')
    else:
        print(f'{email}: 无 token')
"
```

---

### 3. codex-proxy 账号异常

**现象**：Codex CLI 返回错误，管理面板显示 status ≠ active

**修复**：
1. 打开 http://<YOUR_VPS_IP>:8080
2. 点击 **"刷新过期"**（有 refreshToken 时自动续）
3. 失败则点 **"+ 添加账户"** 走 OAuth 重新登录

**查看错误日志**：
```bash
tail -20 /root/codex-proxy/data/error-log.jsonl | python3 -m json.tool
```

---

### 4. Nginx 502 Bad Gateway

**现象**：访问 HTTPS 端点返回 502

**可能原因**：
- 对应的后端容器没有运行
- 容器启动中尚未就绪
- 端口映射配置错误

**排查**：
```bash
# 检查容器状态
docker ps -a

# 检查对应端口是否监听
ss -tlnp | grep -E '3001|3002|8080|8088|8089'

# 检查 Nginx 错误日志
tail -20 /var/log/nginx/error.log
```

---

### 5. Nginx 504 Gateway Timeout

**现象**：长时间请求（如 Codex 大模型推理）返回 504

**原因**：Nginx `proxy_read_timeout` 默认 60s，不够

**修复**：检查 Nginx 配置中对应 location 的超时设置：
```nginx
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

详见 [06-network-tuning.md](06-network-tuning.md)

---

### 6. AI Studio 出图失败

**现象**：配图工具返回错误或超时

**排查**：
```bash
# image-gen 容器日志
docker logs image-gen --tail 30

# 直接测试 chatgpt2api 出图
curl -s -X POST http://localhost:3002/v1/images/generations \
  -H "Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2","prompt":"a red circle","size":"1024x1024"}'
```

**常见原因**：
- chatgpt2api token 过期 → 续期
- 速率限制（6 次/5 分钟/IP）→ 等待
- `host.docker.internal` 解析失败 → 检查 `--add-host` 参数

---

### 7. New-API 数据库相关

**注意**：New-API 数据库文件名是 `one-api.db`（不是 `new-api.db`）

```bash
# 数据库路径
ls -lh /root/new-api-data/one-api.db

# 备份数据库
cp /root/new-api-data/one-api.db /root/backups/one-api-$(date +%Y%m%d).db
```

---

### 8. chatgpt2api Pool-A 偶尔 400

**现象**：Pool-A（<YOUR_PLUS_EMAIL_A>）偶尔返回 400 错误

**状态**：观察中，Pool-B 兜底不影响使用

**排查**：
```bash
docker logs chatgpt2api --tail 100 | grep -i "400\|error\|pool-a"
```

---

### 9. SSH 连接超时

**原因**：VPS 在硅谷，直连可能超时

**解决**：通过 Clash HTTP 代理连接（已在 `~/.ssh/config` 配置）：
```
Host vps
  HostName <YOUR_VPS_IP>
  User root
  ProxyCommand "C:/Program Files/Git/mingw64/bin/connect.exe" -H 127.0.0.1:7897 %h %p
```

确保 Clash 代理运行在 `127.0.0.1:7897`。

---

### 10. codex-proxy 面板"X 条错误"是不是出问题了？

**现象**：打开 `http://<YOUR_VPS_IP>:8080` → 错误页签红色提示几十条错误

**别紧张**：codex-proxy 把所有"非 200 响应"和"流中断"都记进面板，**绝大多数是正常背景噪音**，不是 bug。

#### 三类错误：哪些可以忽略，哪些要处理

| 错误类型 | 含义 | 是否要修 | 触发原因 |
|---------|------|---------|----------|
| `StreamClientAbort` | 客户端主动中止流 | ❌ 忽略 | 用户点了"停止生成" / Ctrl+C / 客户端断网 |
| `StreamUpstreamPrematureClose` (code=1006) | 上游 SSE 流提前关闭 | ⚠️ 偶发可忽略 | 海外 VPS → OpenAI 链路抖动 / OpenAI 端短暂故障 |
| `RefreshFailed` / `OAuthError` / `401` | 账号 token 异常 | ✅ **必须修** | refresh token 过期或被吊销，需重新 OAuth |
| `429 RateLimited` | 单账号被限流 | ⚠️ 看频率 | 请求太密；账号越多越稳，详见 [04-token-renewal.md](04-token-renewal.md) |
| `5xx` 上游 5xx 系列 | OpenAI 服务端故障 | ❌ 等几分钟自愈 | OpenAI 自身在掉链子，不是你的问题 |

#### 健康度参考线

```
错误率 = 错误数 / 总请求数

≤ 5%   优秀（海外链路 + SSE 长连接的常态）
5-15%  正常，但建议看下错误分布
> 15%  需要排查（多半是 token 问题或网络严重不稳）
```

如果面板显示 22 条错误 / 591 总请求 = **3.7%**，且都是 `StreamClientAbort` + `StreamUpstreamPrematureClose`，**直接点"全部标记已读"清空就行**，不影响服务。

#### 真正需要警觉的信号

- 错误率突然从 < 5% 飙到 > 30%
- 出现 `RefreshFailed` 或 `401`（说明 token 出问题）
- 同一个 `accountEntryId` 反复触发 `429`（号池不够用了）
- `日志` 页签里看到大量同一个 `responseId` 重试

收到这些再去排查，否则面板红字就是"健康监控的副作用"，不要被吓到。

---

### 11. codex-proxy 面板"图像请求 0/N failed"是怎么回事

**现象**：用量统计页签里"图像生成请求"显示 `0 / 671`，全部失败。但你主要用 Codex 写代码，没主动生成过图。

**别紧张**：这是统计口径问题，**不是你的服务在反复出错**。

#### 数据来源（关键理解）

codex-proxy dashboard 上的图像统计**不是它自己处理的请求**，而是它定期从 **OpenAI 账号级 usage API** 拉取的：

```
codex-proxy dashboard
    ↑ 拉取
OpenAI 账号 usage API（返回 image_request_failed_count）
    ↑ 计数
该 Plus 账号在 OpenAI 端的所有图像请求（合并统计）
```

也就是说：**只要这个 Plus 账号被任何客户端（包括 chatgpt2api、ChatGPT 网页、其他第三方工具）发过图像请求，OpenAI 端的计数都会累加，并最终显示在 codex-proxy 面板上。**

#### 为什么计数会飙这么高

如果你部署了本仓库的 `image-gen` 工具，它默认使用 **双 Pool 并发策略**：同一张图同时让 Pool-A 和 Pool-B 两个账号去生成，谁先返回用谁，另一个被取消。

```
image-gen 收到 1 个出图请求
   ├─→ Pool-A (账号 A) 调用 /v1/images/edits
   └─→ Pool-B (账号 B) 调用 /v1/images/edits
       │
       ├─ Pool-A 31s 返回成功 ✅ → 用户拿到图
       └─ Pool-B 36s 返回成功（已被取消） ← OpenAI 端计 1 次失败
```

**用户视角**：100% 出图成功
**OpenAI 账号视角**：每张图算 1 次成功 + 1 次"失败"（被取消的那个）
**codex-proxy 面板视角**：只看到累计的失败数

#### 怎么判断是不是这个原因

1. 看 `chatgpt2api` 容器日志，`/v1/images/edits` 是不是大量 200 OK：
   ```bash
   docker logs chatgpt2api --since 24h 2>&1 | grep -c '/v1/images/edits.*200'
   ```
2. 看 `image-gen` 容器日志里 `[GEN-Pool-A]` 和 `[GEN-Pool-B]` 是否成对出现（双发模式）：
   ```bash
   docker logs image-gen --since 24h 2>&1 | grep -E '\[GEN-Pool-[AB]\]' | tail -20
   ```
3. 看 `codex-proxy` 自己的请求路径分布：
   ```bash
   docker logs codex-proxy-codex-proxy-1 --since 24h 2>&1 | grep -oE 'POST /v1/[a-z_/]+' | sort | uniq -c
   ```
   正常情况只会看到 `POST /v1/responses`，**不会**看到 `POST /v1/images/*`。

如果三项都符合 → 就是双 Pool 并发的"统计副作用"，**忽略即可**。

#### 想消除这个数字怎么办

两个选项，按需选：

| 方案 | 优点 | 代价 |
|------|------|------|
| **保留双 Pool 并发（默认）** | 单图最快，用户体验最好 | OpenAI 账号端虚高失败计数 |
| 改成主备模式（Pool-A 先试，超时再 Pool-B） | 账号端数字干净 | 单图最坏情况慢 30s+ |

**推荐保留默认**：用户拿到图的速度比面板上一个无害的数字重要。

---

## 日志位置速查

| 日志 | 路径 | 说明 |
|------|------|------|
| Nginx access | `/var/log/nginx/access.log` | 通用访问日志 |
| Nginx error | `/var/log/nginx/error.log` | 错误日志 |
| Codex access | `/var/log/nginx/codex.access.log` | JSON 格式，含 model 字段 |
| codex-proxy error | `/root/codex-proxy/data/error-log.jsonl` | refresh/auth 错误 |
| Docker 容器 | `docker logs <name>` | 各服务自身日志 |
| 备份日志 | `/var/log/daily-backup.log` | 每日备份执行记录 |
| 报告日志 | `/var/log/daily-report.log` | 每日报告发送记录 |
| 健康检查 | `/var/log/proxy-health.log` | 健康检查执行记录 |
