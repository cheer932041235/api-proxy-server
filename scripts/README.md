# 运维脚本

VPS 上部署的自动化运维脚本。

## 脚本清单

| 脚本 | VPS 位置 | 触发方式 | 用途 |
|------|----------|----------|------|
| `daily-backup.sh` | `/usr/local/bin/` | cron 02:00 | 备份 New-API DB + chatgpt2api 号池 + codex-proxy 数据 + Nginx 配置 |
| `daily-report.sh` | `/usr/local/bin/` | cron 09:00 | 邮件发送 Codex 用量 + Docker 状态 + 磁盘 |
| `proxy-health-check.py` | `/root/codex-proxy/scripts/` | cron 09:00 | 账号健康检查（JWT 过期、refresh 失败）+ 邮件告警 |
| `fix-docker-iptables.sh` | systemd 调用 | 开机自动 | Docker 重启后补 FORWARD 链规则 |
| `fix-docker-iptables.service` | `/etc/systemd/system/` | systemd 单元 | 上述脚本的 service 单元 |
| `dedup-accounts.py` | 按需上传 | 手动 | chatgpt2api 号池去重（保留最新过期时间） |
| `codex-log-sync/sync_to_newapi.py` | `/root/codex-proxy/scripts/` | 按需 | 同步 codex-proxy 日志到 New-API SQLite（用量统计） |

## 部署

```bash
# 上传脚本到 VPS
scp scripts/*.sh scripts/*.py vps:/usr/local/bin/
scp scripts/codex-log-sync/* vps:/root/codex-proxy/scripts/

# 安装 systemd service
scp scripts/fix-docker-iptables.service vps:/etc/systemd/system/
ssh vps "systemctl daemon-reload && systemctl enable fix-docker-iptables"
```

## Cron 配置

```bash
# 查看当前 cron
ssh vps "crontab -l"

# 预期配置
0 2 * * * /usr/local/bin/daily-backup.sh >> /var/log/daily-backup.log 2>&1
0 9 * * * /usr/local/bin/daily-report.sh >> /var/log/daily-report.log 2>&1
0 9 * * * QQ_SMTP_PASS=xxx /usr/bin/python3 /root/codex-proxy/scripts/proxy-health-check.py >> /var/log/proxy-health.log 2>&1
```

## 详情

### daily-backup.sh

每日 02:00 备份关键数据到 `/root/backups/`，保留 7 天。

备份内容：
- New-API SQLite (`one-api.db`)
- chatgpt2api 号池 JSON（`/root/chatgpt2api-data/*.json`）
- codex-proxy 数据（tar.gz）
- Nginx 配置（tar.gz）

### daily-report.sh

每日 09:00 通过 msmtp 发送邮件到 `<YOUR_PLUS_EMAIL_A>`，包含：
- Codex Proxy 使用统计（请求数、Token 用量、缓存命中率）
- Docker 容器状态
- 磁盘使用情况

依赖：`msmtp`（轻量 SMTP 客户端）

### proxy-health-check.py

每日 09:00 检查：
1. codex-proxy 账号状态（`/root/codex-proxy/data/accounts.json`）
   - status 是否 active
   - refreshToken 是否存在
   - JWT 距离过期 < 24h 告警
2. chatgpt2api 账号状态（HTTP API）
   - status 是否正常
   - JWT 距离过期 < 3 天告警（不支持自动续）
3. codex-proxy `error-log.jsonl` 中最近 24h 的 refresh 失败

异常通过 QQ SMTP 发邮件到 `<YOUR_ALERT_EMAIL>`。

```bash
# 测试邮件
QQ_SMTP_PASS=xxx python3 proxy-health-check.py --test-email
```

### fix-docker-iptables.sh

Docker daemon 重启后 `FORWARD` 链规则可能丢失，导致外部无法访问容器端口。本脚本在开机时通过 systemd 自动补回：

```bash
iptables -I FORWARD 2 -o docker0 -j DOCKER
iptables -I FORWARD 2 -o docker0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -I FORWARD 2 -i docker0 ! -o docker0 -j ACCEPT
iptables -I FORWARD 2 -i docker0 -o docker0 -j ACCEPT
```

### dedup-accounts.py

chatgpt2api 多次导入同一账号时号池可能出现重复条目。本脚本：
- 按 email 分组，保留过期时间最新的条目
- 自动备份原文件
- 兼容多种 JSON 结构

```bash
# 用法
ssh vps "python3 /tmp/dedup-accounts.py"
ssh vps "docker restart chatgpt2api"
```

### codex-log-sync/sync_to_newapi.py

将 codex-proxy 的 Docker 日志中的用量数据（model、tokens、time、status）写入 New-API SQLite，让用量统计能在 New-API 后台展示。

按需手动运行或通过 systemd 持续运行。
