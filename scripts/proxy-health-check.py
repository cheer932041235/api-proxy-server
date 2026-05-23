#!/usr/bin/env python3
"""
反代账号健康检查 + 邮件告警

检查内容：
1. codex-proxy (8080) 账号状态（读 /root/codex-proxy/data/accounts.json）
   - status 是否 active
   - refreshToken 是否存在
   - JWT 是否即将过期
2. chatgpt2api (3002) 账号状态（HTTP API）
   - status 是否正常
   - JWT 是否即将过期（不支持 refresh_token，必须手动续）
3. codex-proxy error-log.jsonl 中最近的 refresh 失败

异常时通过 QQ SMTP 发邮件到 <YOUR_ALERT_EMAIL>

部署：
  scp 本脚本到 VPS /root/codex-proxy/scripts/
  设置 cron 每天 9:00 跑：
    0 9 * * * QQ_SMTP_PASS=xxx /usr/bin/python3 /root/codex-proxy/scripts/proxy-health-check.py >> /var/log/proxy-health.log 2>&1
"""
import base64
import json
import os
import smtplib
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# === 配置 ===
CODEX_PROXY_ACCOUNTS = os.environ.get('CODEX_PROXY_ACCOUNTS', '/root/codex-proxy/data/accounts.json')
CODEX_PROXY_ERROR_LOG = os.environ.get('CODEX_PROXY_ERROR_LOG', '/root/codex-proxy/data/error-log.jsonl')

CHATGPT2API_PORT = os.environ.get('PORT_CHATGPT2API', '3002')
CHATGPT2API_URL = f'http://localhost:{CHATGPT2API_PORT}/api/accounts'
CHATGPT2API_AUTH = os.environ.get('CHATGPT2API_AUTH_KEY', '')

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.qq.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', os.environ.get('QQ_SMTP_PASS', ''))
RECIPIENT = os.environ.get('ALERT_RECIPIENT', SMTP_USER)
VPS_HOST = os.environ.get('VPS_HOST', 'unknown')
CODEX_PROXY_PORT = os.environ.get('PORT_CODEX_PROXY', '8080')

# === 告警阈值 ===
JWT_WARNING_HOURS = 24          # JWT 剩余 < N 小时告警
RECENT_ERROR_HOURS = 24         # 最近 N 小时内的 refresh 错误算异常
JWT_WARNING_DAYS_CHATGPT2API = 3  # chatgpt2api 没自动续，提前更多天告警


# ─────────────────────────────────────────────────────────────────
def decode_jwt_payload(jwt: str) -> dict:
    """简易 JWT payload 解析（仅 base64 decode，不验签）"""
    try:
        parts = jwt.split('.')
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


def hours_until_exp(exp: int) -> float:
    """返回 JWT 距离过期还有多少小时（负值表示已过期）"""
    if not exp:
        return 0
    return (exp - time.time()) / 3600


# ─────────────────────────────────────────────────────────────────
def check_codex_proxy() -> list:
    """检查 codex-proxy 账号状态"""
    issues = []
    try:
        data = json.loads(Path(CODEX_PROXY_ACCOUNTS).read_text(encoding='utf-8'))
    except Exception as e:
        return [f'⚠️ [codex-proxy] accounts.json 读取失败: {e}']

    accounts = data.get('accounts', [])
    if not accounts:
        return ['⚠️ [codex-proxy] accounts.json 中无账号']

    for acc in accounts:
        aid = acc.get('id', 'unknown')
        email = acc.get('email', aid)
        status = acc.get('status', 'unknown')
        refresh_token = acc.get('refreshToken') or ''
        access_token = acc.get('token') or ''

        # status 异常
        if status not in ('active', 'valid'):
            issues.append(f'❌ [codex-proxy] {email} 状态异常: status={status}')

        # 没有 refresh_token（过期后必须手动 OAuth）
        if not refresh_token:
            issues.append(f'⚠️ [codex-proxy] {email} 缺少 refreshToken（过期后必须重新 OAuth 登录）')

        # JWT 即将过期
        if access_token:
            payload = decode_jwt_payload(access_token)
            exp = payload.get('exp', 0)
            hrs = hours_until_exp(exp)
            if hrs < 0:
                issues.append(f'🔴 [codex-proxy] {email} access_token 已过期 {-hrs:.1f}h 前')
            elif hrs < JWT_WARNING_HOURS and not refresh_token:
                issues.append(f'⏰ [codex-proxy] {email} access_token 剩 {hrs:.1f}h 过期且无 refreshToken')
        else:
            issues.append(f'❌ [codex-proxy] {email} 缺少 access_token')

    return issues


def check_chatgpt2api() -> list:
    """检查 chatgpt2api 账号状态（HTTP API）"""
    issues = []
    try:
        req = urllib.request.Request(
            CHATGPT2API_URL,
            headers={'Authorization': f'Bearer {CHATGPT2API_AUTH}'},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        return [f'⚠️ [chatgpt2api] API 不可达: {e}']
    except Exception as e:
        return [f'⚠️ [chatgpt2api] API 调用失败: {e}']

    items = data.get('items', [])
    if not items:
        return ['⚠️ [chatgpt2api] 号池为空']

    for acc in items:
        email = acc.get('email', 'unknown')
        status = acc.get('status', 'unknown')
        access_token = acc.get('access_token', '')

        if status not in ('正常', 'active', 'valid'):
            issues.append(f'❌ [chatgpt2api] {email} 状态异常: status={status}')

        if access_token:
            payload = decode_jwt_payload(access_token)
            exp = payload.get('exp', 0)
            hrs = hours_until_exp(exp)
            days = hrs / 24
            if hrs < 0:
                issues.append(f'🔴 [chatgpt2api] {email} access_token 已过期 {-hrs:.1f}h 前，需手动重新导入')
            elif days < JWT_WARNING_DAYS_CHATGPT2API:
                issues.append(
                    f'⏰ [chatgpt2api] {email} access_token 剩 {days:.1f} 天过期（chatgpt2api 不支持自动续，需手动导入）'
                )
        else:
            issues.append(f'❌ [chatgpt2api] {email} 缺少 access_token')

    return issues


def check_recent_refresh_errors() -> list:
    """检查 codex-proxy error-log.jsonl 中最近的 refresh/token 失败"""
    issues = []
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_ERROR_HOURS)
        log_path = Path(CODEX_PROXY_ERROR_LOG)
        if not log_path.exists():
            return []
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()

        seen_codes = set()
        for line in lines[-300:]:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            ts_str = entry.get('ts', '')
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except Exception:
                continue
            if ts < cutoff:
                continue
            err = entry.get('error', {}) or {}
            err_name = err.get('name', '')
            err_msg = err.get('message', '')
            # 只关心 refresh/token/auth 相关 + 排除客户端中断（正常）
            if err_name in ('StreamClientAbort', 'StreamUpstreamPrematureClose'):
                continue
            keywords = ('refresh', 'token', 'auth', 'unauthorized', '401', '403')
            text = f'{err_name} {err_msg}'.lower()
            if any(k in text for k in keywords):
                # 去重相同错误
                code = err.get('code', err_name)
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                issues.append(
                    f'🔴 [codex-proxy {ts.strftime("%m-%d %H:%M")}] {err_name}: {err_msg[:120]}'
                )
    except Exception as e:
        issues.append(f'⚠️ error-log 读取失败: {e}')
    return issues


# ─────────────────────────────────────────────────────────────────
def build_email_body(issues: list) -> str:
    return f"""\
<html><body style="font-family: -apple-system, 'Segoe UI', sans-serif; color: #222;">
<h2 style="color: #d33;">⚠️ 反代账号健康告警</h2>
<p><b>检查时间</b>：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><b>VPS</b>：{VPS_HOST}</p>
<h3>异常列表（共 {len(issues)} 项）：</h3>
<ul>
{''.join(f'<li>{issue}</li>' for issue in issues)}
</ul>
<h3>处理建议：</h3>
<ul>
  <li><b>codex-proxy</b>: 打开 <a href="http://{VPS_HOST}:{CODEX_PROXY_PORT}">http://{VPS_HOST}:{CODEX_PROXY_PORT}</a>
    → 先点 <b>"刷新过期"</b> 按钮（有 refreshToken 时可自动续）
    → 不行再点 <b>"+ 添加账户"</b> 走 OAuth（注意复制 localhost:1455 回调 URL 粘贴回 dashboard）</li>
  <li><b>chatgpt2api</b>: 登录 chat.openai.com → 访问 https://chat.openai.com/api/auth/session 复制 accessToken
    → SSH 到 VPS 执行：
    <pre style="background:#f4f4f4;padding:8px;border-radius:4px;">curl -X POST http://localhost:{CHATGPT2API_PORT}/api/accounts \\
  -H "Authorization: Bearer $CHATGPT2API_AUTH_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"tokens":["YOUR_ACCESS_TOKEN"]}}'</pre></li>
</ul>
<hr>
<p style="color:#999;font-size:12px;">本邮件由 proxy-health-check.py 自动发送 · /root/codex-proxy/scripts/</p>
</body></html>
"""


def send_alert(issues: list) -> None:
    if not SMTP_PASS:
        raise RuntimeError('环境变量 QQ_SMTP_PASS 未设置')
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'⚠️ 反代账号告警 - {len(issues)} 项异常'
    msg['From'] = SMTP_USER
    msg['To'] = RECIPIENT
    msg.attach(MIMEText(build_email_body(issues), 'html', 'utf-8'))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(SMTP_USER, [RECIPIENT], msg.as_string())


# ─────────────────────────────────────────────────────────────────
def main():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # --test-email: 强制发一封测试邮件，验证 SMTP 配置
    if '--test-email' in sys.argv:
        print(f'[{ts}] 测试 SMTP 发件...')
        try:
            send_alert(['✅ 这是一封测试邮件，SMTP 配置正常'])
            print(f'[{ts}] ✅ 测试邮件已发送到 {RECIPIENT}')
            sys.exit(0)
        except Exception as e:
            print(f'[{ts}] ❌ 测试邮件失败: {e}', file=sys.stderr)
            sys.exit(1)

    all_issues = []
    all_issues.extend(check_codex_proxy())
    all_issues.extend(check_chatgpt2api())
    all_issues.extend(check_recent_refresh_errors())

    if all_issues:
        print(f'[{ts}] 发现 {len(all_issues)} 项异常：')
        for issue in all_issues:
            print(f'  - {issue}')
        try:
            send_alert(all_issues)
            print(f'[{ts}] ✅ 告警邮件已发送到 {RECIPIENT}')
        except Exception as e:
            print(f'[{ts}] ❌ 邮件发送失败: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        print(f'[{ts}] ✅ 一切正常，已检查 codex-proxy + chatgpt2api + 错误日志')


if __name__ == '__main__':
    main()
