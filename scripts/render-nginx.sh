#!/usr/bin/env bash
# render-nginx.sh — 基于 .env 渲染 nginx 配置模板
# 用法：bash scripts/render-nginx.sh
# 输出：nginx/rendered/<DOMAIN>.conf

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "❌ .env 文件不存在，请先 cp .env.example .env 并填值"
  exit 1
fi

# 加载环境变量
set -a
# shellcheck disable=SC1091
source .env
set +a

# 校验必要变量
: "${DOMAIN:?DOMAIN 必须在 .env 中设置}"
: "${PORT_NEW_API:?PORT_NEW_API 必须设置}"
: "${PORT_CHATGPT2API:?PORT_CHATGPT2API 必须设置}"
: "${PORT_CODEX_PROXY:?PORT_CODEX_PROXY 必须设置}"
: "${PORT_IMAGE_GEN:?PORT_IMAGE_GEN 必须设置}"

# 创建输出目录
mkdir -p nginx/rendered

# 渲染（envsubst 只替换我们指定的变量，避免误替 nginx 原生 $var）
TEMPLATE="nginx/api.example.com.conf.template"
OUTPUT="nginx/rendered/${DOMAIN}.conf"

envsubst '${DOMAIN} ${PORT_NEW_API} ${PORT_CHATGPT2API} ${PORT_CODEX_PROXY} ${PORT_IMAGE_GEN} ${PORT_CODEX_LOG_VIEWER}' \
  < "$TEMPLATE" > "$OUTPUT"

echo "✅ 已渲染：$OUTPUT"
echo "   下一步：scp 到 VPS 的 /etc/nginx/sites-enabled/"
echo "   或运行：make deploy-nginx"
