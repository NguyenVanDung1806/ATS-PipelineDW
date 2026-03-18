"""
Quick test script — verify FB credentials và pull sample data.
Không cần MinIO/Docker. Chạy trực tiếp từ host machine.

Usage:
    python3 scripts/test_fb_credentials.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Load .env manually (không cần python-dotenv)
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

FB_API_VERSION = "v19.0"
FB_BASE_URL = f"https://graph.facebook.com/{FB_API_VERSION}"


def check_env_vars():
    required = ["FB_ACCESS_TOKEN", "FB_APP_ID", "FB_APP_SECRET", "FB_AD_ACCOUNT_ID"]
    missing = [k for k in required if not os.environ.get(k) or os.environ[k] == "CHANGE_ME"]
    if missing:
        print(f"❌ Missing env vars: {missing}")
        sys.exit(1)
    print("✅ Env vars: OK")


def test_token_valid():
    """Verify access token is valid."""
    token = os.environ["FB_ACCESS_TOKEN"]
    resp = requests.get(
        f"{FB_BASE_URL}/me",
        params={"access_token": token, "fields": "id,name"},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Token valid — User/App: {data.get('name', data.get('id'))}")
        return True
    else:
        err = resp.json().get("error", {})
        print(f"❌ Token invalid: {err.get('message', resp.text[:200])}")
        return False


def test_ad_account_access():
    """Verify ad account accessible."""
    token = os.environ["FB_ACCESS_TOKEN"]
    raw_id = os.environ["FB_AD_ACCOUNT_ID"]
    account_id = raw_id if raw_id.startswith("act_") else f"act_{raw_id}"

    resp = requests.get(
        f"{FB_BASE_URL}/{account_id}",
        params={
            "access_token": token,
            "fields": "id,name,account_status,currency",
        },
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        status_map = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_REVIEW"}
        acct_status = status_map.get(data.get("account_status"), "UNKNOWN")
        print(f"✅ Ad Account: {data.get('name')} | Status: {acct_status} | Currency: {data.get('currency')}")
        return True
    else:
        err = resp.json().get("error", {})
        print(f"❌ Ad account error: {err.get('message', resp.text[:200])}")
        return False


def test_pull_sample_data():
    """Pull last 3 days data — verify fields & row count."""
    token = os.environ["FB_ACCESS_TOKEN"]
    raw_id = os.environ["FB_AD_ACCOUNT_ID"]
    account_id = raw_id if raw_id.startswith("act_") else f"act_{raw_id}"

    end = date.today()
    start = end - timedelta(days=3)

    resp = requests.get(
        f"{FB_BASE_URL}/{account_id}/insights",
        params={
            "access_token": token,
            "fields": "campaign_id,campaign_name,adset_id,ad_id,ad_name,date_start,spend,impressions,clicks,actions",
            "level": "ad",
            "time_range": f'{{"since":"{start}","until":"{end}"}}',
            "time_increment": 1,
            "limit": 10,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        err = resp.json().get("error", {})
        print(f"❌ Insights API error: {err.get('message', resp.text[:200])}")
        return False

    data = resp.json().get("data", [])
    print(f"✅ Insights API: {len(data)} rows for {start} → {end}")

    if data:
        sample = data[0]
        print(f"\n   Sample row:")
        print(f"   Campaign : {sample.get('campaign_name', 'N/A')}")
        print(f"   Ad       : {sample.get('ad_name', 'N/A')}")
        print(f"   Date     : {sample.get('date_start')}")
        print(f"   Spend    : {sample.get('spend', '0')}")
        print(f"   Impressions: {sample.get('impressions', '0')}")
        print(f"   Clicks   : {sample.get('clicks', '0')}")
        # Parse leads: cả native lead form + website form (FB Pixel)
        LEAD_TYPES = {"lead", "offsite_conversion.fb_pixel_lead"}
        actions = sample.get("actions", [])
        leads = sum(int(a.get("value", 0)) for a in actions if a.get("action_type") in LEAD_TYPES)
        all_action_types = [a.get("action_type") for a in actions]
        print(f"   Leads    : {leads}")
        print(f"   Actions  : {all_action_types}")
    else:
        print("   (No data in this date range — campaign may be paused)")

    return True


def test_pydantic_validation():
    """Test schema.py validates real API response correctly."""
    from extractors.facebook.schema import FbAdInsight

    # Pull 1 real row and validate it
    token = os.environ["FB_ACCESS_TOKEN"]
    raw_id = os.environ["FB_AD_ACCOUNT_ID"]
    account_id = raw_id if raw_id.startswith("act_") else f"act_{raw_id}"

    end = date.today()
    start = end - timedelta(days=3)

    resp = requests.get(
        f"{FB_BASE_URL}/{account_id}/insights",
        params={
            "access_token": token,
            "fields": "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,date_start,spend,impressions,clicks,actions",
            "level": "ad",
            "time_range": f'{{"since":"{start}","until":"{end}"}}',
            "time_increment": 1,
            "limit": 1,
        },
        timeout=30,
    )

    data = resp.json().get("data", [])
    if not data:
        print("⚠️  Pydantic validation: skipped (no data rows)")
        return True

    row = data[0]
    # Move actions → leads for validator
    row["leads"] = row.get("actions", [])

    try:
        insight = FbAdInsight.model_validate(row)
        print(f"✅ Pydantic validation: OK — spend={insight.spend}, leads={insight.leads}")
        return True
    except Exception as e:
        print(f"❌ Pydantic validation failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Facebook Ads — Credential & Data Test")
    print("=" * 50)

    check_env_vars()

    results = []
    results.append(test_token_valid())
    results.append(test_ad_account_access())
    results.append(test_pull_sample_data())
    results.append(test_pydantic_validation())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    if all(results):
        print(f"✅ All {total} tests passed — Facebook credentials OK!")
        print("   Next: python3 -m pytest extractors/facebook/test_extract.py -v")
    else:
        print(f"❌ {total - passed}/{total} tests failed — fix errors above")
    print("=" * 50)
