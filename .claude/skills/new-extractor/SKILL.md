---
name: new-extractor
description: Scaffold a complete new platform extractor with all boilerplate.
  Invoke with /new-extractor [platform] to create extract.py, schema.py,
  and test_extract.py for a new data source. Use when adding Facebook,
  Google, TikTok, Zalo, CRM, or any new API extractor to the project.
argument-hint: [platform]
disable-model-invocation: false
---

Scaffold a complete extractor for platform: **$ARGUMENTS**

## Steps to execute

1. **Read reference first**
   - Read `extractors/base/base_extractor.py` — understand the interface
   - Read `extractors/base/minio_client.py` — understand MinIO upload
   - Check if `extractors/$ARGUMENTS/` already exists

2. **Create directory structure**
   ```
   extractors/$ARGUMENTS/
   ├── __init__.py
   ├── extract.py      ← main extractor class
   ├── schema.py       ← Pydantic validation models
   └── test_extract.py ← unit tests for EC-01, EC-02, EC-06
   ```

3. **Write schema.py first** (Pydantic models)
   - All numeric fields: `Field(ge=0)` — EC-01
   - `model_config = ConfigDict(extra="ignore")` — EC-08
   - Include all fields the API actually returns

4. **Write extract.py**
   - Inherit `BaseExtractor`
   - Set `PLATFORM = "$ARGUMENTS"`
   - Implement `extract(start_date, end_date)` — use `self.get_date_range()` (EC-06)
   - Implement `validate(raw)` — validate with Pydantic, fail fast
   - Add `@retry` decorator with tenacity — EC-02

5. **Write test_extract.py**
   - `test_valid_response()` — valid data passes validation
   - `test_null_spend_raises()` — EC-01: null numeric raises ValidationError
   - `test_negative_spend_raises()` — EC-01: negative raises ValidationError
   - `test_extra_fields_ignored()` — EC-08: unknown fields don't crash
   - `test_lookback_7_days()` — EC-06: date range is always 7 days

6. **Run tests**
   ```bash
   python3 -m pytest extractors/$ARGUMENTS/test_extract.py -v
   ```

7. **Apply edge-case-checklist** — run checklist on the new files before finishing

8. **Report**: files created, test results, any issues found
