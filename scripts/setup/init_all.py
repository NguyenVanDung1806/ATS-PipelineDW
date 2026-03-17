#!/usr/bin/env python3
"""
DE Template — One-command setup.
Run once after cloning: python3 scripts/setup/init_all.py
"""
import subprocess, sys, os, time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# ── Colors ───────────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"
BOLD = "\033[1m"; RESET = "\033[0m"
def ok(msg):   print(f"  {G}✓{RESET} {msg}")
def fail(msg): print(f"  {R}✗{RESET} {R}{msg}{RESET}")
def info(msg): print(f"  {B}·{RESET} {msg}")
def warn(msg): print(f"  {Y}⚠{RESET} {Y}{msg}{RESET}")
def header(msg): print(f"\n{BOLD}{B}▸ {msg}{RESET}")


# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd: list, cwd: Path = ROOT, timeout: int = 120) -> tuple[bool, str]:
    r = subprocess.run(cmd, capture_output=True, text=True,
                       cwd=str(cwd), timeout=timeout)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def check_env() -> bool:
    env_file = ROOT / ".env"
    if not env_file.exists():
        fail(".env not found")
        info("Run: cp .env.example .env && fill in your values")
        return False

    required = [
        "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
        "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
        "AIRFLOW_FERNET_KEY", "AIRFLOW_SECRET_KEY",
        "SLACK_WEBHOOK_URL",
    ]
    content = env_file.read_text()
    missing = [k for k in required if k not in content or f"{k}=CHANGE_ME" in content]
    if missing:
        fail(f"Missing or unfilled values in .env: {', '.join(missing)}")
        return False

    ok(".env configured")
    return True


def check_dependencies() -> bool:
    deps = {
        "docker": ["docker", "--version"],
        "docker-compose": ["docker-compose", "--version"],
        "python3": ["python3", "--version"],
        "git": ["git", "--version"],
    }
    all_ok = True
    for name, cmd in deps.items():
        ok_flag, out = run(cmd)
        if ok_flag:
            version = out.split("\n")[0][:40]
            ok(f"{name}: {version}")
        else:
            fail(f"{name}: not found — install before continuing")
            all_ok = False
    return all_ok


def start_services() -> bool:
    info("Starting Docker services (this may take 2-3 minutes first time)...")
    ok_flag, out = run(
        ["docker-compose", "-f", "infra/docker-compose.yml", "up", "-d"],
        timeout=300
    )
    if not ok_flag:
        fail(f"docker-compose failed:\n{out[-300:]}")
        return False
    ok("Docker services started")
    return True


def wait_for_postgres(max_wait: int = 60) -> bool:
    info("Waiting for PostgreSQL to be ready...")
    env = dict(os.environ)
    env_file = ROOT / ".env"
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    for i in range(max_wait):
        ok_flag, _ = run(
            ["docker-compose", "-f", "infra/docker-compose.yml",
             "exec", "-T", "postgres",
             "pg_isready", "-U", env.get("POSTGRES_USER", "de_user")],
            timeout=10
        )
        if ok_flag:
            ok("PostgreSQL ready")
            return True
        time.sleep(2)
        if i % 10 == 9:
            info(f"Still waiting... ({i+1}s)")

    fail("PostgreSQL did not become ready in time")
    return False


def init_minio() -> bool:
    try:
        sys.path.insert(0, str(ROOT))
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        from extractors.base.minio_client import get_minio_client

        FOLDERS = [
            "raw/facebook/ads/", "raw/google/ads/",
            "raw/tiktok/ads/",   "raw/zalo/ads/",
            "raw/crm/leads/",    "processed/",
        ]
        bucket = os.environ.get("MINIO_BUCKET", "datalake")
        client = get_minio_client()

        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)

        for folder in FOLDERS:
            client.put_object(Bucket=bucket, Key=folder + ".keep", Body=b"")

        ok(f"MinIO bucket '{bucket}' initialized with {len(FOLDERS)} folders")
        return True
    except Exception as e:
        warn(f"MinIO init skipped (start services first): {e}")
        return False


def init_dbt() -> bool:
    dbt_dir = ROOT / "dbt"
    ok_flag, out = run(["dbt", "deps", "--quiet"], cwd=dbt_dir, timeout=120)
    if not ok_flag:
        fail(f"dbt deps failed: {out[-200:]}")
        return False
    ok("dbt packages installed")

    ok_flag, out = run(["dbt", "debug", "--quiet"], cwd=dbt_dir, timeout=30)
    if ok_flag:
        ok("dbt connection verified")
    else:
        warn("dbt debug failed — check profiles.yml and .env")
    return True


def check_python_deps() -> bool:
    required = ["pydantic", "boto3", "tenacity", "black", "mypy", "pytest"]
    missing = []
    for pkg in required:
        ok_flag, _ = run(["python3", "-c", f"import {pkg.replace('-','_')}"])
        if not ok_flag:
            missing.append(pkg)

    if missing:
        warn(f"Missing Python packages: {', '.join(missing)}")
        info("Installing...")
        ok_flag, out = run(
            ["pip3", "install"] + missing + ["--quiet"],
            timeout=120
        )
        if ok_flag:
            ok("Python packages installed")
        else:
            fail(f"pip install failed: {out[-200:]}")
            return False
    else:
        ok("Python dependencies satisfied")
    return True


def print_next_steps():
    print(f"""
{BOLD}{B}══════════════════════════════════════════{RESET}
{BOLD}{G}  Setup complete! Next steps:{RESET}
{B}══════════════════════════════════════════{RESET}

  {G}1.{RESET} Open Claude Code with Opus for planning:
     {B}claude --model opus{RESET}

  {G}2.{RESET} First prompt:
     {B}"Read CLAUDE.md and MEMORY.md.
      I'm starting Phase 0.
      Use /run-phase 0 to create the execution plan."{RESET}

  {G}3.{RESET} Service URLs:
     · Airflow:  http://localhost:8080  (admin/admin)
     · MinIO:    http://localhost:9001
     · Metabase: http://localhost:3000

  {G}4.{RESET} Useful commands:
     · {B}make help{RESET}           — show all shortcuts
     · {B}/new-extractor fb{RESET}   — scaffold FB extractor
     · {B}/validate-pipeline{RESET}  — pre-merge check
     · {B}/run-phase 1{RESET}        — plan Phase 1

{B}══════════════════════════════════════════{RESET}
""")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}{B}DE Senior Template — Setup{RESET}\n{'═'*42}")

    steps = [
        ("Checking dependencies",     check_dependencies),
        ("Checking .env config",       check_env),
        ("Python packages",            check_python_deps),
        ("Starting Docker services",   start_services),
        ("Waiting for PostgreSQL",     wait_for_postgres),
        ("Initializing MinIO",         init_minio),
        ("Setting up dbt",             init_dbt),
    ]

    failed_steps = []
    for name, fn in steps:
        header(name)
        try:
            if not fn():
                failed_steps.append(name)
                if name in ("Checking .env config", "Checking dependencies"):
                    fail("Cannot continue without fixing above. Exiting.")
                    sys.exit(1)
        except Exception as e:
            fail(f"Unexpected error: {e}")
            failed_steps.append(name)

    print(f"\n{'═'*42}")
    if failed_steps:
        warn(f"Some steps had issues: {', '.join(failed_steps)}")
        warn("Fix the issues above and re-run: python3 scripts/setup/init_all.py")
    else:
        ok("All setup steps completed successfully")

    print_next_steps()


if __name__ == "__main__":
    main()
