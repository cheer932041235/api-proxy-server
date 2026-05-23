# New-API 部署记录

基于开源项目 [New-API](https://github.com/QuantumNous/new-api)（One-API 增强版），提供专业的 API 管理/分发中转站。

## 访问方式

| 项目 | 值 |
|------|---|
| Web UI | http://<YOUR_VPS_IP>:3001 |
| 账号 | `root` |
| 密码 | `<YOUR_NEW_API_ADMIN_PASS>` |
| API 端点 | http://<YOUR_VPS_IP>:3001/v1/chat/completions |

## 功能特性

- **多模型支持**: GPT / Claude / Gemini / GLM / Kimi / MiniMax / Qwen 等 30+ 模型
- **多渠道管理**: 支持多个 API Key、负载均衡、故障自动转移
- **用户系统**: 注册/登录/配额/订阅
- **精确计费**: 按 Token 计费，账单明细随时可查
- **渠道监控**: 自动检测渠道可用性
- **统一格式**: 所有模型统一为 OpenAI API 格式

## Docker 部署命令

```bash
docker run --name new-api -d --restart always \
  -p 3001:3000 \
  -e TZ=Asia/Shanghai \
  -e MEMORY_CACHE_ENABLED=true \
  -v /root/new-api-data:/data \
  calciumion/new-api:latest
```

## 更新容器

```bash
docker pull calciumion/new-api:latest
docker stop new-api && docker rm new-api
# 重新运行上面的 docker run 命令（数据在 /root/new-api-data 中持久化）
```

## 当前配置

- **自用模式**: 已开启（无需配置模型定价）
- **渠道**: chatgpt2api（代理 `http://172.17.0.1:3002`，密钥 `<YOUR_CHATGPT2API_AUTH_KEY>`）
- **已验证模型**: gpt-5-mini（文本）, gpt-image-2（出图）

## 客户端接入

```
API Base URL: https://<YOUR_DOMAIN>/v1
API Key:      <YOUR_NEW_API_KEY>
```

## 服务架构

```
用户端 → New-API:3001 → chatgpt2api:3002 → ChatGPT Plus（文本 + 出图）
```

> 历史曾接入 AIClient-2-API（端口 3000），已于 2026-05-23 退役。
