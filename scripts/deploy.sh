#!/bin/bash
# VPS 一键部署脚本 — 部署全部三个服务
# 用法: bash scripts/deploy.sh [all|proxy|gateway|codex]

set -e

COMPONENT=${1:-all}
WORKDIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$WORKDIR"

echo "=== API Proxy Server 统一部署 ==="
echo "工作目录: $WORKDIR"
echo "部署组件: $COMPONENT"

# ── 基础环境 ──
if ! command -v python3 &> /dev/null; then
    echo "安装 Python3..."
    apt update && apt install -y python3 python3-pip python3-venv
fi

if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "安装依赖..."
pip install -r requirements.txt
pip install -r gateway/requirements.txt

mkdir -p logs

# ── 检查配置文件 ──
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  已创建 .env，请编辑填入 API Key: nano .env"
fi

if [ ! -f "gateway/secrets.json" ]; then
    cp gateway/secrets.example.json gateway/secrets.json
    echo "⚠️  已创建 gateway/secrets.json，请编辑填入 Key: nano gateway/secrets.json"
fi

# ── 服务 1: 透明计费反代 (port 3001) ──
setup_proxy() {
    echo ">>> 配置 proxy 服务 (port 3001)..."
    cat > /etc/systemd/system/api-proxy.service << EOF
[Unit]
Description=API Proxy - Transparent Billing
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$WORKDIR
ExecStart=$WORKDIR/.venv/bin/gunicorn -w 2 -b 0.0.0.0:3001 --timeout 300 proxy.server:app
Restart=always
RestartSec=5
Environment=PYTHONPATH=$WORKDIR

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable api-proxy
    systemctl restart api-proxy
    echo "    ✅ api-proxy 已启动 (port 3001)"
}

# ── 服务 2: Claude Desktop 网关 (port 8082 + 8083) ──
setup_gateway() {
    echo ">>> 配置 gateway 服务 (port 8082/8083)..."
    cat > /etc/systemd/system/api-gateway.service << EOF
[Unit]
Description=API Gateway - Claude Desktop Multi-Provider
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$WORKDIR/gateway
Environment=PROXY_HOST=0.0.0.0
ExecStart=$WORKDIR/.venv/bin/python $WORKDIR/gateway/proxy.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable api-gateway
    systemctl restart api-gateway
    echo "    ✅ api-gateway 已启动 (port 8082 + 8083)"
}

# ── 服务 3: Codex/Claude Code 协议转换 (port 5678) ──
setup_codex() {
    echo ">>> 配置 codex-proxy 服务 (port 5678)..."
    cat > /etc/systemd/system/codex-proxy.service << EOF
[Unit]
Description=Codex Proxy - Anthropic/OpenAI Protocol Translation
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$WORKDIR/gateway
ExecStart=$WORKDIR/.venv/bin/python $WORKDIR/gateway/codex-proxy.py --host 0.0.0.0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable codex-proxy
    systemctl restart codex-proxy
    echo "    ✅ codex-proxy 已启动 (port 5678)"
}

# ── 按组件部署 ──
case $COMPONENT in
    all)
        setup_proxy
        setup_gateway
        setup_codex
        ;;
    proxy)   setup_proxy ;;
    gateway) setup_gateway ;;
    codex)   setup_codex ;;
    *)
        echo "用法: bash scripts/deploy.sh [all|proxy|gateway|codex]"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "  ✅ 部署完成！"
echo "========================================="
echo ""
echo "服务状态:"
echo "  systemctl status api-proxy"
echo "  systemctl status api-gateway"
echo "  systemctl status codex-proxy"
echo ""
echo "查看日志:"
echo "  journalctl -u api-proxy -f"
echo "  journalctl -u api-gateway -f"
echo "  journalctl -u codex-proxy -f"
echo ""
echo "健康检查:"
echo "  curl http://localhost:3001/health"
echo "  curl http://localhost:8082/"
echo ""
echo "端口一览:"
echo "  3001  透明计费反代"
echo "  8082  Claude Desktop 网关"
echo "  8083  网关控制面板"
echo "  5678  Codex/Claude Code 代理"
