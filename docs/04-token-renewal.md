# ★ Token 续期 SOP

> 最后更新：2026-05-23
> 这是最常需要的运维操作，务必熟悉。

## 概览

| 服务 | 续期方式 | 频率 | 紧急程度 |
|------|----------|------|----------|
| **codex-proxy** | OAuth refresh_token 自动刷新 | 自动（无需干预） | 低 — 仅 refreshToken 丢失时需手动 |
| **chatgpt2api** | 手动获取 access_token 并导入 | ~每 10 天 | 高 — 过期后服务不可用 |

---

## codex-proxy 续期（通常自动）

### 正常情况：无需操作

codex-proxy 使用 OAuth 机制，拥有 `refreshToken` 的账号会自动续期 `accessToken`。

### 异常情况：refreshToken 丢失 / 账号状态异常

**症状**：健康检查告警 `缺少 refreshToken` 或 `access_token 已过期`

**修复步骤**：

1. 打开 codex-proxy 管理面板：http://<YOUR_VPS_IP>:8080
2. 点击 **"刷新过期"** 按钮（如果有 refreshToken 会自动续）
3. 如果刷新失败，点击 **"+ 添加账户"** 走 OAuth 流程：
   - 浏览器会跳转到 OpenAI 登录页
   - 登录后会重定向到 `localhost:1455` 回调 URL
   - **注意**：需要复制 `localhost:1455` 的完整回调 URL 粘贴回 codex-proxy dashboard
4. 验证：管理面板显示 status = `active`，refreshToken 存在

### 查看账号状态

```bash
# 在 VPS 上直接查看
cat /root/codex-proxy/data/accounts.json | python3 -m json.tool

# 检查 JWT 过期时间
python3 -c "
import json, base64, time
data = json.load(open('/root/codex-proxy/data/accounts.json'))
for acc in data.get('accounts', []):
    token = acc.get('token', '')
    if token:
        payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
        exp = payload.get('exp', 0)
        hrs = (exp - time.time()) / 3600
        print(f'{acc.get(\"email\", \"?\")} → {hrs:.1f}h 后过期, refreshToken={bool(acc.get(\"refreshToken\"))}')
"
```

---

## chatgpt2api 续期（手动，重要！）

### 什么时候需要续期？

- access_token 有效期约 **10 天**
- 健康检查会提前 **3 天**告警
- 告警邮件标题含 `⏰ [chatgpt2api]`

### 第一步：获取 access_token

> 需要用 **浏览器** 操作，VPN 连美国节点效果更好。

1. 打开 https://chat.openai.com 并**登录**（每个账号分别操作）
2. 登录成功后，在**同一浏览器**新标签页访问：
   ```
   https://chat.openai.com/api/auth/session
   ```
3. 页面返回 JSON，复制其中 `accessToken` 字段的值（很长的一串）

### 第二步：导入到号池

```bash
# SSH 到 VPS
ssh vps

# 导入 Token（替换 YOUR_ACCESS_TOKEN）
curl -s -X POST http://localhost:3002/api/accounts \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' \
  -d '{"tokens": ["YOUR_ACCESS_TOKEN"]}'

# 验证导入成功
curl -s http://localhost:3002/api/accounts \
  -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' | python3 -m json.tool
```

### 第三步：验证

```bash
# 测试文本 API
curl -s https://<YOUR_DOMAIN>/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_NEW_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

### 两个账号都要续

| 账号 | 邮箱 | 说明 |
|------|------|------|
| Pool-A | <YOUR_PLUS_EMAIL_A> | Plus |
| Pool-B | <YOUR_PLUS_EMAIL_B> | Plus |

> 分别登录 → 分别获取 accessToken → 分别导入。两个账号的 token 可以**一次性**导入：
> ```bash
> curl -s -X POST http://localhost:3002/api/accounts \
>   -H 'Content-Type: application/json' \
>   -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' \
>   -d '{"tokens": ["TOKEN_A", "TOKEN_B"]}'
> ```

---

## 号池去重

如果多次导入同一账号（例如续期时），号池可能出现重复条目。

```bash
# 上传去重脚本
scp scripts/dedup-accounts.py vps:/tmp/

# 执行去重（自动备份 + 保留最新过期时间的条目）
ssh vps "python3 /tmp/dedup-accounts.py"

# 重启 chatgpt2api 使其重新读取
ssh vps "docker restart chatgpt2api"
```

---

## 告警配置

健康检查脚本 `proxy-health-check.py` 在 VPS 上以 cron 运行：

```bash
# cron 配置
0 9 * * * QQ_SMTP_PASS=xxx /usr/bin/python3 /root/codex-proxy/scripts/proxy-health-check.py >> /var/log/proxy-health.log 2>&1
```

告警阈值：
- codex-proxy JWT 剩余 < **24 小时**（且无 refreshToken）
- chatgpt2api JWT 剩余 < **3 天**
- codex-proxy error-log 最近 **24 小时**内有 refresh/auth 相关错误

告警邮件发送到：`<YOUR_ALERT_EMAIL>`（QQ SMTP）
