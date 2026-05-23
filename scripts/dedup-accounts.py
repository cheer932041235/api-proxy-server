#!/usr/bin/env python3
"""Dedupe chatgpt2api accounts.json by email, keep entry with latest exp."""
import json
import base64
import time
import shutil
import sys

PATH = "/root/chatgpt2api-data/accounts.json"


def jwt_exp(tok):
    if not tok:
        return 0
    try:
        p = tok.split(".")[1]
        p += "=" * (4 - len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get("exp", 0)
    except Exception:
        return 0


with open(PATH) as f:
    data = json.load(f)

# Normalize: data could be list or dict with 'accounts' / 'items'
if isinstance(data, list):
    items = data
    container_key = None
elif "accounts" in data:
    items = data["accounts"]
    container_key = "accounts"
elif "items" in data:
    items = data["items"]
    container_key = "items"
else:
    print(f"ERROR: unexpected JSON structure, keys={list(data.keys())}")
    sys.exit(1)

now = time.time()

print(f"BEFORE: {len(items)} entries")
for i, a in enumerate(items):
    exp = jwt_exp(a.get("access_token", ""))
    days = (exp - now) / 86400 if exp else 0
    print(f"  [{i}] {a.get('email','?'):28} exp_in={days:5.1f}d quota={a.get('quota')}")

# Dedupe: keep entry with highest exp per email
by_email = {}
for a in items:
    email = a.get("email", "")
    exp = jwt_exp(a.get("access_token", ""))
    if email not in by_email or jwt_exp(by_email[email].get("access_token", "")) < exp:
        by_email[email] = a

new_items = list(by_email.values())

print(f"\nAFTER: {len(new_items)} entries")
for a in new_items:
    exp = jwt_exp(a.get("access_token", ""))
    days = (exp - now) / 86400 if exp else 0
    print(f"  {a.get('email','?'):28} exp_in={days:5.1f}d quota={a.get('quota')}")

# Backup
backup = PATH + ".bak-dedup-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy(PATH, backup)
print(f"\nBackup: {backup}")

# Write
if container_key is None:
    new_data = new_items
else:
    data[container_key] = new_items
    new_data = data

with open(PATH, "w") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)

print("Saved.")
