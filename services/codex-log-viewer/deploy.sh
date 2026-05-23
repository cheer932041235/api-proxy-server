#!/bin/bash
# Deploy Codex Log Viewer: update Nginx config + start log viewer service
set -e

echo "=== 1. Update Nginx config ==="

NGINX_CONF="/etc/nginx/sites-available/<YOUR_DOMAIN>.conf"

# Add codex JSON log format in http block (nginx.conf)
if ! grep -q 'codex_json' /etc/nginx/nginx.conf; then
  echo "[+] Adding codex_json log format to nginx.conf"
  # Insert before the last closing brace of http block
  sed -i '/^http {/,/^}/ {
    /include \/etc\/nginx\/sites-enabled/i \
    # Codex Proxy structured access log\
    log_format codex_json escape=json\
      '"'"'{"time_iso8601":"$time_iso8601",'"'"'\
      '"'"'"remote_addr":"$remote_addr",'"'"'\
      '"'"'"method":"$request_method",'"'"'\
      '"'"'"uri":"$uri",'"'"'\
      '"'"'"query":"$query_string",'"'"'\
      '"'"'"status":$status,'"'"'\
      '"'"'"bytes_sent":$bytes_sent,'"'"'\
      '"'"'"request_time":$request_time,'"'"'\
      '"'"'"upstream_response_time":"$upstream_response_time",'"'"'\
      '"'"'"user_agent":"$http_user_agent",'"'"'\
      '"'"'"request_body":"$request_body"}'"'"';
  }' /etc/nginx/nginx.conf
else
  echo "[=] codex_json log format already exists"
fi

# Update /codex/ location to include access log + request body buffering
echo "[+] Updating /codex/ location in site config"

# Replace the existing /codex/ block
python3 << 'PYEOF'
import re

conf_path = "/etc/nginx/sites-available/<YOUR_DOMAIN>.conf"
with open(conf_path, "r") as f:
    content = f.read()

new_codex_block = """    # Codex Proxy — with structured logging
    location /codex/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE streaming support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;

        # Capture request body for logging (model name extraction)
        client_body_in_single_buffer on;
        client_body_buffer_size 16k;
        client_max_body_size 50m;

        # Structured JSON access log
        access_log /var/log/nginx/codex.access.log codex_json;
    }

    # Codex Log Viewer dashboard
    location /codex/log/ {
        proxy_pass http://127.0.0.1:8089/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }"""

# Match the existing /codex/ location block
pattern = r'(\s*# Codex Proxy\n\s*location /codex/ \{[^}]+\})'
if re.search(pattern, content):
    content = re.sub(pattern, new_codex_block, content)
else:
    # Insert before the closing } of the server block (before HTTP redirect server)
    # Find last occurrence of location in the 443 server
    content = content.replace(
        "    # Codex Proxy\n    location /codex/ {",
        new_codex_block + "\n\n    # OLD Codex Proxy (replaced)\n    # location /codex/ {"
    )

with open(conf_path, "w") as f:
    f.write(content)

print("[+] Nginx site config updated")
PYEOF

# Test nginx config
echo "=== 2. Test Nginx config ==="
nginx -t

echo "=== 3. Reload Nginx ==="
systemctl reload nginx
echo "[+] Nginx reloaded"

# Touch the log file
touch /var/log/nginx/codex.access.log
chown www-data:adm /var/log/nginx/codex.access.log

echo "=== 4. Deploy log viewer ==="
mkdir -p /root/codex-log-viewer/static
cp /tmp/codex-log-viewer/server.py /root/codex-log-viewer/
cp /tmp/codex-log-viewer/static/index.html /root/codex-log-viewer/static/

# Install Flask if needed
pip3 install flask -q 2>/dev/null || true

# Stop old viewer if running
pkill -f 'codex-log-viewer/server.py' 2>/dev/null || true
sleep 1

# Start viewer as background service
cd /root/codex-log-viewer
nohup python3 server.py > /var/log/codex-log-viewer.log 2>&1 &
sleep 2

# Verify
if curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8089/ | grep -q 200; then
  echo "[+] Log viewer running on port 8089"
else
  echo "[!] Log viewer may not be ready yet, check /var/log/codex-log-viewer.log"
fi

echo "=== 5. Quick smoke test ==="
# Send a test request through nginx
RESP=$(curl -sS -o /dev/null -w "%{http_code}" https://<YOUR_DOMAIN>/codex/v1/models -H "Authorization: Bearer pwd")
echo "[+] /codex/v1/models → HTTP $RESP"
sleep 1
echo "[+] Log file lines: $(wc -l < /var/log/nginx/codex.access.log)"

echo ""
echo "=== DONE ==="
echo "Codex Proxy:    https://<YOUR_DOMAIN>/codex/v1"
echo "Log Viewer:     https://<YOUR_DOMAIN>/codex/log/?token=pwd"
echo "Nginx Log:      /var/log/nginx/codex.access.log"
