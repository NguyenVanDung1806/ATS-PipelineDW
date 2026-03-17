#!/usr/bin/env python3
"""Full pipeline health check. Run before every merge."""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

def run(name: str, cmd: list, cwd: Path | None = None) -> bool:
    print(f"\n  ▸ {name}")
    r = subprocess.run(cmd, capture_output=True, text=True,
                       cwd=str(cwd or ROOT), timeout=120)
    if r.returncode == 0:
        print(f"    ✓ passed")
        return True
    print(f"    ✗ FAILED\n    {r.stderr[-300:].strip()}")
    return False

CHECKS = [
    ("Security scan",    ["python3", "scripts/validate/check_credentials.py"], None),
    ("Docker services",  ["docker-compose", "-f", "infra/docker-compose.yml", "ps"], None),
    ("dbt compile",      ["dbt", "compile", "--quiet"], ROOT / "dbt"),
    ("dbt run staging",  ["dbt", "run", "--select", "staging", "--quiet"], ROOT / "dbt"),
    ("dbt test staging", ["dbt", "test", "--select", "staging", "--quiet"], ROOT / "dbt"),
    ("dbt run marts",    ["dbt", "run", "--select", "marts", "--quiet"], ROOT / "dbt"),
    ("dbt test marts",   ["dbt", "test", "--select", "marts", "--quiet"], ROOT / "dbt"),
]

if __name__ == "__main__":
    print("\n══════════════════════════════════")
    print("  Pipeline Validation")
    print("══════════════════════════════════")
    for name, cmd, cwd in CHECKS:
        if not run(name, cmd, cwd):
            print(f"\n  ✗ FAILED at: {name}")
            sys.exit(1)
    print("\n  ✓ All checks passed — ready to merge")
    sys.exit(0)
