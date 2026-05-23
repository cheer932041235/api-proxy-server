#!/usr/bin/env bash
# setup.sh — 首次安装：在新 VPS 上跑一次，装好基础设施
# 用法：bash scripts/setup.sh
#
# 做的事：
#   1. 安装系统依赖（Docker、Nginx、certbot、msmtp）
#   2. 创建数据目录
#   3. 拉取所有 Docker 镜像
#   4. 申请 SSL 证书
#   5. 渲染并安装 Nginx 配置
#   6. 安装 Docker iptables 自动修复 systemd
#   7. 安装每日备份/报告 cron

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "❌ .env 文件不存在，请先 cp .env.example .env 并填值"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${VPS_HOST:?}"
: "${VPS_USER:?}"
: "${DOMAIN:?}"
: "${SSL_EMAIL:?}"

SSH_TARGET="${VPS_USER}@${VPS_HOST}"

echo "╔══════════════════════════════════════════════════╗"
echo "║          API Proxy Server — 首次安装              ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║ VPS:     $SSH_TARGET"
echo "║ Domain:  $DOMAIN"
echo "║ Email:   $SSL_EMAIL"
echo "╚══════════════════════════════════════════════════╝"
read -rp "确认开始安装？(y/N) " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "已取消"; exit 0; }

# ─── 1. 系统依赖 ──────────────────────────────
echo ""
echo "▶ 1/7 安装系统依赖..."
ssh "$SSH_TARGET" bash <<'REMOTE_EOF'
set -euo pipefail
apt-get update -qq
apt-get install -y -qq docker.io docker-compose nginx certbot python3-certbot-nginx msmtp curl jq python3 python3-pip
systemctl enable --now docker
systemctl enable --now nginx
REMOTE_EOF

# ─── 2. 数据目录 ─────────────────────────────
echo ""
echo "▶ 2/7 创建数据目录..."
ssh "$SSH_TARGET" "mkdir -p ${DATA_NEW_API} ${DATA_CHATGPT2API} ${DATA_CODEX_PROXY} ${DATA_BACKUPS} /var/www/homepage /root/image-gen /root/codex-log-viewer"

# ─── 3. 拉取镜像 ─────────────────────────────
echo ""
echo "▶ 3/7 拉取 Docker 镜像..."
ssh "$SSH_TARGET" "docker pull ${IMAGE_NEW_API} && docker pull ${IMAGE_CHATGPT2API} && docker pull ${IMAGE_CODEX_PROXY}"

# ─── 4. SSL 证书 ─────────────────────────────
echo ""
echo "▶ 4/7 申请 SSL 证书..."
ssh "$SSH_TARGET" "certbot --nginx -d ${DOMAIN} --email ${SSL_EMAIL} --agree-tos --non-interactive --redirect || echo '⚠️ 证书申请失败（如果已存在可忽略）'"

# ─── 5. Nginx 配置 ───────────────────────────
echo ""
echo "▶ 5/7 渲染并部署 Nginx 配置..."
bash "$ROOT_DIR/scripts/render-nginx.sh"
scp "nginx/rendered/${DOMAIN}.conf" "$SSH_TARGET:/etc/nginx/sites-enabled/${DOMAIN}.conf"
ssh "$SSH_TARGET" "nginx -t && systemctl reload nginx"

# ─── 6. Docker iptables 修复 systemd ─────────
echo ""
echo "▶ 6/7 安装 Docker iptables 修复 systemd..."
scp scripts/fix-docker-iptables.sh "$SSH_TARGET:/usr/local/bin/"
scp scripts/fix-docker-iptables.service "$SSH_TARGET:/etc/systemd/system/"
ssh "$SSH_TARGET" "chmod +x /usr/local/bin/fix-docker-iptables.sh && systemctl daemon-reload && systemctl enable fix-docker-iptables"

# ─── 7. 备份/报告脚本 ────────────────────────
echo ""
echo "▶ 7/7 安装备份/报告 cron..."
scp scripts/daily-backup.sh scripts/daily-report.sh "$SSH_TARGET:/usr/local/bin/"
ssh "$SSH_TARGET" "chmod +x /usr/local/bin/daily-backup.sh /usr/local/bin/daily-report.sh"
ssh "$SSH_TARGET" "(crontab -l 2>/dev/null | grep -v 'daily-backup.sh\|daily-report.sh'; echo '0 2 * * * /usr/local/bin/daily-backup.sh >> /var/log/daily-backup.log 2>&1'; echo '0 9 * * * /usr/local/bin/daily-report.sh >> /var/log/daily-report.log 2>&1') | crontab -"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              ✅ 安装完成！                        ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║ 下一步：                                           ║"
echo "║   1. make deploy   ← 启动所有服务                  ║"
echo "║   2. 浏览器访问 https://${DOMAIN}                  "
echo "║   3. 导入 ChatGPT Plus 账号（详见 04-token-renewal）"
echo "╚══════════════════════════════════════════════════╝"
