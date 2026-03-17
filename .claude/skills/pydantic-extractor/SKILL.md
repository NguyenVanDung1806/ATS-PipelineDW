---
name: pydantic-extractor
description: Apply when writing, modifying, fixing, or reviewing any data
  extractor, API client, response parser, or data ingestion script.
  Also triggers on: fix extractor, update parser, debug API response, extraction bug, data fetch, pull from API.
  Auto-invoked for: extract.py, schema.py, any file in extractors/ directory,
  Pydantic models, API response validation, fixing extraction bugs,
  updating parsers, debugging API responses, rate limit handling,
  retry logic, tenacity, data fetch, pull from API, ingest data.
  Also triggers on: fix extractor, update parser, extraction bug,
  response validation, field mapping, ingest data, fetch data.
allowed-tools: Read, Write, Bash(python3 *)
---

# Pydantic Extractor Pattern

## Extractors already built (live — don't duplicate):
!`find extractors -name "extract.py" -not -path "*/base/*" 2>/dev/null | sed 's|extractors/||' | sed 's|/extract.py||' | sort || echo "none yet"`

## Base class (always current):
!`cat extractors/base/base_extractor.py 2>/dev/null | head -60 || echo "base_extractor.py not found"`

## Reference implementation:
!`ls extractors/*/extract.py 2>/dev/null | grep -v base | head -1 | xargs cat 2>/dev/null | head -80 || echo "No reference extractor yet — you are writing the first one"`

---

## Mandatory order of operations — never skip

```
1. Write Pydantic schema (schema.py) FIRST
2. Validate API response against schema
3. Upload raw JSON to MinIO
4. Load validated data to staging
```

## 1. Pydantic Schema (schema.py)

```python
from pydantic import BaseModel, Field, model_validator
from pydantic import ConfigDict
from datetime import date
from typing import Optional

class AdInsight(BaseModel):
    model_config = ConfigDict(extra="ignore")  # EC-08

    date: date
    campaign_id: str
    campaign_name: str
    ad_set_id: Optional[str] = None
    spend: float = Field(ge=0)        # EC-01: non-negative
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    leads: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def validate_clicks_vs_impressions(self) -> "AdInsight":
        if self.impressions > 0 and self.clicks > self.impressions:
            raise ValueError(f"clicks ({self.clicks}) > impressions ({self.impressions})")
        return self
```

## 2. Lookback window — ALWAYS 7 days (EC-06)

```python
from datetime import datetime, timedelta, date

def get_date_range(lookback_days: int = 7) -> tuple[date, date]:
    end = datetime.today().date()
    start = end - timedelta(days=lookback_days)
    return start, end
```

## 3. Retry for rate limits (EC-02)

```python
from tenacity import (
    retry, wait_exponential, stop_after_attempt,
    retry_if_exception_type, before_sleep_log
)

@retry(
    retry=retry_if_exception_type((RateLimitError, TimeoutError)),
    wait=wait_exponential(multiplier=1, min=60, max=300),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def call_api(client, params: dict) -> list[dict]:
    return client.get_insights(params)
```

## 4. MinIO upload BEFORE staging (EC-08 safety net)

```python
def upload_to_minio(data: list[dict], platform: str, run_date: date) -> str:
    key = (
        f"raw/{platform}/ads/year={run_date.year}/"
        f"month={run_date.month:02d}/day={run_date.day:02d}/"
        f"{platform}_{run_date}_{datetime.now().strftime('%H%M%S')}.json"
    )
    client.put_object(Bucket=os.environ["MINIO_BUCKET"],
                      Key=key, Body=json.dumps(data, default=str))
    return key
```

## Edge cases covered
| EC | Issue | Solution |
|----|-------|----------|
| EC-01 | Null/negative fields | `Field(ge=0)` + fail fast |
| EC-02 | Rate limit | tenacity exponential backoff |
| EC-06 | Attribution window | 7-day lookback always |
| EC-08 | API schema change | `extra="ignore"` + MinIO raw |


## 1. Pydantic Schema (schema.py)

```python
from pydantic import BaseModel, Field, model_validator
from datetime import date
from typing import Optional
from pydantic import ConfigDict

class AdInsight(BaseModel):
    model_config = ConfigDict(extra="ignore")  # EC-08: ignore new API fields

    date: date
    campaign_id: str
    campaign_name: str
    ad_set_id: Optional[str] = None
    ad_id: Optional[str] = None
    spend: float = Field(ge=0, description="EC-01: non-negative")
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    leads: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def validate_ctr(self) -> "AdInsight":
        if self.impressions > 0 and self.clicks > self.impressions:
            raise ValueError(f"clicks ({self.clicks}) > impressions ({self.impressions})")
        return self
```

## 2. Lookback window — ALWAYS 7 days (EC-06)

```python
from datetime import datetime, timedelta, date

def get_date_range(lookback_days: int = 7) -> tuple[date, date]:
    """Never pull only 'today' — ad platforms update retroactively."""
    end = datetime.today().date()
    start = end - timedelta(days=lookback_days)
    return start, end
```

## 3. Retry for rate limits (EC-02)

```python
from tenacity import (
    retry, wait_exponential, stop_after_attempt,
    retry_if_exception_type, before_sleep_log
)
import logging

logger = logging.getLogger(__name__)

@retry(
    retry=retry_if_exception_type((RateLimitError, TimeoutError, ConnectionError)),
    wait=wait_exponential(multiplier=1, min=60, max=300),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def call_api_with_retry(client, params: dict) -> list[dict]:
    return client.get_insights(params)
```

## 4. MinIO upload BEFORE staging (EC-08 safety net)

```python
import boto3, json, os
from datetime import date, datetime

def upload_raw_to_minio(data: list[dict], platform: str, run_date: date) -> str:
    """Raw JSON is immutable. If schema changes, reprocess from here."""
    key = (
        f"raw/{platform}/ads/"
        f"year={run_date.year}/month={run_date.month:02d}/"
        f"day={run_date.day:02d}/"
        f"{platform}_{run_date}_{datetime.now().strftime('%H%M%S')}.json"
    )
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
    )
    client.put_object(
        Bucket=os.environ.get("MINIO_BUCKET", "datalake"),
        Key=key,
        Body=json.dumps(data, default=str),
        ContentType="application/json",
    )
    logger.info(f"Uploaded {len(data)} records → minio://{key}")
    return key
```

## Edge cases this skill enforces

| EC | Issue | This skill's solution |
|----|-------|----------------------|
| EC-01 | Null/negative fields | Pydantic `Field(ge=0)`, fail fast |
| EC-02 | Rate limit | tenacity retry, exponential backoff |
| EC-06 | Attribution window | 7-day lookback, not just today |
| EC-08 | API schema change | `extra="ignore"`, raw in MinIO to reprocess |
| EC-09 | Data not finalized | Schedule at 9h ICT (2h UTC) |

## Read before writing any extractor

1. `extractors/base/base_extractor.py` — inherit this
2. `extractors/base/minio_client.py` — use this for uploads
3. Any existing extractor in `extractors/` — follow the pattern
