# codex-log-viewer

Codex Proxy 调用日志面板，读取 Nginx JSON access log 展示实时统计。

## 基本信息

| 项目 | 值 |
|------|---|
| 端口 | 8089 |
| 类型 | systemd service（Python Flask） |
| 访问 | https://<YOUR_DOMAIN>/codex/log/?token=pwd |
| VPS 路径 | `/root/codex-log-viewer/server.py` |
| systemd | `codex-log-viewer.service`（开机自启，崩溃自动重启） |
| 本地源码 | `services/codex-log-viewer/` |

## 功能

- 实时刷新日志
- 模型统计（按模型分组计数）
- 状态码过滤
- 响应时间可视化

## 数据源

- 日志文件：`/var/log/nginx/codex.access.log`（JSON 格式）
- logrotate 自动轮转
- Nginx `codex_json` 格式记录：`time_iso8601`, `remote_addr`, `method`, `uri`, `query`, `status`, `bytes_sent`, `request_time`, `upstream_response_time`, `user_agent`, `request_body`

## API

| 端点 | 用途 |
|------|------|
| `/codex/log/` | 日志面板 HTML |
| `/codex/log/api/logs` | 日志 JSON（支持 `?key=<YOUR_LOG_TOKEN>`） |
| `/codex/log/api/stats` | 统计 JSON |

## 管理

```bash
# 查看状态
systemctl status codex-log-viewer

# 重启
systemctl restart codex-log-viewer

# 查看服务日志
journalctl -u codex-log-viewer --tail 50 -f
```

## 更新

```bash
# 上传新版
scp services/codex-log-viewer/* vps:/root/codex-log-viewer/

# 重启
ssh vps "systemctl restart codex-log-viewer"
```
