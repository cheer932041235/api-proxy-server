#!/usr/bin/env bash
# deploy.sh — 启动/重建所有服务
# 用法：bash scripts/deploy.sh [service_name]
#   不带参数：部署所有
#   带参数：仅重建指定服务（new-api / chatgpt2api / codex-proxy / image-gen）

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "❌ .env 文件不存在"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${VPS_HOST:?}"
: "${VPS_USER:?}"

SSH_TARGET="${VPS_USER}@${VPS_HOST}"
TARGET="${1:-all}"

# ─── new-api ───────────────────────────────
deploy_new_api() {
  echo "▶ 部署 new-api..."
  ssh "$SSH_TARGET" "docker stop new-api 2>/dev/null || true; docker rm new-api 2>/dev/null || true"
  ssh "$SSH_TARGET" "docker run --name new-api -d --restart always \
    -p ${PORT_NEW_API}:3000 \
    -e TZ=Asia/Shanghai \
    -e MEMORY_CACHE_ENABLED=true \
    -v ${DATA_NEW_API}:/data \
    ${IMAGE_NEW_API}"
}

# ─── chatgpt2api ───────────────────────────
deploy_chatgpt2api() {
  echo "▶ 部署 chatgpt2api..."
  ssh "$SSH_TARGET" "docker stop chatgpt2api 2>/dev/null || true; docker rm chatgpt2api 2>/dev/null || true"
  ssh "$SSH_TARGET" "docker run -d --name chatgpt2api --restart unless-stopped \
    -p ${PORT_CHATGPT2API}:80 \
    -v ${DATA_CHATGPT2API}:/app/data \
    -e CHATGPT2API_AUTH_KEY=${CHATGPT2API_AUTH_KEY} \
    -e STORAGE_BACKEND=json \
    ${IMAGE_CHATGPT2API}"
}

# ─── codex-proxy ───────────────────────────
deploy_codex_proxy() {
  echo "▶ 部署 codex-proxy..."
  ssh "$SSH_TARGET" "docker stop codex-proxy 2>/dev/null || true; docker rm codex-proxy 2>/dev/null || true"
  ssh "$SSH_TARGET" "docker run -d --name codex-proxy --restart unless-stopped \
    -p ${PORT_CODEX_PROXY}:8080 \
    -p ${PORT_CODEX_OAUTH_CALLBACK}:1455 \
    -v ${DATA_CODEX_PROXY}:/app/data \
    ${IMAGE_CODEX_PROXY}"
}

# ─── image-gen（自建镜像）───────────────────
deploy_image_gen() {
  echo "▶ 部署 image-gen（同步源码 + 重建镜像）..."
  rsync -avz --delete services/image-gen/ "$SSH_TARGET:/root/image-gen/"
  ssh "$SSH_TARGET" "docker stop image-gen 2>/dev/null || true; docker rm image-gen 2>/dev/null || true"
  ssh "$SSH_TARGET" "cd /root/image-gen && docker build -t image-gen ."
  ssh "$SSH_TARGET" "docker run -d --name image-gen --restart unless-stopped \
    -p ${PORT_IMAGE_GEN}:8088 \
    --add-host=host.docker.internal:host-gateway \
    image-gen"
}

# ─── codex-log-viewer（systemd）─────────────
deploy_codex_log_viewer() {
  echo "▶ 部署 codex-log-viewer（同步源码）..."
  rsync -avz --delete services/codex-log-viewer/ "$SSH_TARGET:/root/codex-log-viewer/"
  ssh "$SSH_TARGET" "systemctl restart codex-log-viewer 2>/dev/null || echo '⚠️ codex-log-viewer.service 尚未安装'"
}

# ─── 主流程 ───────────────────────────────
case "$TARGET" in
  all)
    deploy_new_api
    deploy_chatgpt2api
    deploy_codex_proxy
    deploy_image_gen
    deploy_codex_log_viewer
    ;;
  new-api)         deploy_new_api ;;
  chatgpt2api)     deploy_chatgpt2api ;;
  codex-proxy)     deploy_codex_proxy ;;
  image-gen)       deploy_image_gen ;;
  codex-log-viewer) deploy_codex_log_viewer ;;
  *)
    echo "未知服务：$TARGET"
    echo "可选：all / new-api / chatgpt2api / codex-proxy / image-gen / codex-log-viewer"
    exit 1
    ;;
esac

echo "✅ 完成。检查容器："
ssh "$SSH_TARGET" "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
