"""
Unit tests for Facebook Ads extractor.
No API calls, no MinIO — pure Pydantic validation logic.

Run: python3 -m pytest extractors/facebook/test_extract.py -v
"""
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from extractors.facebook.schema import FbAdInsight


# ── Fixtures ─────────────────────────────────────────────────────────────────

def valid_row(**overrides) -> dict:
    """Minimal valid row matching real FB Insights API response shape."""
    base = {
        "campaign_id": "123456789",
        "campaign_name": "A19 004 ATS PL64 | FBLead | HCM",
        "adset_id": "987654321",
        "adset_name": "Normal+LAL | 18-35",
        "ad_id": "111222333",
        "ad_name": "1_FB_USP_Image_v1",
        "date_start": "2026-03-15",
        "spend": "778.50",        # FB returns spend as string
        "impressions": "1500",    # FB returns as string too
        "clicks": "42",
        "actions": [],            # no leads
    }
    base.update(overrides)
    return base


# ── EC-01: Fail fast on bad numeric data ─────────────────────────────────────

def test_valid_row_passes():
    row = valid_row()
    row["leads"] = 0
    insight = FbAdInsight.model_validate(row)
    assert insight.campaign_id == "123456789"
    assert insight.spend == 778.50
    assert insight.impressions == 1500
    assert insight.clicks == 42
    assert insight.leads == 0


def test_spend_as_string_coerced():
    """FB API returns spend as string — must coerce to float."""
    row = valid_row(spend="12.50")
    row["leads"] = 0
    insight = FbAdInsight.model_validate(row)
    assert insight.spend == 12.50
    assert isinstance(insight.spend, float)


def test_negative_spend_raises():
    """EC-01: negative spend must raise — never load bad data."""
    row = valid_row(spend="-100")
    row["leads"] = 0
    with pytest.raises(ValidationError) as exc_info:
        FbAdInsight.model_validate(row)
    assert "spend" in str(exc_info.value)


def test_null_spend_raises():
    """EC-01: null spend must raise — not default to 0 silently."""
    row = valid_row(spend=None)
    row["leads"] = 0
    with pytest.raises(ValidationError):
        FbAdInsight.model_validate(row)


def test_negative_impressions_raises():
    """EC-01: negative impressions must raise."""
    row = valid_row(impressions="-1")
    row["leads"] = 0
    with pytest.raises(ValidationError):
        FbAdInsight.model_validate(row)


def test_negative_clicks_raises():
    """EC-01: negative clicks must raise."""
    row = valid_row(clicks="-5")
    row["leads"] = 0
    with pytest.raises(ValidationError):
        FbAdInsight.model_validate(row)


# ── EC-05: Leads default to 0 when no lead form ──────────────────────────────

def test_leads_absent_defaults_to_zero():
    """EC-05: no actions → leads = 0."""
    row = valid_row()
    row["leads"] = []  # empty actions list
    insight = FbAdInsight.model_validate(row)
    assert insight.leads == 0


def test_leads_from_native_lead_form():
    """FBLead campaign: action_type='lead'."""
    row = valid_row()
    row["leads"] = [
        {"action_type": "link_click", "value": "42"},
        {"action_type": "lead", "value": "5"},
    ]
    insight = FbAdInsight.model_validate(row)
    assert insight.leads == 5


def test_leads_from_pixel_website_form():
    """FBWebsite.Form campaign: action_type='offsite_conversion.fb_pixel_lead'."""
    row = valid_row()
    row["leads"] = [
        {"action_type": "link_click", "value": "100"},
        {"action_type": "offsite_conversion.fb_pixel_lead", "value": "8"},
    ]
    insight = FbAdInsight.model_validate(row)
    assert insight.leads == 8


def test_leads_pixel_priority_over_native():
    """Double-count prevention: pixel lead takes priority over native lead."""
    row = valid_row()
    row["leads"] = [
        {"action_type": "lead", "value": "10"},
        {"action_type": "offsite_conversion.fb_pixel_lead", "value": "7"},
    ]
    insight = FbAdInsight.model_validate(row)
    # Must NOT sum (10+7=17), must pick pixel (7)
    assert insight.leads == 7


def test_leads_onsite_web_lead_fallback():
    """onsite_web_lead used when no pixel or native lead."""
    row = valid_row()
    row["leads"] = [
        {"action_type": "onsite_web_lead", "value": "3"},
    ]
    insight = FbAdInsight.model_validate(row)
    assert insight.leads == 3


def test_leads_negative_raises():
    """EC-01: negative leads must raise."""
    row = valid_row(leads=-1)
    with pytest.raises(ValidationError):
        FbAdInsight.model_validate(row)


# ── EC-08: Unknown fields ignored ────────────────────────────────────────────

def test_extra_fields_ignored():
    """EC-08: new fields from FB API don't crash pipeline."""
    row = valid_row()
    row["leads"] = 0
    row["new_field_fb_added"] = "some_value"
    row["another_unknown_field"] = 999
    # must not raise
    insight = FbAdInsight.model_validate(row)
    assert insight.campaign_id == "123456789"


# ── EC-06: 7-day lookback ─────────────────────────────────────────────────────

def test_lookback_7_days():
    """EC-06: get_date_range always returns 7-day window."""
    from extractors.facebook.extract import FacebookExtractor
    import os
    # Provide dummy env vars so __init__ doesn't fail
    os.environ.setdefault("FB_ACCESS_TOKEN", "dummy")
    os.environ.setdefault("FB_APP_ID", "dummy")
    os.environ.setdefault("FB_APP_SECRET", "dummy")
    os.environ.setdefault("FB_AD_ACCOUNT_ID", "dummy")

    extractor = FacebookExtractor()
    start, end = extractor.get_date_range()

    assert end == date.today()
    assert start == date.today() - timedelta(days=7)
    assert (end - start).days == 7


# ── to_staging_row mapping ────────────────────────────────────────────────────

def test_to_staging_row_keys():
    """to_staging_row() must match raw.facebook_ads column names exactly."""
    row = valid_row()
    row["leads"] = [{"action_type": "lead", "value": "2"}]
    insight = FbAdInsight.model_validate(row)
    staging = insight.to_staging_row()

    expected_keys = {
        "campaign_id", "campaign_name",
        "ad_set_id", "ad_set_name",
        "ad_id", "ad_name",
        "date", "spend", "impressions", "clicks", "leads",
    }
    assert set(staging.keys()) == expected_keys
    assert staging["leads"] == 2
    assert staging["spend"] == 778.50
    assert staging["date"] == date(2026, 3, 15)
