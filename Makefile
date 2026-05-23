# API Proxy Server — 顶层入口
# 用法：make help

.PHONY: help setup deploy update logs status backup ssh restart render-nginx deploy-nginx \
        deploy-new-api deploy-chatgpt2api deploy-codex-proxy deploy-image-gen deploy-log-viewer \
        check-secrets

# 加载 .env（如果存在）
ifneq (,$(wildcard .env))
	include .env
	export
endif

SSH := ssh $(VPS_USER)@$(VPS_HOST)

help:
	@echo "API Proxy Server — 命令清单"
	@echo ""
	@echo "  ─── 首次部署 ───"
	@echo "  make setup            首次安装（Docker / Nginx / SSL / cron / 渲染配置）"
	@echo "  make deploy           启动/重建所有服务"
	@echo ""
	@echo "  ─── 日常运维 ───"
	@echo "  make update           rsync 同步本地修改到 VPS（不重建容器）"
	@echo "  make restart          重启所有 Docker 容器"
	@echo "  make status           查看所有服务状态"
	@echo "  make logs             查看 codex-proxy 实时日志"
	@echo "  make backup           手动触发一次备份"
	@echo "  make ssh              SSH 到 VPS"
	@echo ""
	@echo "  ─── 单独部署 ───"
	@echo "  make deploy-new-api          仅重建 new-api"
	@echo "  make deploy-chatgpt2api      仅重建 chatgpt2api"
	@echo "  make deploy-codex-proxy      仅重建 codex-proxy"
	@echo "  make deploy-image-gen        仅重建 image-gen"
	@echo "  make deploy-log-viewer       仅同步 codex-log-viewer + 重启"
	@echo ""
	@echo "  ─── Nginx ───"
	@echo "  make render-nginx     基于 .env 渲染 nginx 配置到 nginx/rendered/"
	@echo "  make deploy-nginx     渲染 + 部署到 VPS + reload"
	@echo ""
	@echo "  ─── 安全检查 ───"
	@echo "  make check-secrets    扫描敏感词，确认无明文泄露"
	@echo ""
	@echo "当前 .env 关键值："
	@echo "  VPS=$(VPS_USER)@$(VPS_HOST)  Domain=$(DOMAIN)"

# ─── 首次部署 ─────────────────────────────────
setup:
	@bash scripts/setup.sh

# ─── 部署服务 ─────────────────────────────────
deploy:
	@bash scripts/deploy.sh all

deploy-new-api:
	@bash scripts/deploy.sh new-api

deploy-chatgpt2api:
	@bash scripts/deploy.sh chatgpt2api

deploy-codex-proxy:
	@bash scripts/deploy.sh codex-proxy

deploy-image-gen:
	@bash scripts/deploy.sh image-gen

deploy-log-viewer:
	@bash scripts/deploy.sh codex-log-viewer

# ─── Nginx ──────────────────────────────────
render-nginx:
	@bash scripts/render-nginx.sh

deploy-nginx: render-nginx
	@scp nginx/rendered/$(DOMAIN).conf $(VPS_USER)@$(VPS_HOST):/etc/nginx/sites-enabled/$(DOMAIN).conf
	@$(SSH) "nginx -t && systemctl reload nginx"
	@echo "✅ Nginx 已重载"

# ─── 日常运维 ─────────────────────────────────
update:
	@rsync -avz --exclude='.env' --exclude='.git' --exclude='node_modules' \
	  --exclude='__pycache__' --exclude='*.pyc' --exclude='nginx/rendered' \
	  ./services/ $(VPS_USER)@$(VPS_HOST):/root/

restart:
	@$(SSH) "docker restart \$$(docker ps -q)"
	@echo "✅ 所有容器已重启"

status:
	@$(SSH) "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
	@echo ""
	@$(SSH) "systemctl is-active nginx codex-log-viewer fix-docker-iptables 2>/dev/null | paste -d= <(echo -e 'nginx\ncodex-log-viewer\nfix-docker-iptables') -"

logs:
	@$(SSH) "docker logs -f --tail 50 codex-proxy"

backup:
	@$(SSH) "/usr/local/bin/daily-backup.sh"

ssh:
	@$(SSH)

# ─── 安全检查 ─────────────────────────────────
check-secrets:
	@echo "扫描可能的敏感词..."
	@! grep -rEn '170\.106\.|shujinxing777|932041235|cheershuyang|Proxy2026|sk-MxTbv9|sk-gpt2api-secret|疏锦行' \
	  --include='*.md' --include='*.sh' --include='*.py' --include='*.template' \
	  --exclude='local.secrets.md' --exclude='LICENSE' \
	  . 2>/dev/null || (echo "❌ 发现敏感词残留，请清理后再提交" && exit 1)
	@echo "✅ 未发现敏感词残留"
	@echo ""
	@echo "检查 .env 是否被 gitignore..."
	@git check-ignore .env >/dev/null 2>&1 && echo "✅ .env 已被 gitignore" || (echo "❌ .env 未被 gitignore！" && exit 1)
	@git check-ignore local.secrets.md >/dev/null 2>&1 && echo "✅ local.secrets.md 已被 gitignore" || (echo "❌ local.secrets.md 未被 gitignore！" && exit 1)
