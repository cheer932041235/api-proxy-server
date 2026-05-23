# chatgpt2api 部署记录

基于 [chatgpt2api](https://github.com/basketikun/chatgpt2api)，ChatGPT Plus/Pro 逆向 → 标准 OpenAI API。
支持文本模型 + GPT-Image-2 出图 + 号池管理。

## 访问方式

| 项目 | 值 |
|------|---|
| Web 号池管理 | http://<YOUR_VPS_IP>:3002 |
| API 端点 | http://<YOUR_VPS_IP>:3002/v1 |
| Auth Key | `<YOUR_CHATGPT2API_AUTH_KEY>` |

## 可用模型

**文本**: auto, gpt-5, gpt-5-1, gpt-5-2, gpt-5-3, gpt-5-3-mini, gpt-5-5, gpt-5-mini
**出图**: gpt-image-2, codex-gpt-image-2

## 已导入账号

| 邮箱 | 套餐 | 号池 | 状态 |
|------|------|------|------|
| <YOUR_PLUS_EMAIL_A> | Plus | Pool-A | ✅ 正常 |
| <YOUR_PLUS_EMAIL_B> | Plus | Pool-B | ✅ 正常 |

## Docker 部署命令

```bash
docker run -d --name chatgpt2api --restart unless-stopped \
  -p 3002:80 \
  -v /root/chatgpt2api-data:/app/data \
  -e CHATGPT2API_AUTH_KEY=<YOUR_CHATGPT2API_AUTH_KEY> \
  -e STORAGE_BACKEND=json \
  ghcr.io/basketikun/chatgpt2api:latest
```

## 接入 New-API

在 New-API (http://<YOUR_VPS_IP>:3001) 渠道管理中：
1. 类型：**OpenAI**
2. 代理地址：`http://172.17.0.1:3002`（Docker 内网访问宿主机）
3. 密钥：`<YOUR_CHATGPT2API_AUTH_KEY>`
4. 模型：gpt-5, gpt-5-mini, gpt-5-5, gpt-image-2, codex-gpt-image-2

## 添加更多账号

```bash
# 通过 API 导入 access_token
curl -X POST http://localhost:3002/api/accounts \
  -H "Authorization: Bearer <YOUR_CHATGPT2API_AUTH_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"tokens":["ACCESS_TOKEN_HERE"]}'
```

或通过 Web 面板 http://<YOUR_VPS_IP>:3002 批量导入。

## 更新

```bash
docker pull ghcr.io/basketikun/chatgpt2api:latest
docker stop chatgpt2api && docker rm chatgpt2api
# 重新运行 docker run 命令（数据在 /root/chatgpt2api-data 持久化）
```
