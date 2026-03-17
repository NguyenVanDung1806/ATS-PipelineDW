#!/usr/bin/env python3
"""
Create all Airflow connections required by ATS pipelines.
Run after Docker services are up: python3 scripts/setup/init_airflow_connections.py
"""
import subprocess, sys, os, json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"
BOLD = "\033[1m"; RESET = "\033[0m"
def ok(msg):   print(f"  {G}✓{RESET} {msg}")
def fail(msg): print(f"  {R}✗{RESET} {R}{msg}{RESET}")
def info(msg): print(f"  {B}·{RESET} {msg}")
def warn(msg): print(f"  {Y}⚠{RESET} {Y}{msg}{RESET}")


def load_env() -> dict:
    env = {}
    env_file = ROOT / ".env"
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def airflow_cmd(args: list) -> tuple[bool, str]:
    """Run airflow CLI inside the webserver container."""
    cmd = ["docker", "exec", "de_airflow_web", "airflow"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def connection_exists(conn_id: str) -> bool:
    ok_flag, out = airflow_cmd(["connections", "get", conn_id])
    return ok_flag


def upsert_connection(conn_id: str, args: list, description: str):
    """Delete if exists, then add fresh."""
    if connection_exists(conn_id):
        airflow_cmd(["connections", "delete", conn_id])

    ok_flag, out = airflow_cmd(["connections", "add", conn_id] + args)
    if ok_flag:
        ok(f"{conn_id} — {description}")
    else:
        fail(f"{conn_id}: {out[-200:]}")
    return ok_flag


def setup_connections(env: dict):
    pg_user  = env.get("POSTGRES_USER", "ats_admin")
    pg_pass  = env.get("POSTGRES_PASSWORD", "")
    pg_db    = env.get("POSTGRES_DB", "ats_dw")

    minio_key    = env.get("MINIO_ACCESS_KEY", "")
    minio_secret = env.get("MINIO_SECRET_KEY", "")
    minio_endpoint = env.get("MINIO_ENDPOINT", "http://minio:9000")

    slack_url = env.get("SLACK_WEBHOOK_URL", "")

    fb_token    = env.get("FB_ACCESS_TOKEN", "PLACEHOLDER")
    fb_app_id   = env.get("FB_APP_ID", "")
    fb_app_secret = env.get("FB_APP_SECRET", "")

    crm_base_url = env.get("CRM_BASE_URL", "http://crm.placeholder.local")
    crm_api_key  = env.get("CRM_API_KEY", "PLACEHOLDER")

    connections = [
        # ── PostgreSQL ──────────────────────────────────────────────────────
        (
            "postgres_ats",
            [
                "--conn-type", "postgres",
                "--conn-host", "postgres",          # Docker internal hostname
                "--conn-port", "5432",              # Internal port (not 5434)
                "--conn-login", pg_user,
                "--conn-password", pg_pass,
                "--conn-schema", pg_db,
            ],
            "PostgreSQL ATS DW (internal Docker network)"
        ),
        # ── MinIO (S3-compatible) ───────────────────────────────────────────
        (
            "minio_ats",
            [
                "--conn-type", "aws",
                "--conn-login", minio_key,
                "--conn-password", minio_secret,
                "--conn-extra", json.dumps({
                    "endpoint_url": "http://minio:9000",
                    "region_name": "us-east-1",
                }),
            ],
            "MinIO S3 (internal Docker network)"
        ),
        # ── Slack ───────────────────────────────────────────────────────────
        (
            "slack_default",
            [
                "--conn-type", "http",
                "--conn-host", "hooks.slack.com",
                "--conn-schema", "https",
                "--conn-password", slack_url,
            ],
            "Slack webhook for pipeline alerts"
        ),
        # ── Facebook Ads API ────────────────────────────────────────────────
        (
            "fb_ads",
            [
                "--conn-type", "http",
                "--conn-host", "graph.facebook.com",
                "--conn-schema", "https",
                "--conn-extra", json.dumps({
                    "access_token": fb_token,
                    "app_id": fb_app_id,
                    "app_secret": fb_app_secret,
                }),
            ],
            "Facebook Graph API"
        ),
        # ── CRM Live1 ───────────────────────────────────────────────────────
        (
            "crm_live1",
            [
                "--conn-type", "http",
                "--conn-host", crm_base_url.replace("https://", "").replace("http://", ""),
                "--conn-schema", "https" if crm_base_url.startswith("https") else "http",
                "--conn-extra", json.dumps({
                    "api_key": crm_api_key,
                }),
            ],
            "CRM Live1 API"
        ),
    ]

    results = []
    for conn_id, args, description in connections:
        success = upsert_connection(conn_id, args, description)
        results.append((conn_id, success))

    return results


def verify_connections():
    print(f"\n{BOLD}Verification:{RESET}")
    ok_flag, out = airflow_cmd(["connections", "list"])
    if ok_flag:
        for line in out.splitlines():
            if any(c in line for c in ["postgres_ats", "minio_ats", "slack_default", "fb_ads", "crm_live1"]):
                print(f"  {G}·{RESET} {line.strip()}")
    else:
        warn("Could not list connections")


def main():
    print(f"\n{BOLD}{B}ATS — Airflow Connections Setup{RESET}\n{'═'*42}")

    # Load env
    try:
        env = load_env()
        ok(".env loaded")
    except Exception as e:
        fail(f"Could not load .env: {e}")
        sys.exit(1)

    # Check Docker container is running
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "de_airflow_web"],
                       capture_output=True, text=True)
    if r.stdout.strip() != "true":
        fail("de_airflow_web container is not running — run: make up")
        sys.exit(1)
    ok("Airflow container reachable")

    # Warn about placeholder connections
    if not env.get("FB_ACCESS_TOKEN") or env.get("FB_ACCESS_TOKEN") == "PLACEHOLDER":
        warn("FB_ACCESS_TOKEN not set in .env — fb_ads connection created as placeholder")
    if not env.get("CRM_API_KEY") or env.get("CRM_API_KEY") == "PLACEHOLDER":
        warn("CRM_API_KEY not set in .env — crm_live1 connection created as placeholder")

    print(f"\n{BOLD}Creating connections:{RESET}")
    results = setup_connections(env)

    verify_connections()

    failed = [c for c, s in results if not s]
    print(f"\n{'═'*42}")
    if failed:
        fail(f"Failed connections: {', '.join(failed)}")
        sys.exit(1)
    else:
        ok(f"All {len(results)} connections created successfully")
        info("View in Airflow UI: http://localhost:8080/connection/list/")


if __name__ == "__main__":
    main()
