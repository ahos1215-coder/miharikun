"""NK データの needs_review を全件 false に戻す（緊急修正）"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import requests

try:
    from utils.supabase_client import get_supabase_url, get_supabase_headers
except ImportError:
    from supabase_client import get_supabase_url, get_supabase_headers

url = get_supabase_url()
headers = get_supabase_headers()

# NK の needs_review を全件 false に
resp = requests.patch(
    f"{url}/rest/v1/regulations",
    params={"source": "eq.nk"},
    json={"needs_review": False},
    headers={**headers, "Prefer": "return=minimal"},
    timeout=30,
)
print(f"NK needs_review=false 更新: HTTP {resp.status_code}")

# 確認
resp2 = requests.get(
    f"{url}/rest/v1/regulations",
    params={"source": "eq.nk", "select": "id", "limit": "1000"},
    headers=headers,
    timeout=30,
)
print(f"NK 全件数: {len(resp2.json())}")

resp3 = requests.get(
    f"{url}/rest/v1/regulations",
    params={"source": "eq.nk", "needs_review": "eq.true", "select": "id", "limit": "1000"},
    headers=headers,
    timeout=30,
)
print(f"NK hidden件数: {len(resp3.json())}")
