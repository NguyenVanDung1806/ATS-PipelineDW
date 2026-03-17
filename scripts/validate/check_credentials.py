#!/usr/bin/env python3
"""Pre-commit credential scanner. Blocks commit if secrets found."""
import subprocess, sys, re
from pathlib import Path

PATTERNS = [
    (r'(?i)(api_key|apikey)\s*=\s*["\'][A-Za-z0-9+/]{10,}', "API key"),
    (r'(?i)password\s*=\s*["\'][^"\']{4,}', "Password"),
    (r'(?i)(secret|token)\s*=\s*["\'][A-Za-z0-9+/]{8,}', "Secret/Token"),
    (r'(?i)access_key\s*=\s*["\'][A-Za-z0-9+/]{10,}', "Access key"),
    (r'AKIA[0-9A-Z]{16}', "AWS Key ID"),
]
SAFE = ["os.environ", "os.getenv", "CHANGE_ME", "YOUR_", ".env.example"]
SKIP = {".git", "__pycache__", "venv", ".env.example", "check_credentials.py"}

def get_staged() -> list[Path]:
    r = subprocess.run(["git", "diff", "--cached", "--name-only"],
                       capture_output=True, text=True)
    return [Path(f) for f in r.stdout.strip().split("\n")
            if f and f.endswith((".py", ".sql", ".yml", ".yaml", ".json"))
            and not any(s in f for s in SKIP)]

def scan() -> list[str]:
    issues = []
    for fp in get_staged():
        try:
            for i, line in enumerate(fp.read_text(errors="ignore").splitlines(), 1):
                if any(s in line for s in SAFE):
                    continue
                for pat, label in PATTERNS:
                    if re.search(pat, line):
                        issues.append(f"  {fp}:{i} [{label}] {line.strip()[:80]}")
                        break
        except (FileNotFoundError, PermissionError):
            pass
    return issues

if __name__ == "__main__":
    issues = scan()
    if issues:
        print("CREDENTIAL FOUND — commit blocked:\n")
        print("\n".join(issues))
        print("\nFix: use os.environ['KEY'] instead of hardcoded values.")
        sys.exit(1)
    print("Security scan: clean")
    sys.exit(0)
