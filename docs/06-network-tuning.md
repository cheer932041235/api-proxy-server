# ★ 链路稳定性 & 网络调优

> 最后更新：2026-05-23

## 问题背景

Codex CLI / OpenCode 的单次推理可能持续 **数分钟**（大型 repo 上下文 + 高 reasoning effort）。默认的 60s 超时在这种场景下会导致连接中断。

本文档记录了从客户端到 OpenAI 全链路的超时配置。

## 超时全链路

```
Codex CLI / OpenCode
    ↓ (客户端超时)
Nginx (SSL 终端)
    ↓ (proxy_read_timeout)
codex-proxy Docker
    ↓ (应用层超时)
OpenAI API
```

每一层都需要配置足够的超时时间。

## Nginx 配置

文件：`/etc/nginx/sites-enabled/<YOUR_DOMAIN>.conf`

### codex-proxy 路由

```nginx
location /codex/ {
    proxy_pass http://127.0.0.1:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # SSE streaming support
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;    # 5 分钟
}
```

### New-API 路由

```nginx
location / {
    proxy_pass http://127.0.0.1:3001;
    # ...
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

### chatgpt2api Images API

```nginx
location /img/v1/ {
    proxy_pass http://127.0.0.1:3002/v1/;
    # ...
    proxy_read_timeout 300s;    # 出图可能较慢
    proxy_send_timeout 300s;
}
```

### 关键参数说明

| 参数 | 说明 | 建议值 |
|------|------|--------|
| `proxy_read_timeout` | 等待后端响应的最大时间 | 300s（5分钟） |
| `proxy_send_timeout` | 向后端发送请求的最大时间 | 300s |
| `proxy_buffering off` | 关闭响应缓冲，SSE 流式必需 | off |
| `proxy_cache off` | 关闭缓存，实时数据必需 | off |
| `client_max_body_size` | 请求体上限（image-gen 需要上传图片） | 10m |

## SSE 流式传输

Codex CLI 和 ChatGPT API 都使用 **Server-Sent Events (SSE)** 进行流式响应。关键配置：

```nginx
proxy_buffering off;   # 不缓冲响应，逐块转发
proxy_cache off;       # 不缓存流式响应
```

如果不关闭 `proxy_buffering`，Nginx 会等后端完整响应后才转发给客户端，导致：
- 客户端看不到实时输出
- 长时间推理时客户端可能超时断开

## Linux 内核参数（sysctl）

如果遇到大量并发连接或 TIME_WAIT 堆积：

```bash
# 查看当前连接状态
ss -s

# /etc/sysctl.conf 可选优化
net.core.somaxconn = 1024
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_fin_timeout = 30

# 生效
sysctl -p
```

## Docker 网络

### 容器间通信

Docker 容器间通过 Docker 内网 `172.17.0.0/16` 通信：
- New-API → chatgpt2api：`http://172.17.0.1:3002`
- image-gen → chatgpt2api：`http://host.docker.internal:3002`（需 `--add-host`）

### DNS 解析

Docker 容器内的 DNS 默认使用宿主机配置。如果 OpenAI API 域名解析慢，可在 Docker 运行命令中指定 DNS：
```bash
docker run --dns 8.8.8.8 --dns 1.1.1.1 ...
```

## Codex CLI 客户端配置

OpenCode / Codex CLI 自身也有超时配置，确保客户端超时 ≥ Nginx 超时：

```json
{
  "providers": {
    "codex-proxy": {
      "npm": "@ai-sdk/openai",
      "options": {
        "baseURL": "https://<YOUR_DOMAIN>/codex/v1",
        "apiKey": "pwd"
      }
    }
  }
}
```

> Codex CLI 默认超时通常足够（数分钟级别）。如果遇到超时，检查 Nginx 层是否是瓶颈。

## 排查超时问题

```bash
# 1. 检查 Nginx 超时配置
grep -r "timeout" /etc/nginx/sites-enabled/

# 2. 模拟长请求
curl -v --max-time 120 https://<YOUR_DOMAIN>/codex/v1/responses \
  -H "Authorization: Bearer pwd" \
  -H "Content-Type: application/json" \
  -d '{"model":"o3","input":"hello","stream":true}'

# 3. 检查 Nginx 错误日志中的 upstream timeout
grep "upstream timed out" /var/log/nginx/error.log | tail -10

# 4. 检查 codex-proxy 响应时间分布
python3 -c "
import json
with open('/var/log/nginx/codex.access.log') as f:
    times = []
    for line in f:
        try:
            entry = json.loads(line)
            t = float(entry.get('request_time', 0))
            if t > 0: times.append(t)
        except: pass
if times:
    times.sort()
    print(f'请求数: {len(times)}')
    print(f'中位数: {times[len(times)//2]:.1f}s')
    print(f'P95: {times[int(len(times)*0.95)]:.1f}s')
    print(f'P99: {times[int(len(times)*0.99)]:.1f}s')
    print(f'最大: {times[-1]:.1f}s')
"
```

## 速率限制

| 服务 | 限制 | 说明 |
|------|------|------|
| image-gen | 6 次/5 分钟/IP | 应用层实现 |
| chatgpt2api | 取决于 Plus 速率限制 | OpenAI 侧限制，号池越多越稳定 |
| codex-proxy | 取决于账号池大小 | OAuth 账号轮询 |
| New-API | 可在管理面板配置 | 按令牌/用户设置 |

## 注意事项

1. **Plus 速率限制**：单个 Plus 账号有调用频率上限，号池越多越稳定
2. **IP 风控**：单 IP 大量请求可能触发 OpenAI 风控，必要时加代理轮换
3. **Nginx reload vs restart**：修改配置后用 `nginx -t && systemctl reload nginx`，不中断现有连接
4. **logrotate**：`codex.access.log` 已配置自动轮转，无需手动清理
