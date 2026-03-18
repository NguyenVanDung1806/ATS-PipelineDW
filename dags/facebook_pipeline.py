"""
Facebook Ads Pipeline DAG.
Schedule: 09:00 ICT daily (02:00 UTC) — EC-09
Flow: extract → MinIO → staging → dbt stg → dbt fct → log

Skills auto-loaded when editing: airflow-dag-pattern, edge-case-checklist
"""
from datetime import datetime, timedelta

import requests
import os
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator

PLATFORM = "facebook"
SCHEDULE = "0 2 * * *"   # 09:00 ICT — EC-09, staggered: FB first
POSTGRES_CONN_ID = "postgres_ats"   # matches init_airflow_connections.py


# ── Alerting (REQUIRED — never remove) ───────────────────────────────────────

def slack_alert_failure(context: dict) -> None:
    """Rule #11: fail loudly — Slack alert on every pipeline failure."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL not set — skipping alert")
        return

    dag_id  = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    error   = str(context.get("exception", "Unknown"))[:400]
    log_url = context["task_instance"].log_url

    requests.post(
        webhook_url,
        json={"text": (
            f":rotating_light: *Pipeline FAILED*\n"
            f"DAG: `{dag_id}` | Task: `{task_id}`\n"
            f"Error: ```{error}```\n"
            f"<{log_url}|View logs>"
        )},
        timeout=10,
    )


# ── Tasks ─────────────────────────────────────────────────────────────────────

def task_extract(**context) -> dict:
    """
    Extract all FB Ads data → validate (Pydantic) → upload to MinIO.
    Returns metadata dict pushed to XCom.
    """
    from extractors.facebook.extract import FacebookExtractor
    extractor = FacebookExtractor()
    result = extractor.run()
    context["task_instance"].xcom_push(key="extract_result", value=result)
    return result


def task_load_staging(**context) -> int:
    """
    TRUNCATE raw.facebook_ads, then INSERT validated rows.
    Data comes from extractor.run() via re-extract (avoid XCom size limit).
    Rule: staging is always fresh — never append.
    """
    import requests as req
    import json
    import boto3

    ti = context["task_instance"]
    result = ti.xcom_pull(task_ids="extract", key="extract_result")
    minio_key = result["minio_key"]

    # Load raw JSON from MinIO (source of truth — EC-08)
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
    )
    obj = s3.get_object(Bucket=os.environ.get("MINIO_BUCKET", "ats-datalake"), Key=minio_key)
    raw_rows = json.loads(obj["Body"].read())

    # Re-validate (Pydantic) before staging insert
    from extractors.facebook.schema import FbAdInsight
    validated = []
    for row in raw_rows:
        row["leads"] = row.get("actions", [])
        validated.append(FbAdInsight.model_validate(row).to_staging_row())

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)

    # TRUNCATE first — staging is always fresh (Rule: idempotent)
    hook.run("TRUNCATE TABLE raw.facebook_ads")

    # Bulk INSERT
    if validated:
        hook.insert_rows(
            table="raw.facebook_ads",
            rows=[
                (
                    r["campaign_id"], r["campaign_name"],
                    r["ad_set_id"], r["ad_set_name"],
                    r["ad_id"], r["ad_name"],
                    r["date"], r["spend"],
                    r["impressions"], r["clicks"], r["leads"],
                )
                for r in validated
            ],
            target_fields=[
                "campaign_id", "campaign_name",
                "ad_set_id", "ad_set_name",
                "ad_id", "ad_name",
                "date", "spend",
                "impressions", "clicks", "leads",
            ],
            commit_every=500,
        )

    rows_loaded = len(validated)
    print(f"[facebook] Loaded {rows_loaded} rows → raw.facebook_ads")
    return rows_loaded


def task_log_run(status: str = "success", **context) -> None:
    """Append run metadata to meta.pipeline_runs (observability)."""
    ti = context["task_instance"]
    result = ti.xcom_pull(task_ids="extract", key="extract_result") or {}

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    hook.run(
        """
        INSERT INTO meta.pipeline_runs
            (dag_id, platform, run_date, status,
             rows_extracted, rows_loaded, minio_key, finished_at)
        VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, NOW())
        """,
        parameters=(
            context["dag"].dag_id,
            PLATFORM,
            status,
            result.get("rows_extracted", 0),
            result.get("rows_validated", 0),
            result.get("minio_key"),
        ),
    )


# ── DAG definition ────────────────────────────────────────────────────────────

default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "on_failure_callback": slack_alert_failure,
    "execution_timeout": timedelta(hours=2),
    "depends_on_past": False,
}

with DAG(
    dag_id="facebook_pipeline",
    default_args=default_args,
    description="Facebook Ads → MinIO → Staging → dbt → DW",
    schedule_interval=SCHEDULE,
    start_date=datetime(2026, 3, 1),
    catchup=False,
    max_active_runs=1,
    tags=["marketing", "facebook", "daily"],
) as dag:

    extract = PythonOperator(
        task_id="extract",
        python_callable=task_extract,
    )

    load_staging = PythonOperator(
        task_id="load_staging",
        python_callable=task_load_staging,
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt run --select stg_facebook_ads --no-version-check --target prod"
        ),
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt test --select stg_facebook_ads --no-version-check --target prod"
        ),
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt run --select fct_ad_spend --no-version-check --target prod"
        ),
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt test --select fct_ad_spend --no-version-check --target prod"
        ),
    )

    log_success = PythonOperator(
        task_id="log_success",
        python_callable=task_log_run,
        op_kwargs={"status": "success"},
        trigger_rule="all_success",
    )

    # ── Dependencies ──────────────────────────────────────────────────────────
    (
        extract
        >> load_staging
        >> dbt_run_staging
        >> dbt_test_staging
        >> dbt_run_marts
        >> dbt_test_marts
        >> log_success
    )
