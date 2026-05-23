#!/usr/bin/env python3
"""Image generation web server - calls chatgpt2api for free image generation
Features: prompt optimization via LLM, style presets, image generation via gpt-image-2
"""
import http.server
import json
import urllib.request
import urllib.error
import os
import base64
import sys
import threading
import time
import hashlib
import logging
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', stream=sys.stdout)
log = logging.getLogger('image-gen')

# In-memory ring buffer for recent logs (accessible via /api/logs)
_log_buffer = []
_log_buffer_lock = threading.Lock()
LOG_BUFFER_SIZE = 200

class BufferHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        with _log_buffer_lock:
            _log_buffer.append(msg)
            if len(_log_buffer) > LOG_BUFFER_SIZE:
                del _log_buffer[:len(_log_buffer) - LOG_BUFFER_SIZE]

_buf_handler = BufferHandler()
_buf_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
log.addHandler(_buf_handler)

# Stats counters
_stats_lock = threading.Lock()
_stats = {"started": None, "requests": 0, "success": 0, "errors": 0, "last_error": None, "last_success": None}

PORT = 8088
MAX_BODY_SIZE = 10 * 1024  # 10KB for text-only requests
MAX_IMAGE_BODY_SIZE = 8 * 1024 * 1024  # 8MB for requests with image
CACHE_TTL = 300  # 5 minutes
# Two backend pools for parallel generation
BACKENDS = [
    {"name": "Pool-A", "url": os.environ.get("CHATGPT2API_URL", "http://host.docker.internal:3002"), "key": "<YOUR_CHATGPT2API_AUTH_KEY>"},
    {"name": "Pool-B", "url": os.environ.get("CHATGPT2API_URL", "http://host.docker.internal:3002"), "key": "<YOUR_CHATGPT2API_AUTH_KEY>"},
]
CHATGPT2API_URL = BACKENDS[0]["url"]
CHATGPT2API_KEY = BACKENDS[0]["key"]
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Content-hash cache busting: compute MD5 of static assets at startup
def _file_hash(filename):
    path = os.path.join(STATIC_DIR, filename)
    if not os.path.exists(path):
        return 'missing'
    return hashlib.md5(open(path, 'rb').read()).hexdigest()[:8]

_asset_hashes = {}
def _refresh_hashes():
    global _asset_hashes
    _asset_hashes = {
        '__JS_HASH__': _file_hash('script.js'),
        '__CSS_HASH__': _file_hash('style.css'),
    }
    log.info(f'  Asset hashes: JS={_asset_hashes["__JS_HASH__"]}, CSS={_asset_hashes["__CSS_HASH__"]}')

_refresh_hashes()

# Simple per-IP rate limiter for /api/generate
_rate_lock = threading.Lock()
_rate_map = {}  # ip -> [timestamp, ...]
RATE_LIMIT = 6  # max requests per window
RATE_WINDOW = 300  # 5 minutes

# In-memory image cache (id -> bytes), auto-cleanup
_image_cache = {}
_cache_lock = threading.Lock()

def _cleanup_cache():
    """Remove images older than CACHE_TTL and stale rate-limit entries"""
    now = time.time()
    with _cache_lock:
        expired = [k for k, v in _image_cache.items() if now - v["ts"] > CACHE_TTL]
        for k in expired:
            del _image_cache[k]
        if _image_cache:
            log.info(f'[CACHE] {len(_image_cache)} images in cache')
    with _rate_lock:
        stale = [ip for ip, ts in _rate_map.items() if all(now - t > RATE_WINDOW for t in ts)]
        for ip in stale:
            del _rate_map[ip]
    t = threading.Timer(60, _cleanup_cache)
    t.daemon = True
    t.start()

_cleanup_cache()


def _build_multipart(fields, files):
    """Build multipart/form-data body for image editing API"""
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    for key, (filename, data, content_type) in files.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
            + data + b'\r\n'
        )
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'

def _check_rate(ip):
    now = time.time()
    with _rate_lock:
        times = _rate_map.get(ip, [])
        times = [t for t in times if now - t < RATE_WINDOW]
        if len(times) >= RATE_LIMIT:
            return False
        times.append(now)
        _rate_map[ip] = times
        return True


class ImageGenHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        log.info(f"[{self.log_date_time_string()}] {format % args}")

    def do_POST(self):
        try:
            if self.path == '/api/optimize':
                self._handle_optimize()
            elif self.path == '/api/generate':
                self._handle_generate()
            else:
                self.send_error(404)
        except Exception as e:
            log.error(f'do_POST crashed: {traceback.format_exc()}')
            try:
                self._json_response(500, {"error": f"Internal error: {str(e)}"})
            except Exception:
                pass

    def do_GET(self):
        try:
            if self.path.startswith('/api/image/'):
                self._handle_image_proxy()
            elif self.path == '/api/health':
                self._handle_health()
            elif self.path.startswith('/api/logs'):
                self._handle_logs()
            elif self.path == '/' or self.path.startswith('/?'):
                self._serve_html_with_hashes()
            else:
                super().do_GET()
        except Exception as e:
            log.error(f'do_GET crashed: {traceback.format_exc()}')

    def _serve_html_with_hashes(self):
        """Serve index.html with content-hash cache busting and no-cache header"""
        html_path = os.path.join(STATIC_DIR, 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for placeholder, hash_val in _asset_hashes.items():
            content = content.replace(placeholder, hash_val)
        body = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Cache-Control', 'no-cache, must-revalidate')
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        """Add cache headers for static assets (JS/CSS get long cache, others default)"""
        path = self.path.split('?')[0]
        if path.endswith(('.js', '.css')):
            self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        super().end_headers()

    def _read_body(self, max_size=MAX_BODY_SIZE):
        length = int(self.headers.get('Content-Length', 0))
        if not length:
            return {}
        if length > max_size:
            raise ValueError(f'Request body too large: {length}')
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.error(f'JSON decode failed: {e}, raw={raw[:200]}')
            raise

    def _handle_optimize(self):
        """Step 1: Use LLM to optimize the user's prompt"""
        body = self._read_body()
        prompt = body.get('prompt', '').strip()
        style = body.get('style', 'general')

        if not prompt:
            self._json_response(400, {"error": "prompt is required"})
            return

        style_instructions = {
            "academic": "Optimize this into a professional academic figure description suitable for scientific papers. Use precise, technical language. Describe layout, labels, color scheme (clean, publication-ready). Mention white background, clear annotations, high contrast. The figure should look like it belongs in a Nature/Science paper.",
            "architecture": "Optimize this into a detailed system architecture diagram description. Include components, connections, data flow arrows, labels. Use clean professional style with organized layout, consistent shapes, and clear hierarchy.",
            "minimalist": "Optimize this into a clean, minimalist illustration description. Use simple shapes, limited color palette (2-3 colors), plenty of white space, modern flat design aesthetic.",
            "realistic": "Optimize this into a photorealistic image description. Include lighting details, textures, depth of field, camera angle. Make it look like a professional photograph.",
            "artistic": "Optimize this into an artistic, creative illustration description. Include art style references (watercolor, oil painting, digital art), mood, atmosphere, color harmony.",
            "infographic": "Optimize this into an infographic-style visual description. Include data visualization elements, icons, clear sections, readable text areas, professional color scheme.",
            "general": "Optimize this image prompt to be more detailed and specific for AI image generation. Add details about composition, lighting, style, colors, and mood."
        }

        system_msg = f"""You are an expert prompt engineer for AI image generation (GPT-image-2).
{style_instructions.get(style, style_instructions['general'])}

Rules:
- Output ONLY the optimized English prompt, nothing else
- Be specific about visual details: composition, colors, lighting, style
- Keep it under 200 words
- Do NOT include any explanation or metadata"""

        payload = json.dumps({
            "model": "gpt-5-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Original prompt: {prompt}"}
            ],
            "max_tokens": 300,
            "temperature": 0.7
        }).encode()

        req = urllib.request.Request(
            f"{CHATGPT2API_URL}/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {CHATGPT2API_KEY}", "Content-Type": "application/json"}
        )

        try:
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            optimized = result["choices"][0]["message"]["content"].strip()
            self._json_response(200, {"optimized_prompt": optimized, "model": "gpt-5-mini"})
        except Exception as e:
            self._json_response(500, {"error": f"Optimization failed: {str(e)}"})

    @staticmethod
    def _gen_one(backend, prompt, size, image_b64=None):
        """Generate or edit an image. Returns dict or error string."""
        name = backend['name']
        try:
            if image_b64:
                img_bytes = base64.b64decode(image_b64)
                fields = {"model": "gpt-image-2", "prompt": prompt, "n": "1", "size": size}
                files = {"image": ("input.png", img_bytes, "image/png")}
                body, content_type = _build_multipart(fields, files)
                url = f"{backend['url']}/v1/images/edits"
                headers = {"Authorization": f"Bearer {backend['key']}", "Content-Type": content_type}
                mode = "Edit"
            else:
                body = json.dumps({"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": size}).encode()
                url = f"{backend['url']}/v1/images/generations"
                headers = {"Authorization": f"Bearer {backend['key']}", "Content-Type": "application/json"}
                mode = "Create"

            req = urllib.request.Request(url, data=body, headers=headers)
            log.info(f'[GEN-{name}] {mode}, prompt={prompt[:50]}..., size={size}')
            resp = urllib.request.urlopen(req, timeout=300)
            raw = resp.read()
            log.info(f'[GEN-{name}] Response received, length={len(raw)}')
            result = json.loads(raw)
            img_data = result["data"][0]
            img_id = hashlib.md5(f"{prompt}{time.time()}{name}".encode()).hexdigest()[:12]
            b64 = img_data.get("b64_json", "")
            if b64:
                with _cache_lock:
                    _image_cache[img_id] = {"data": b64, "ts": time.time()}
            return {"image_id": img_id, "has_b64": bool(b64), "revised_prompt": img_data.get("revised_prompt", ""), "model": "gpt-image-2", "size": size, "pool": name}
        except Exception as e:
            log.error(f'[GEN-{name}] ERROR: {e}')
            return f"{name}: {str(e)}"

    def _handle_generate(self):
        """Generate images from two pools in parallel, return all successes"""
        with _stats_lock:
            _stats['requests'] += 1
        client_ip = self.client_address[0]
        if not _check_rate(client_ip):
            self._json_response(429, {"error": "\u8bf7\u6c42\u8fc7\u4e8e\u9891\u7e41\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\uff08\u6bcf5\u5206\u949f\u6700\u591a6\u6b21\uff09"})
            return

        body = self._read_body(max_size=MAX_IMAGE_BODY_SIZE)
        prompt = body.get('prompt', '').strip()
        size = body.get('size', '1024x1024')
        image_b64 = body.get('image')  # optional base64 image for editing

        if not prompt:
            self._json_response(400, {"error": "prompt is required"})
            return

        if image_b64:
            log.info(f'[GEN] Image-to-image mode, image size={len(image_b64)//1024}KB')

        results = []
        errors = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(self._gen_one, be, prompt, size, image_b64): be['name'] for be in BACKENDS}
            for fut in as_completed(futures):
                r = fut.result()
                if isinstance(r, dict):
                    results.append(r)
                else:
                    errors.append(r)

        if not results:
            err_msg = f"All pools failed: {'; '.join(errors)}"
            log.error(f'[GEN] {err_msg}')
            with _stats_lock:
                _stats['errors'] += 1
                _stats['last_error'] = f"{time.strftime('%H:%M:%S')} {err_msg[:100]}"
            self._json_response(500, {"error": err_msg})
            return

        with _stats_lock:
            _stats['success'] += 1
            _stats['last_success'] = time.strftime('%H:%M:%S')
        self._json_response(200, {"images": results, "count": len(results)})

    def _handle_image_proxy(self):
        """Serve cached image by ID"""
        img_id = self.path.split("/")[-1]
        with _cache_lock:
            entry = _image_cache.get(img_id)

        if not entry:
            self.send_error(404, "Image not found or expired")
            return

        try:
            img_bytes = base64.b64decode(entry["data"])
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(img_bytes))
            self.send_header('Cache-Control', f'public, max-age={CACHE_TTL}')
            self.send_header('Content-Disposition', f'inline; filename="ai-image-{img_id}.png"')
            self.end_headers()
            self.wfile.write(img_bytes)
        except Exception as e:
            self.send_error(500, str(e))

    def _handle_health(self):
        """Health check with stats"""
        with _stats_lock:
            uptime = (time.time() - _stats['started']) if _stats['started'] else 0
            with _cache_lock:
                cache_count = len(_image_cache)
            with _rate_lock:
                active_ips = len(_rate_map)
            health = {
                "status": "ok",
                "uptime_seconds": round(uptime),
                "uptime_human": f"{int(uptime//3600)}h{int((uptime%3600)//60)}m",
                "total_requests": _stats['requests'],
                "success": _stats['success'],
                "errors": _stats['errors'],
                "error_rate": f"{_stats['errors']/_stats['requests']*100:.1f}%" if _stats['requests'] else "0%",
                "last_error": _stats['last_error'],
                "last_success": _stats['last_success'],
                "cache_images": cache_count,
                "active_ips": active_ips,
                "backend": CHATGPT2API_URL,
            }
        self._json_response(200, health)

    def _handle_logs(self):
        """Return recent logs (password protected)"""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        key = params.get('key', [''])[0]
        if key != 'shujinxing777':
            self._json_response(403, {"error": "Invalid key. Use /api/logs?key=<YOUR_LOG_TOKEN>"})
            return
        n = int(params.get('n', ['50'])[0])
        level = params.get('level', ['all'])[0]
        with _log_buffer_lock:
            logs = list(_log_buffer[-n:])
        if level == 'error':
            logs = [l for l in logs if 'ERROR' in l or 'error' in l.lower() or 'crashed' in l.lower() or 'failed' in l.lower()]
        self._json_response(200, {"count": len(logs), "logs": logs})

    def _json_response(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        log.info(f'[RESP] code={code}, body_len={len(body)}')
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except Exception as e:
            log.error(f'[RESP ERROR] Write failed: {e}')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


if __name__ == '__main__':
    _stats['started'] = time.time()
    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), ImageGenHandler)
    log.info(f"Image Generation Server running on http://0.0.0.0:{PORT}")
    log.info(f"  Backend: {CHATGPT2API_URL}")
    log.info(f"  Health: /api/health | Logs: /api/logs?key=<YOUR_LOG_TOKEN>")
    server.serve_forever()
