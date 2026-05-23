# 日常运维

> 最后更新：2026-05-23

## 连接 VPS

```bash
ssh vps
# 等价于 ssh root@<YOUR_VPS_IP>（需代理，已配置在 ~/.ssh/config）
```

## 查看服务状态

```bash
# 所有 Docker 容器
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# codex-log-viewer（systemd）
systemctl status codex-log-viewer

# 磁盘使用
df -h /
du -sh /root/*-data /root/backups 2>/dev/null
```

## 重启服务

```bash
# 重启单个 Docker 服务
docker restart codex-proxy
docker restart chatgpt2api
docker restart new-api
docker restart image-gen

# 重启 codex-log-viewer
systemctl restart codex-log-viewer

# 重启 Nginx
systemctl restart nginx

# 重启所有 Docker 容器
docker restart $(docker ps -q)
```

## 查看日志

```bash
# Docker 容器日志
docker logs codex-proxy --tail 50 -f
docker logs chatgpt2api --tail 50 -f
docker logs new-api --tail 50 -f
docker logs image-gen --tail 50 -f

# Nginx 日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Codex 专用 JSON 日志
tail -f /var/log/nginx/codex.access.log | python3 -m json.tool

# codex-log-viewer
journalctl -u codex-log-viewer --tail 50 -f

# codex-proxy 错误日志
tail -50 /root/codex-proxy/data/error-log.jsonl | python3 -m json.tool
```

## 更新容器镜像

```bash
# 以 chatgpt2api 为例
docker pull ghcr.io/basketikun/chatgpt2api:latest
docker stop chatgpt2api && docker rm chatgpt2api

# 重新运行（数据已持久化到 /root/chatgpt2api-data/）
docker run -d --name chatgpt2api --restart unless-stopped \
  -p 3002:3002 \
  -v /root/chatgpt2api-data:/data \
  ghcr.io/basketikun/chatgpt2api:latest
```

## 自动备份

已配置 cron 每日 02:00 自动备份，保留 7 天。

```bash
# 查看 cron 任务
crontab -l

# 手动执行备份
/usr/local/bin/daily-backup.sh

# 查看备份
ls -lh /root/backups/
```

### 备份内容

| 数据 | 来源 | 备份文件名 |
|------|------|------------|
| New-API 数据库 | `/root/new-api-data/one-api.db` | `one-api-YYYYMMDD.db` |
| chatgpt2api 号池 | `/root/chatgpt2api-data/*.json` | `*-YYYYMMDD.json` |
| codex-proxy 数据 | `/root/codex-proxy/data/` | `codex-proxy-data-YYYYMMDD.tar.gz` |
| Nginx 配置 | `/etc/nginx/sites-*/` | `nginx-conf-YYYYMMDD.tar.gz` |

## 每日报告

已配置 cron 每日 09:00 发送邮件到 `<YOUR_PLUS_EMAIL_A>`。

内容包括：
- Codex Proxy 使用统计（请求数、Token 用量、缓存命中率）
- Docker 容器状态
- 磁盘使用情况

```bash
# 手动发送
/usr/local/bin/daily-report.sh

# 查看日志
cat /var/log/daily-report.log
```

## 健康检查

每日 09:00 自动执行 `proxy-health-check.py`，检查：
1. codex-proxy 账号状态（status、refreshToken、JWT 过期时间）
2. chatgpt2api 账号状态（status、JWT 过期时间）
3. codex-proxy error-log.jsonl 中最近的 refresh 失败

异常时通过 QQ SMTP 发邮件告警。

```bash
# 手动执行健康检查
QQ_SMTP_PASS=xxx python3 /root/codex-proxy/scripts/proxy-health-check.py

# 测试邮件发送
QQ_SMTP_PASS=xxx python3 /root/codex-proxy/scripts/proxy-health-check.py --test-email
```

## SSL 证书

Let's Encrypt 证书由 certbot 自动续期（systemd timer）。

```bash
# 查看证书状态
certbot certificates

# 手动续期
certbot renew --dry-run

# 续期后重载 Nginx
systemctl reload nginx
```

## 数据持久化路径

| 服务 | VPS 路径 | 内容 |
|------|----------|------|
| New-API | `/root/new-api-data/` | SQLite DB (`one-api.db`)、配置 |
| chatgpt2api | `/root/chatgpt2api-data/` | 号池账号 JSON |
| codex-proxy | `/root/codex-proxy/data/` | 账号 JSON、使用历史、错误日志 |
| codex-log-viewer | `/root/codex-log-viewer/` | Python Flask 源码 |
| image-gen | `/root/image-gen/` | Docker 构建源码 |
| Nginx | `/etc/nginx/sites-enabled/` | 站点配置 |
| 备份 | `/root/backups/` | 每日备份（保留 7 天） |
| 退役归档 | `/root/_archive/` | 已退役服务数据 |

## 防火墙注意事项

新增端口需**同时**在两处放行：

1. **腾讯云控制台**：https://console.cloud.tencent.com/lighthouse → 防火墙规则
2. **VPS iptables**：`iptables -A INPUT -p tcp --dport PORT -j ACCEPT`

> VPS 内有 `YJ-FIREWALL-INPUT` iptables 链（云平台注入的 IP 黑名单），不要清除。
