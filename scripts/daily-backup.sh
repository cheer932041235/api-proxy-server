#!/bin/bash
# daily-backup.sh — Daily backup of critical data
# Cron: 0 2 * * * /usr/local/bin/daily-backup.sh >> /var/log/daily-backup.log 2>&1

BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d)
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting daily backup..."

# Backup New-API database
cp /root/new-api-data/one-api.db "$BACKUP_DIR/one-api-${DATE}.db" 2>/dev/null && \
  echo "  ✓ one-api.db" || echo "  ✗ one-api.db not found"

# Backup chatgpt2api accounts
cp /root/chatgpt2api-data/*.json "$BACKUP_DIR/" 2>/dev/null && \
  for f in /root/chatgpt2api-data/*.json; do
    mv "$BACKUP_DIR/$(basename $f)" "$BACKUP_DIR/$(basename $f .json)-${DATE}.json"
  done && echo "  ✓ chatgpt2api data" || echo "  ✗ chatgpt2api data not found"

# Backup codex-proxy data
if [ -d /root/codex-proxy/data ]; then
  tar -czf "$BACKUP_DIR/codex-proxy-data-${DATE}.tar.gz" -C /root/codex-proxy data/ && \
    echo "  ✓ codex-proxy data" || echo "  ✗ codex-proxy backup failed"
fi

# Backup Nginx config
if [ -d /etc/nginx ]; then
  tar -czf "$BACKUP_DIR/nginx-conf-${DATE}.tar.gz" -C /etc nginx/sites-enabled/ nginx/sites-available/ 2>/dev/null && \
    echo "  ✓ nginx config" || echo "  ✗ nginx config backup failed"
fi

# Clean old backups
find "$BACKUP_DIR" -type f -mtime +${KEEP_DAYS} -delete
echo "[$(date)] Backup done. Kept last ${KEEP_DAYS} days."
