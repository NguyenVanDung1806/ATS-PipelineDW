"""
Facebook Ads extractor.
Pulls Insights data at ad-level, validates with Pydantic, uploads to MinIO.

EC-01: Pydantic validation fails fast — bad rows raise, never load silently.
EC-02: tenacity retry with exponential backoff for FB rate limits (200/hr).
EC-05: leads default to 0 when no lead form attached.
EC-06: Always lookback 7 days (attribution window).
GOTCHA: Use time_range dict, NOT date_preset — from CLAUDE.md known gotchas.
GOTCHA: Ad account ID must be "act_XXXXXXXXX" format.
"""
import logging
import os
import time
from datetime import date
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from extractors.base.base_extractor import BaseExtractor
from extractors.facebook.schema import FbAdInsight

logger = logging.getLogger(__name__)

# FB Insights API fields to request
INSIGHTS_FIELDS = [
    "campaign_id",
    "campaign_name",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "date_start",
    "spend",
    "impressions",
    "clicks",
    "actions",  # contains leads — parsed by FbAdInsight.parse_leads_from_actions
]

FB_API_VERSION = "v19.0"
FB_BASE_URL = f"https://graph.facebook.com/{FB_API_VERSION}"


class FbRateLimitError(Exception):
    """Raised when FB API returns rate limit response (EC-02)."""


class FacebookExtractor(BaseExtractor):

    PLATFORM = "facebook"
    LOOKBACK_DAYS = 7  # EC-06: attribution window

    def __init__(self) -> None:
        self.access_token = os.environ["FB_ACCESS_TOKEN"]
        self.app_id = os.environ["FB_APP_ID"]
        self.app_secret = os.environ["FB_APP_SECRET"]
        # Ensure "act_" prefix — GOTCHA from CLAUDE.md
        raw_account_id = os.environ["FB_AD_ACCOUNT_ID"]
        self.ad_account_id = (
            raw_account_id
            if raw_account_id.startswith("act_")
            else f"act_{raw_account_id}"
        )

    def extract(self, start_date: date, end_date: date) -> list[dict]:
        """
        Pull ad-level Insights from FB API for the given date range.
        Paginates automatically using cursor-based pagination.
        """
        url = f"{FB_BASE_URL}/{self.ad_account_id}/insights"
        params = {
            "access_token": self.access_token,
            "fields": ",".join(INSIGHTS_FIELDS),
            "level": "ad",
            "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',  # GOTCHA: time_range dict
            "time_increment": 1,  # one row per day per ad
            "limit": 500,         # max per page
        }

        all_rows: list[dict] = []
        page_num = 0

        while True:
            page_num += 1
            data = self._request_with_retry(url, params)

            rows = data.get("data", [])
            all_rows.extend(rows)
            logger.info(
                f"[facebook] Page {page_num}: {len(rows)} rows "
                f"(total so far: {len(all_rows)})"
            )

            # Cursor-based pagination
            paging = data.get("paging", {})
            next_cursor = paging.get("cursors", {}).get("after")
            if not paging.get("next") or not next_cursor:
                break

            params["after"] = next_cursor

        logger.info(
            f"[facebook] Extracted {len(all_rows)} rows "
            f"for {start_date} → {end_date}"
        )
        return all_rows

    def validate(self, raw: list[dict]) -> list[FbAdInsight]:
        """
        Validate each row with Pydantic FbAdInsight.
        EC-01: raises ValidationError immediately on bad data — never swallow.
        """
        validated = []
        for i, row in enumerate(raw):
            # Extract leads from actions array before passing to Pydantic
            row_with_leads = self._extract_leads_field(row)
            insight = FbAdInsight.model_validate(row_with_leads)
            validated.append(insight)

        logger.info(f"[facebook] Validated {len(validated)}/{len(raw)} rows")
        return validated

    # ── Private helpers ──────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(FbRateLimitError),
        wait=wait_exponential(multiplier=1, min=60, max=240),  # EC-02: 60→120→240s
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _request_with_retry(self, url: str, params: dict) -> dict:
        """
        Make GET request to FB API with retry on rate limit.
        EC-02: exponential backoff 60→120→240s on rate limit errors.
        """
        response = requests.get(url, params=params, timeout=30)

        # Check for rate limit (HTTP 429 or FB error code 17/32/613)
        if response.status_code == 429:
            logger.warning("[facebook] Rate limit hit (HTTP 429) — will retry")
            raise FbRateLimitError("HTTP 429 rate limit")

        if response.status_code != 200:
            error_body = response.json().get("error", {})
            error_code = error_body.get("code", 0)
            if error_code in (17, 32, 613):
                logger.warning(
                    f"[facebook] Rate limit hit (code {error_code}) — will retry"
                )
                raise FbRateLimitError(f"FB error code {error_code}")

            raise RuntimeError(
                f"[facebook] API error {response.status_code}: {response.text[:300]}"
            )

        return response.json()

    def _extract_leads_field(self, row: dict) -> dict:
        """
        Move 'actions' array to 'leads' key so Pydantic validator can parse it.
        FbAdInsight.parse_leads_from_actions handles both formats.
        """
        row = dict(row)  # shallow copy — don't mutate original raw data
        if "actions" in row and "leads" not in row:
            row["leads"] = row["actions"]
        return row
