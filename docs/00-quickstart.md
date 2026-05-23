# 快速开始（30 分钟跑通）

> 目标：把空白 VPS 变成一个能用 Codex CLI / Cherry Studio 的 AI 中转站。

## 前置条件

- 一台**海外 VPS**（推荐配置：2C 4GB 60GB，Ubuntu 22.04+）
- 一个**域名**已解析到 VPS 的公网 IP
- 至少 **1 个 ChatGPT Plus** 账号（推荐 ≥2 个轮询）
- 本机能 SSH 到 VPS（建议在 `~/.ssh/config` 起别名）

## 第一步：本地准备（3 分钟）

```bash
# 克隆仓库到本机
git clone https://github.com/cheer932041235/api-proxy-server.git
cd api-proxy-server

# 配置环境变量
cp .env.example .env
vim .env                              # 至少改这几个：
                                      #   VPS_HOST=你的VPS的IP
                                      #   VPS_USER=root
                                      #   DOMAIN=你的域名
                                      #   SSL_EMAIL=你的邮箱
                                      #   各种 ChangeMe_* 改成强随机值
```

### SSH 别名（可选但推荐）

```bash
# 在 ~/.ssh/config 添加
Host vps
  HostName <YOUR_VPS_IP>
  User root
  # 国内访问海外 VPS 慢的话加代理
  # ProxyCommand "C:/Program Files/Git/mingw64/bin/connect.exe" -H 127.0.0.1:7897 %h %p
```

## 第二步：VPS 首次安装（10 分钟）

```bash
# 在本地仓库目录执行
make setup
```

`setup.sh` 会做的事：
1. 在 VPS 安装 Docker、Nginx、certbot、msmtp
2. 创建数据目录（`/root/new-api-data` 等）
3. 申请 Let's Encrypt SSL 证书
4. 渲染并安装 Nginx 配置（基于 `.env`）
5. 安装 Docker iptables 自动修复 systemd
6. 安装每日备份/报告 cron

**手动等价命令**（如果不想用脚本）：

```bash
ssh vps "apt update && apt install -y docker.io docker-compose nginx certbot python3-certbot-nginx msmtp"
ssh vps "mkdir -p /root/{new-api-data,chatgpt2api-data,codex-proxy/data,backups}"
ssh vps "certbot --nginx -d <YOUR_DOMAIN> --email <YOUR_EMAIL> --agree-tos --non-interactive"
```

## 第三步：部署服务（5 分钟）

```bash
make deploy
```

会启动 4 个 Docker 容器：

```bash
# 等价的手动命令（VPS 上执行）

# 1. New-API 网关
docker run --name new-api -d --restart always \
  -p 3001:3000 -e TZ=Asia/Shanghai -e MEMORY_CACHE_ENABLED=true \
  -v /root/new-api-data:/data \
  calciumion/new-api:latest

# 2. chatgpt2api 反代
docker run -d --name chatgpt2api --restart unless-stopped \
  -p 3002:80 \
  -v /root/chatgpt2api-data:/app/data \
  -e CHATGPT2API_AUTH_KEY=<YOUR_CHATGPT2API_AUTH_KEY> \
  -e STORAGE_BACKEND=json \
  ghcr.io/basketikun/chatgpt2api:latest

# 3. codex-proxy 反代
docker run -d --name codex-proxy --restart unless-stopped \
  -p 8080:8080 -p 1457:1455 \
  -v /root/codex-proxy/data:/app/data \
  ghcr.io/icebear0828/codex-proxy:latest

# 4. image-gen 配图工具（需先 scp 源码）
cd /root/image-gen && docker build -t image-gen .
docker run -d --name image-gen --restart unless-stopped \
  -p 8088:8088 \
  --add-host=host.docker.internal:host-gateway \
  image-gen
```

## 第四步：导入 ChatGPT Plus 账号（5 分钟）

详见 [04-token-renewal.md](04-token-renewal.md)。简版：

### codex-proxy 走 OAuth

1. 浏览器访问 `http://<YOUR_VPS_IP>:8080`
2. 点 **"+ 添加账户"** → 跳转 OpenAI 登录
3. 登录后复制 `localhost:1457` 回调 URL 粘贴回 dashboard

### chatgpt2api 走 access_token

1. 浏览器登录 `chat.openai.com`
2. 同浏览器访问 `https://chat.openai.com/api/auth/session`
3. 复制 `accessToken` 字段
4. 在本机执行：
   ```bash
   ssh vps "curl -X POST http://localhost:3002/api/accounts \
     -H 'Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>' \
     -H 'Content-Type: application/json' \
     -d '{\"tokens\":[\"YOUR_ACCESS_TOKEN_HERE\"]}'"
   ```

## 第五步：在 New-API 配置渠道（5 分钟）

1. 浏览器打开 `https://<YOUR_DOMAIN>` → 用 `.env` 中的 `NEW_API_ADMIN_USER` / `NEW_API_ADMIN_PASS` 登录
2. 进入 **渠道** → **添加渠道**：
   - 类型：`OpenAI`
   - 名称：`chatgpt2api`
   - 代理地址：`http://172.17.0.1:3002`（Docker 内网）
   - 密钥：`<YOUR_CHATGPT2API_AUTH_KEY>`（与 .env 同步）
   - 模型：`gpt-5, gpt-5-mini, gpt-5-5, gpt-image-2, codex-gpt-image-2`
3. 进入 **令牌** → 创建一个供你客户端用的 API Key
4. 在 Cherry Studio / ChatBox 配置：
   - Base URL: `https://<YOUR_DOMAIN>/v1`
   - API Key: 上一步创建的令牌

## 第六步：验证（2 分钟）

```bash
# 测试文本（通过 New-API）
curl -s https://<YOUR_DOMAIN>/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"hi"}]}' | jq

# 测试 Codex Proxy（Responses API）
curl -s https://<YOUR_DOMAIN>/codex/v1/responses \
  -H "Authorization: Bearer pwd" \
  -H "Content-Type: application/json" \
  -d '{"model":"o3","input":"hello","stream":false}' | jq

# 测试出图
curl -s -X POST https://<YOUR_DOMAIN>/img/v1/images/generations \
  -H "Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2","prompt":"a red circle","size":"1024x1024"}'
```

## 接下来做什么

- [日常运维](03-operations.md) — 重启、看日志、备份
- [Token 续期 SOP](04-token-renewal.md) — chatgpt2api 每 ~10 天要手动续
- [故障速查](05-troubleshooting.md) — 502 / 401 / 超时怎么办
- [链路稳定性](06-network-tuning.md) — Codex 长请求超时调优

## 常见首次部署问题

| 问题 | 解决 |
|------|------|
| `make: command not found`（Windows） | 装 [GnuWin32 make](https://gnuwin32.sourceforge.net/packages/make.htm) 或用 Git Bash |
| SSH 连不上 VPS | 检查云控制台防火墙是否放行 22；国内访问海外加代理 |
| Let's Encrypt 失败 | 域名必须先解析到 VPS_HOST 且 80 端口可访问 |
| Docker 拉镜像慢 | VPS 上设置镜像加速器，或用本地拉好后 `docker save` + `scp` |
| Nginx 502 Bad Gateway | 检查容器是否启动 `docker ps`，端口是否监听 `ss -tlnp` |
| Codex CLI 401 | API Key 不对，确认是 `.env` 中的 `CODEX_PUBLIC_KEY` |
