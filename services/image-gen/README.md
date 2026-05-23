# image-gen

GPT-Image-2 双号池并行出图 Web 工具。

## 基本信息

| 项目 | 值 |
|------|---|
| 端口 | 8088 |
| 类型 | Docker 容器（自建镜像） |
| 访问 | https://<YOUR_DOMAIN>/studio/ |
| 鉴权 | 答题解锁（<YOUR_STUDIO_QUIZ_QUESTION>→ <YOUR_STUDIO_QUIZ_ANSWER>） |
| VPS 源码 | `/root/image-gen/` |
| 本地源码 | `services/image-gen/` |

## 功能

- 双号池（Pool-A/B）并行调用 GPT-Image-2，一次生成两张图
- 智能增强（LLM 润色 prompt）+ 7 种风格预设 + 5 种尺寸
- 速率限制 6 次/5 分钟/IP，请求体上限 10KB
- 图片缓存 5 分钟自动清理
- 图到图编辑（上传参考图，4MB 限制）
- 过期提示横幅 + 浏览器缓存治理

## 部署

```bash
cd /root/image-gen
docker build -t image-gen .
docker run -d --name image-gen --restart unless-stopped \
  -p 8088:8088 \
  --add-host=host.docker.internal:host-gateway \
  image-gen
```

## 更新

```bash
# 本地修改后上传
scp services/image-gen/* vps:/root/image-gen/

# VPS 重建
ssh vps "docker stop image-gen && docker rm image-gen && \
  cd /root/image-gen && docker build -t image-gen . && \
  docker run -d --name image-gen --restart unless-stopped \
  -p 8088:8088 --add-host=host.docker.internal:host-gateway image-gen"
```

## 依赖

- 后端调用 `host.docker.internal:3002`（chatgpt2api）的 Images API
- chatgpt2api token 过期会导致出图失败
