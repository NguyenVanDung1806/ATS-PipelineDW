"""
Base extractor — all platform extractors inherit this.
Implements: lookback window, MinIO upload, run() orchestration.
"""
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any
import json, logging, os

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Inherit this for every platform extractor.
    Only implement: extract() and validate().
    run() handles the full orchestration.
    """

    PLATFORM: str = ""       # override: "facebook", "google", etc.
    LOOKBACK_DAYS: int = 7   # EC-06: ad platform attribution window

    def get_date_range(self, lookback_days: int | None = None) -> tuple[date, date]:
        """Always lookback — never pull only 'today'. EC-06."""
        days = lookback_days or self.LOOKBACK_DAYS
        end = datetime.today().date()
        start = end - timedelta(days=days)
        return start, end

    def upload_to_minio(self, data: list[dict], run_date: date) -> str:
        """
        Upload raw JSON to MinIO BEFORE staging load.
        This is the safety net for EC-08 (API schema changes).
        Raw data is immutable — never delete, never update.
        """
        from extractors.base.minio_client import get_minio_client

        key = (
            f"raw/{self.PLATFORM}/ads/"
            f"year={run_date.year}/month={run_date.month:02d}/"
            f"day={run_date.day:02d}/"
            f"{self.PLATFORM}_{run_date}_{datetime.now().strftime('%H%M%S')}.json"
        )
        client = get_minio_client()
        client.put_object(
            Bucket=os.environ.get("MINIO_BUCKET", "datalake"),
            Key=key,
            Body=json.dumps(data, default=str),
            ContentType="application/json",
        )
        logger.info(f"[{self.PLATFORM}] Uploaded {len(data)} records → {key}")
        return key

    @abstractmethod
    def extract(self, start_date: date, end_date: date) -> list[dict]:
        """Pull raw data from platform API. Return list of dicts."""
        ...

    @abstractmethod
    def validate(self, raw: list[dict]) -> list[Any]:
        """
        Validate with Pydantic. Raise ValidationError on bad data (EC-01).
        Never catch and swallow validation errors.
        """
        ...

    def run(self) -> dict:
        """
        Orchestrate: extract → validate → upload MinIO → return metadata.
        Loading to staging is handled by the Airflow task after run().
        """
        start, end = self.get_date_range()
        logger.info(f"[{self.PLATFORM}] Extracting: {start} → {end}")

        raw = self.extract(start, end)
        logger.info(f"[{self.PLATFORM}] Extracted {len(raw)} raw records")

        validated = self.validate(raw)  # EC-01: fails fast on bad data
        logger.info(f"[{self.PLATFORM}] Validated {len(validated)} records")

        minio_key = self.upload_to_minio(raw, end)

        return {
            "platform": self.PLATFORM,
            "start_date": str(start),
            "end_date": str(end),
            "rows_extracted": len(raw),
            "rows_validated": len(validated),
            "minio_key": minio_key,
        }
