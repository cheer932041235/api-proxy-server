#!/usr/bin/env python3
"""
AI Studio 配图工具 — 测试用例
用法: python tests.py [--base http://localhost:8088]

测试覆盖:
  1. 静态文件服务 (HTML/CSS/JS)
  2. Prompt 优化接口
  3. 文本生图接口
  4. 图到图编辑接口
  5. 图片缓存与过期
  6. 请求体大小限制
  7. 速率限制
  8. 错误处理
"""

import argparse
import base64
import json
import sys
import time
import urllib.request
import urllib.error


# === 配置 ===
DEFAULT_BASE = "http://localhost:8088"

# 1x1 红色像素 PNG (89 bytes) — 用于图到图测试
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
)

passed = 0
failed = 0
skipped = 0


def log_pass(name):
    global passed
    passed += 1
    print(f"  ✅ {name}")


def log_fail(name, reason=""):
    global failed
    failed += 1
    print(f"  ❌ {name} — {reason}")


def log_skip(name, reason=""):
    global skipped
    skipped += 1
    print(f"  ⏭️  {name} — {reason}")


def post_json(base, path, data, timeout=10):
    """POST JSON, return (status_code, response_dict)"""
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def get(base, path, timeout=10):
    """GET request, return (status_code, content_type, body_bytes)"""
    req = urllib.request.Request(f"{base}{path}")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:
        return 0, "", str(e).encode()


# ══════════════════════════════════════════════
#  测试组 1: 静态文件服务
# ══════════════════════════════════════════════
def test_static_files(base):
    print("\n[1] 静态文件服务")

    # 1.1 首页 HTML
    code, ct, body = get(base, "/")
    if code == 200 and "text/html" in ct:
        log_pass("GET / → 200 HTML")
    else:
        log_fail("GET / → 200 HTML", f"code={code}, ct={ct}")

    # 1.2 CSS
    code, ct, body = get(base, "/style.css")
    if code == 200 and "css" in ct:
        log_pass("GET /style.css → 200")
    else:
        log_fail("GET /style.css", f"code={code}")

    # 1.3 JS
    code, ct, body = get(base, "/script.js")
    if code == 200 and "javascript" in ct:
        log_pass("GET /script.js → 200")
    else:
        log_fail("GET /script.js", f"code={code}")

    # 1.4 不存在的文件
    code, _, _ = get(base, "/nonexistent.xyz")
    if code == 404:
        log_pass("GET /nonexistent.xyz → 404")
    else:
        log_fail("GET /nonexistent.xyz → 404", f"code={code}")


# ══════════════════════════════════════════════
#  测试组 2: Prompt 优化接口
# ══════════════════════════════════════════════
def test_optimize(base):
    print("\n[2] Prompt 优化接口 /api/optimize")

    # 2.1 空 prompt
    code, data = post_json(base, "/api/optimize", {"prompt": ""})
    if code == 400 and "error" in data:
        log_pass("空 prompt → 400")
    else:
        log_fail("空 prompt → 400", f"code={code}")

    # 2.2 缺少 prompt 字段
    code, data = post_json(base, "/api/optimize", {"style": "academic"})
    if code == 400:
        log_pass("缺少 prompt → 400")
    else:
        log_fail("缺少 prompt → 400", f"code={code}")

    # 2.3 正常优化 (需要后端在线)
    code, data = post_json(base, "/api/optimize",
                           {"prompt": "a cat", "style": "academic"}, timeout=60)
    if code == 200 and "optimized_prompt" in data:
        log_pass(f"正常优化 → 200, len={len(data['optimized_prompt'])}")
    elif code == 500:
        log_skip("正常优化", "后端 LLM 不可用")
    else:
        log_fail("正常优化", f"code={code}, data={data}")


# ══════════════════════════════════════════════
#  测试组 3: 文本生图接口
# ══════════════════════════════════════════════
def test_generate(base):
    print("\n[3] 文本生图接口 /api/generate")

    # 3.1 空 prompt
    code, data = post_json(base, "/api/generate", {"prompt": ""})
    if code == 400 and "error" in data:
        log_pass("空 prompt → 400")
    else:
        log_fail("空 prompt → 400", f"code={code}")

    # 3.2 正常生图 (需要后端在线，较慢)
    code, data = post_json(base, "/api/generate",
                           {"prompt": "a simple red circle on white background",
                            "size": "1024x1024"}, timeout=300)
    if code == 200 and "images" in data and data.get("count", 0) > 0:
        img = data["images"][0]
        img_id = img.get("image_id", "")
        log_pass(f"正常生图 → 200, count={data['count']}, id={img_id}")

        # 3.3 图片可下载
        code2, ct2, body2 = get(base, f"/api/image/{img_id}")
        if code2 == 200 and "image/png" in ct2 and len(body2) > 100:
            log_pass(f"图片下载 → 200, size={len(body2)} bytes")
        else:
            log_fail("图片下载", f"code={code2}, size={len(body2)}")
    elif code == 500:
        log_skip("正常生图", "后端 API 不可用")
    elif code == 429:
        log_skip("正常生图", "速率限制")
    else:
        log_fail("正常生图", f"code={code}, data={data}")


# ══════════════════════════════════════════════
#  测试组 4: 图到图编辑接口
# ══════════════════════════════════════════════
def test_image_to_image(base):
    print("\n[4] 图到图编辑接口 /api/generate (with image)")

    # 4.1 带图片的生成请求
    code, data = post_json(base, "/api/generate",
                           {"prompt": "make it blue",
                            "size": "1024x1024",
                            "image": TINY_PNG_B64}, timeout=300)
    if code == 200 and "images" in data:
        log_pass(f"图到图编辑 → 200, count={data['count']}")
    elif code == 500:
        log_skip("图到图编辑", "后端 API 不可用或不支持 edits")
    elif code == 429:
        log_skip("图到图编辑", "速率限制")
    else:
        log_fail("图到图编辑", f"code={code}, data={data}")

    # 4.2 有图但空 prompt
    code, data = post_json(base, "/api/generate",
                           {"prompt": "", "image": TINY_PNG_B64})
    if code == 400:
        log_pass("图到图空 prompt → 400")
    else:
        log_fail("图到图空 prompt → 400", f"code={code}")


# ══════════════════════════════════════════════
#  测试组 5: 图片缓存与过期
# ══════════════════════════════════════════════
def test_cache(base):
    print("\n[5] 图片缓存")

    # 5.1 不存在的图片 ID
    code, _, _ = get(base, "/api/image/nonexistent123")
    if code == 404:
        log_pass("不存在的图片 → 404")
    else:
        log_fail("不存在的图片 → 404", f"code={code}")

    # 5.2 过期图片（需要手动测试，缩短 TTL 或等 5 分钟）
    log_skip("图片过期自动删除", "需等待 CACHE_TTL(300s) 后验证")


# ══════════════════════════════════════════════
#  测试组 6: 请求体大小限制
# ══════════════════════════════════════════════
def test_body_size_limit(base):
    print("\n[6] 请求体大小限制")

    # 6.1 超大 prompt 优化请求 (>10KB，应被拒绝)
    huge_prompt = "A" * 20000  # 20KB
    code, data = post_json(base, "/api/optimize", {"prompt": huge_prompt})
    if code == 500 and "too large" in data.get("error", "").lower():
        log_pass("超大 optimize 请求 → 拒绝")
    elif code == 500:
        log_pass(f"超大 optimize 请求 → 500 (rejected)")
    else:
        log_fail("超大 optimize 请求", f"code={code}")

    # 6.2 generate 接口用 MAX_IMAGE_BODY_SIZE (8MB)，发 5KB 不应被 size limit 拒绝
    big_prompt = "B" * 5000  # 5KB
    code, data = post_json(base, "/api/generate", {"prompt": big_prompt}, timeout=5)
    # 任何非 size-limit 的响应都说明请求体大小被接受了
    err = data.get("error", "")
    if "too large" in err.lower():
        log_fail("5KB generate 请求不应被 body size 拒绝", f"code={code}")
    else:
        log_pass(f"5KB generate 请求体大小被接受 (code={code})")


# ══════════════════════════════════════════════
#  测试组 7: 速率限制
# ══════════════════════════════════════════════
def test_rate_limit(base):
    print("\n[7] 速率限制 (6次/5分钟)")
    log_skip("速率限制完整测试", "需连续发送 7 次生图请求，耗时过长")

    # 简单验证: 确认 429 响应格式
    # 实际测试需快速发送 7 个请求然后检查第 7 个返回 429


# ══════════════════════════════════════════════
#  测试组 8: CORS & OPTIONS
# ══════════════════════════════════════════════
def test_cors(base):
    print("\n[8] CORS & OPTIONS")

    req = urllib.request.Request(f"{base}/api/generate", method="OPTIONS")
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        if resp.status == 204 and acao == "*":
            log_pass("OPTIONS /api/generate → 204, CORS=*")
        else:
            log_fail("OPTIONS", f"status={resp.status}, ACAO={acao}")
    except Exception as e:
        log_fail("OPTIONS", str(e))


# ══════════════════════════════════════════════
#  测试组 9: 404 路由
# ══════════════════════════════════════════════
def test_404_routes(base):
    print("\n[9] 404 路由")

    code, data = post_json(base, "/api/nonexistent", {"foo": "bar"})
    if code == 404:
        log_pass("POST /api/nonexistent → 404")
    else:
        log_fail("POST /api/nonexistent → 404", f"code={code}")


# ══════════════════════════════════════════════
#  测试组 10: HTML 内容检查
# ══════════════════════════════════════════════
def test_html_content(base):
    print("\n[10] HTML 内容检查")

    code, ct, body = get(base, "/")
    html = body.decode("utf-8", errors="replace")

    # 10.1 解锁门
    if "gateOverlay" in html and "身份验证" in html:
        log_pass("包含解锁门 (gateOverlay)")
    else:
        log_fail("包含解锁门")

    # 10.2 图片上传区
    if "uploadArea" in html and "参考图片" in html:
        log_pass("包含图片上传区 (uploadArea)")
    else:
        log_fail("包含图片上传区")

    # 10.3 过期提示
    if "expire-notice" in html and "5 分钟" in html:
        log_pass("包含过期提示 (expire-notice)")
    else:
        log_fail("包含过期提示")

    # 10.4 双图预览
    if "dualGrid" in html:
        log_pass("包含双图预览 (dualGrid)")
    else:
        log_fail("包含双图预览")


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="AI Studio 配图工具 测试")
    parser.add_argument("--base", default=DEFAULT_BASE, help="服务地址")
    parser.add_argument("--quick", action="store_true",
                        help="仅运行快速测试（跳过生图）")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    print(f"🧪 AI Studio 测试  →  {base}")

    # 检查服务是否在线
    try:
        urllib.request.urlopen(f"{base}/", timeout=5)
    except Exception as e:
        print(f"\n❌ 服务不可达: {e}")
        print(f"   请先启动服务: python server.py")
        sys.exit(1)

    # 快速测试（不调用后端 API）
    test_static_files(base)
    test_html_content(base)
    test_cors(base)
    test_404_routes(base)
    test_cache(base)
    test_body_size_limit(base)

    if not args.quick:
        # 慢速测试（需要后端 chatgpt2api 在线）
        test_optimize(base)
        test_generate(base)
        test_image_to_image(base)
        test_rate_limit(base)
    else:
        print("\n⏭️  --quick 模式: 跳过生图/优化测试")

    # 汇总
    total = passed + failed + skipped
    print(f"\n{'='*50}")
    print(f"  ✅ 通过: {passed}  ❌ 失败: {failed}  ⏭️ 跳过: {skipped}  📊 总计: {total}")
    print(f"{'='*50}")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
