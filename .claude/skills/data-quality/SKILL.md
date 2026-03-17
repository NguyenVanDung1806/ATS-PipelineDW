---
name: data-quality
description: Apply when designing data quality checks, freshness monitoring,
  anomaly detection, pipeline observability, or meta.pipeline_runs logging.
  Auto-invoked for: data quality tests, freshness alerts, anomaly checks,
  pipeline monitoring, observability design, meta schema work,
  Slack alerting patterns, SLA monitoring.
allowed-tools: Read, Write, Bash(psql *)
---

# Data Quality Framework

## Freshness check (run as separate DAG or Airflow sensor)
```python
def check_data_freshness(
    table: str,
    max_hours_stale: int = 25,
    ts_column: str = "updated_at"
) -> None:
    """Alert if table hasn't been updated within SLA."""
    hook = PostgresHook(postgres_conn_id="postgres_dw")
    result = hook.get_first(f"""
        SELECT
            MAX({ts_column}) AS last_update,
            EXTRACT(EPOCH FROM (NOW() - MAX({ts_column}))) / 3600 AS hours_stale
        FROM {table}
    """)
    hours_stale = result[1] or 999
    if hours_stale > max_hours_stale:
        slack_alert(
            f":warning: *Data Freshness Alert*\n"
            f"Table `{table}` is {hours_stale:.1f}h stale "
            f"(SLA: {max_hours_stale}h)\n"
            f"Last update: `{result[0]}`"
        )
```

## Anomaly detection (spend spike / lead drop)
```sql
-- Detect spend anomalies: today vs 7-day average
WITH daily_avg AS (
    SELECT
        platform,
        AVG(spend) AS avg_spend_7d,
        STDDEV(spend) AS stddev_spend_7d
    FROM dw.fct_ad_spend
    WHERE date BETWEEN CURRENT_DATE - 8 AND CURRENT_DATE - 1
    GROUP BY platform
),
today AS (
    SELECT platform, SUM(spend) AS today_spend
    FROM dw.fct_ad_spend
    WHERE date = CURRENT_DATE
    GROUP BY platform
)
SELECT
    t.platform,
    t.today_spend,
    a.avg_spend_7d,
    ROUND((t.today_spend - a.avg_spend_7d)
          / NULLIF(a.stddev_spend_7d, 0), 2)  AS z_score,
    CASE
        WHEN ABS((t.today_spend - a.avg_spend_7d)
                 / NULLIF(a.stddev_spend_7d, 0)) > 2
        THEN 'ANOMALY'
        ELSE 'NORMAL'
    END                                        AS status
FROM today t
JOIN daily_avg a USING (platform);
```

## meta.pipeline_runs schema
```sql
CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    id              BIGSERIAL PRIMARY KEY,
    dag_id          TEXT NOT NULL,
    platform        TEXT,
    run_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT CHECK (status IN ('running','success','failed','skipped')),
    rows_extracted  INT DEFAULT 0,
    rows_loaded     INT DEFAULT 0,
    minio_key       TEXT,
    error_message   TEXT,
    duration_secs   INT GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (finished_at - started_at))::INT
    ) STORED
);

-- Index for dashboard queries
CREATE INDEX idx_pipeline_runs_date ON meta.pipeline_runs (run_date DESC);
```

## dbt test extensions (dbt_utils)
```yaml
# In packages.yml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.0.0", "<2.0.0"]

# Custom business rule tests
tests:
  - dbt_utils.expression_is_true:
      expression: "cpl < 10000000"  # CPL < 10M VND sanity check
  - dbt_utils.expression_is_true:
      expression: "sync_rate_pct >= 80"  # EC-04: min 80% sync rate
  - dbt_utils.recency:
      datepart: hour
      field: updated_at
      interval: 25  # freshness SLA
```

## Pipeline health dashboard query
```sql
-- For Metabase: pipeline run summary last 7 days
SELECT
    run_date,
    dag_id,
    platform,
    status,
    rows_extracted,
    rows_loaded,
    duration_secs,
    CASE WHEN status = 'failed' THEN error_message ELSE NULL END AS error
FROM meta.pipeline_runs
WHERE run_date >= CURRENT_DATE - 7
ORDER BY started_at DESC;
```
