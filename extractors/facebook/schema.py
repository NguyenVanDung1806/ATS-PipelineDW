"""
Pydantic validation models for Facebook Ads Insights API response.

EC-01: All numeric fields have ge=0 — fail fast on bad data, never load nulls.
EC-08: model_config extra='ignore' — unknown fields from API don't crash pipeline.
"""
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FbAdInsight(BaseModel):
    """
    One row from the FB Insights API at ad-level granularity.
    Maps directly to raw.facebook_ads staging table columns.
    """

    model_config = ConfigDict(extra="ignore")  # EC-08: ignore new fields silently

    # Identifiers
    campaign_id: str
    campaign_name: str
    adset_id: str
    adset_name: str
    ad_id: str
    ad_name: str

    # Date — FB returns "date_start" string, we alias it to "date"
    date_start: str  # kept as str here, coerced to date in property below

    # Metrics — EC-01: all must be >= 0
    spend: float = Field(ge=0.0)          # FB returns string "12.50" — coerced below
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    leads: int = Field(default=0, ge=0)   # EC-05: may be absent if no lead form

    @field_validator("spend", mode="before")
    @classmethod
    def coerce_spend(cls, v: Any) -> float:
        """FB Insights API returns spend as a string — coerce to float."""
        try:
            return float(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"spend must be numeric, got: {v!r}") from e

    @field_validator("impressions", "clicks", mode="before")
    @classmethod
    def coerce_int_metrics(cls, v: Any) -> int:
        """FB returns impressions/clicks as strings occasionally."""
        try:
            return int(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"metric must be integer, got: {v!r}") from e

    @field_validator("leads", mode="before")
    @classmethod
    def parse_leads_from_actions(cls, v: Any) -> int:
        """
        FB Insights API returns leads inside the 'actions' array:
          [{"action_type": "lead", "value": "3"}, ...]

        This validator handles both:
          - Pre-parsed int (already extracted upstream)
          - Raw actions list from API response (extracted here)
          - Missing entirely → defaults to 0 (EC-05)
        """
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 0
        if isinstance(v, list):
            # ATS dùng 3 loại lead tracking, nhưng tránh double-count:
            # Priority: offsite_conversion.fb_pixel_lead > lead > onsite_web_lead
            # Lý do: nhiều campaign có cả "lead" và "offsite_conversion.fb_pixel_lead"
            # trong cùng 1 row → cộng cả 2 sẽ đếm trùng.
            # CRM là source of truth (Rule #9) — FB leads chỉ để tham khảo CPL sơ bộ.
            action_map = {
                a.get("action_type"): int(a.get("value", 0))
                for a in v
                if isinstance(a, dict)
            }
            # Ưu tiên pixel lead (website form) nếu có
            if "offsite_conversion.fb_pixel_lead" in action_map:
                return action_map["offsite_conversion.fb_pixel_lead"]
            # Fallback: FB native lead form
            if "lead" in action_map:
                return action_map["lead"]
            # Fallback: onsite web lead
            if "onsite_web_lead" in action_map:
                return action_map["onsite_web_lead"]
            return 0
        return 0

    @property
    def date(self) -> date:
        """Parsed date from date_start string (YYYY-MM-DD)."""
        return date.fromisoformat(self.date_start)

    def to_staging_row(self) -> dict:
        """Convert to dict matching raw.facebook_ads column names."""
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "ad_set_id": self.adset_id,
            "ad_set_name": self.adset_name,
            "ad_id": self.ad_id,
            "ad_name": self.ad_name,
            "date": self.date,
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "leads": self.leads,
        }
