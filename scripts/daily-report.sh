#!/bin/bash
# daily-report.sh — Send daily token usage report via email
# Cron: 0 9 * * * /usr/local/bin/daily-report.sh >> /var/log/daily-report.log 2>&1
# Requires: msmtp (lightweight SMTP client)

RECIPIENT="932041235@qq.com"
DATE_YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)
DATE_DISPLAY=$(date -d "yesterday" +"%Y年%m月%d日" 2>/dev/null || date -v-1d +"%Y年%m月%d日")

# ── Collect New-API stats ──
NEWAPI_STATS=$(curl -s http://localhost:3001/api/log/stat \
  -H "Authorization: Bearer $(cat /root/.newapi-admin-token 2>/dev/null || echo '')" \
  2>/dev/null)

# ── Collect codex-proxy stats ──
CODEX_USAGE=""
if [ -f /root/codex-proxy/data/usage-history.json ]; then
  CODEX_USAGE=$(python3 -c "
import json, sys
from datetime import datetime, timedelta

yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
with open('/root/codex-proxy/data/usage-history.json') as f:
    data = json.load(f)

day_entries = [e for e in data if e.get('timestamp','')[:10] == yesterday]
total_input = sum(e['usage'].get('input_tokens', 0) for e in day_entries)
total_output = sum(e['usage'].get('output_tokens', 0) for e in day_entries)
total_cached = sum(e['usage'].get('cached_tokens', 0) for e in day_entries)
req_count = len(day_entries)

print(f'请求数: {req_count}')
print(f'输入 Tokens: {total_input:,}')
print(f'输出 Tokens: {total_output:,}')
print(f'缓存 Tokens: {total_cached:,}')
if total_input > 0:
    print(f'缓存命中率: {total_cached/total_input*100:.1f}%')
" 2>/dev/null)
fi

# ── Collect Docker container status ──
DOCKER_STATUS=$(docker ps --format "{{.Names}}\t{{.Status}}" 2>/dev/null)

# ── Collect disk usage ──
DISK_USAGE=$(df -h / | tail -1 | awk '{print "总量: "$2" 已用: "$3" 可用: "$4" 使用率: "$5}')

# ── Build email body ──
BODY="AI 中转站日报 — ${DATE_DISPLAY}
========================================

📊 Codex Proxy (Responses API) 使用统计:
${CODEX_USAGE:-无数据}

🐳 Docker 容器状态:
${DOCKER_STATUS}

💾 磁盘使用:
${DISK_USAGE}

========================================
此邮件由 VPS (170.106.65.175) 自动发送
"

# ── Send email via msmtp ──
echo -e "Subject: =?UTF-8?B?$(echo -n "AI中转站日报 ${DATE_DISPLAY}" | base64 -w0)?=\nFrom: cheershuyang@qq.com\nTo: ${RECIPIENT}\nContent-Type: text/plain; charset=UTF-8\n\n${BODY}" | \
  msmtp "${RECIPIENT}" 2>&1

if [ $? -eq 0 ]; then
  echo "[$(date)] Daily report sent to ${RECIPIENT}"
else
  echo "[$(date)] Failed to send daily report"
fi
