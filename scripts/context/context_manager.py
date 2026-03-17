#!/usr/bin/env python3
"""
DE Context Manager
Tự động extract context từ git history + file changes
và update MEMORY.md — không cần user update tay.

Gọi bởi:
  - Stop hook (cuối session)
  - Pre-session check (đầu session)
  - Compact hook (khi context đầy)
"""
import subprocess, json, os, sys, re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent


# ── Git helpers ───────────────────────────────────────────────────────────────

def git(cmd: list) -> str:
    r = subprocess.run(["git"] + cmd, capture_output=True,
                       text=True, cwd=ROOT)
    return r.stdout.strip()


def get_changed_files() -> list[str]:
    """Files changed since last commit."""
    staged   = git(["diff", "--cached", "--name-only"])
    unstaged = git(["diff", "--name-only"])
    untracked = git(["ls-files", "--others", "--exclude-standard"])
    all_files = set(
        (staged + "\n" + unstaged + "\n" + untracked).strip().split("\n")
    )
    return [f for f in all_files if f and not f.startswith(".")]


def get_last_commit_info() -> dict:
    """Get info about last commit."""
    msg  = git(["log", "-1", "--pretty=%s"])
    date = git(["log", "-1", "--pretty=%ci"])
    files = git(["diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD"])
    return {
        "message": msg,
        "date": date[:16] if date else "",
        "files": [f for f in files.split("\n") if f],
    }


def get_current_branch() -> str:
    return git(["branch", "--show-current"]) or "main"


# ── File analysis ─────────────────────────────────────────────────────────────

def analyze_project_state() -> dict:
    """Analyze what's done and what's in progress by scanning files."""
    state = {
        "extractors": {},
        "dbt_models": {"staging": [], "marts": [], "dimensions": []},
        "dags": [],
        "tests": {"pass": 0, "total": 0},
        "phase": 0,
    }

    # Check extractors
    extractors_dir = ROOT / "extractors"
    for platform_dir in extractors_dir.iterdir():
        if platform_dir.is_dir() and platform_dir.name != "base":
            platform = platform_dir.name
            has_extract = (platform_dir / "extract.py").exists()
            has_schema  = (platform_dir / "schema.py").exists()
            has_tests   = (platform_dir / "test_extract.py").exists()

            if has_extract and has_schema and has_tests:
                status = "DONE"
            elif has_extract or has_schema:
                status = "IN_PROGRESS"
            else:
                status = "TODO"

            state["extractors"][platform] = {
                "status": status,
                "has_extract": has_extract,
                "has_schema": has_schema,
                "has_tests": has_tests,
            }

    # Check dbt models
    models_dir = ROOT / "dbt" / "models"
    for layer in ["staging", "marts", "dimensions"]:
        layer_dir = models_dir / layer
        if layer_dir.exists():
            state["dbt_models"][layer] = [
                f.stem for f in layer_dir.glob("*.sql")
            ]

    # Check dags
    dags_dir = ROOT / "dags"
    if dags_dir.exists():
        state["dags"] = [
            f.stem for f in dags_dir.glob("*.py")
            if f.stem != "template_pipeline"
        ]

    # Infer phase
    n_extractors_done = sum(
        1 for v in state["extractors"].values()
        if v["status"] == "DONE"
    )
    has_fct = bool(state["dbt_models"]["marts"])
    has_dags = bool(state["dags"])

    if n_extractors_done == 0 and not has_fct:
        state["phase"] = 0
    elif n_extractors_done >= 1 and has_fct and not has_dags:
        state["phase"] = 1
    elif n_extractors_done >= 1 and has_dags:
        state["phase"] = 2
    else:
        state["phase"] = 0

    return state


def get_current_working_file() -> str:
    """Best guess at what file user is currently working on."""
    changed = get_changed_files()
    if not changed:
        return "—"

    # Prioritize Python and SQL files
    priority = [f for f in changed
                if f.endswith((".py", ".sql", ".yml", ".yaml", ".md"))
                and not f.startswith(".")]

    if priority:
        # Most recently modified
        try:
            priority.sort(
                key=lambda f: (ROOT / f).stat().st_mtime
                if (ROOT / f).exists() else 0,
                reverse=True
            )
            return priority[0]
        except Exception:
            return priority[0]

    return changed[0] if changed else "—"


# ── MEMORY.md parser + writer ─────────────────────────────────────────────────

def read_memory() -> dict:
    """Parse current MEMORY.md into structured dict."""
    memory_file = ROOT / "MEMORY.md"
    if not memory_file.exists():
        return {}

    content = memory_file.read_text(encoding="utf-8")
    data = {"raw": content}

    # Extract QUICK CONTEXT block
    qc_match = re.search(
        r"## QUICK CONTEXT.*?```\n(.*?)```",
        content, re.DOTALL
    )
    if qc_match:
        qc_text = qc_match.group(1)
        qc = {}
        for line in qc_text.strip().split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                qc[k.strip()] = v.strip()
        data["quick_context"] = qc

    return data


def update_memory(
    current_file: str = None,
    last_action: str = None,
    next_action: str = None,
    new_gotcha: str = None,
    session_note: str = None,
    auto_phase: int = None,
) -> None:
    """
    Update MEMORY.md QUICK CONTEXT section automatically.
    Only updates fields that are provided — doesn't overwrite everything.
    """
    memory_file = ROOT / "MEMORY.md"
    if not memory_file.exists():
        print("MEMORY.md not found — skipping update")
        return

    content = memory_file.read_text(encoding="utf-8")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    # Parse existing QUICK CONTEXT
    qc_match = re.search(
        r"(## QUICK CONTEXT.*?```\n)(.*?)(```)",
        content, re.DOTALL
    )

    if not qc_match:
        print("QUICK CONTEXT block not found in MEMORY.md")
        return

    # Parse existing values
    qc_text = qc_match.group(2)
    existing = {}
    for line in qc_text.strip().split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            existing[k.strip()] = v.strip()

    # Update only provided fields
    if current_file:
        existing["Current file"] = current_file
    if last_action:
        existing["Last action"] = last_action
    if next_action:
        existing["Next action"] = next_action
    if auto_phase is not None:
        phase_names = {
            0: "0 — Infrastructure Setup",
            1: "1 — First Pipeline",
            2: "2 — Multi-Platform",
            3: "3 — Observability",
            4: "4 — Analytics",
        }
        existing["Phase"] = phase_names.get(auto_phase, str(auto_phase))
    existing["Last session"] = today

    # Rebuild QUICK CONTEXT block
    lines = []
    for k in ["Phase", "Current file", "Last action", "Next action",
              "Blocked on", "Last session"]:
        v = existing.get(k, "—")
        lines.append(f"{k}:        {v}")

    new_qc = "\n".join(lines)
    new_content = content[:qc_match.start(2)] + new_qc + "\n" + content[qc_match.end(2):]

    # Add gotcha if provided
    if new_gotcha:
        gotcha_entry = f"\n{today} {new_gotcha}"
        new_content = new_content.replace(
            "```\n[DATE] [Component]: [Issue] → [Fix]",
            f"```\n[DATE] [Component]: [Issue] → [Fix]\n{today} {new_gotcha}"
        )

    # Add session note
    if session_note:
        session_entry = f"\n### {today} — Auto-logged\n- {session_note}\n"
        if "## Session Notes" in new_content:
            new_content = new_content.replace(
                "## Session Notes\n",
                f"## Session Notes\n{session_entry}"
            )

    memory_file.write_text(new_content, encoding="utf-8")
    print(f"[context] MEMORY.md updated at {now}")


# ── Auto-extract from session ─────────────────────────────────────────────────

def auto_extract_session_context() -> dict:
    """
    Auto-detect what happened this session from:
    - Git changes (what files were modified)
    - File timestamps (what was worked on)
    - Project state analysis
    """
    changed = get_changed_files()
    state   = analyze_project_state()
    current = get_current_working_file()
    branch  = get_current_branch()
    commit  = get_last_commit_info()

    # Infer last action from changed files
    last_action = "—"
    if changed:
        py_files  = [f for f in changed if f.endswith(".py")]
        sql_files = [f for f in changed if f.endswith(".sql")]
        yml_files = [f for f in changed if f.endswith((".yml", ".yaml"))]

        if py_files:
            names = ", ".join(Path(f).name for f in py_files[:2])
            last_action = f"Modified {names}"
        elif sql_files:
            names = ", ".join(Path(f).stem for f in sql_files[:2])
            last_action = f"Modified dbt models: {names}"
        elif yml_files:
            last_action = f"Modified config: {', '.join(Path(f).name for f in yml_files[:2])}"

    # Infer next action
    next_action = "—"
    # Check which extractors are incomplete
    for platform, info in state["extractors"].items():
        if info["status"] == "IN_PROGRESS":
            if not info["has_extract"]:
                next_action = f"Implement extractors/{platform}/extract.py"
            elif not info["has_tests"]:
                next_action = f"Write tests for extractors/{platform}/"
            break

    if next_action == "—" and not state["dbt_models"]["marts"]:
        next_action = "Create dbt/models/marts/fct_ad_spend.sql"

    if next_action == "—" and not state["dags"]:
        next_action = "Create first Airflow DAG in dags/"

    return {
        "current_file":  current,
        "last_action":   last_action,
        "next_action":   next_action,
        "phase":         state["phase"],
        "changed_files": changed,
        "branch":        branch,
        "state":         state,
    }


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_session_end():
    """Called by Stop hook — auto-update MEMORY.md."""
    print("\n[context] Auto-extracting session context...")
    ctx = auto_extract_session_context()

    update_memory(
        current_file=ctx["current_file"],
        last_action=ctx["last_action"],
        next_action=ctx["next_action"],
        auto_phase=ctx["phase"],
        session_note=f"Branch: {ctx['branch']} | Changed: {len(ctx['changed_files'])} files",
    )

    # Print summary for user
    print(f"\n[context] Session summary:")
    print(f"  Phase:        {ctx['phase']}")
    print(f"  Current file: {ctx['current_file']}")
    print(f"  Last action:  {ctx['last_action']}")
    print(f"  Next action:  {ctx['next_action']}")
    print(f"  Changed:      {len(ctx['changed_files'])} files")

    if ctx["changed_files"]:
        print(f"  Files:")
        for f in ctx["changed_files"][:5]:
            print(f"    · {f}")
        if len(ctx["changed_files"]) > 5:
            print(f"    ... and {len(ctx['changed_files'])-5} more")


def cmd_session_start():
    """Called at start of session — show current context."""
    ctx   = auto_extract_session_context()
    mem   = read_memory()
    qc    = mem.get("quick_context", {})
    state = ctx["state"]

    print("\n" + "═"*48)
    print("  DE Project Context")
    print("═"*48)
    print(f"  Phase:        {qc.get('Phase', ctx['phase'])}")
    print(f"  Current file: {qc.get('Current file', ctx['current_file'])}")
    print(f"  Last action:  {qc.get('Last action', '—')}")
    print(f"  Next action:  {qc.get('Next action', ctx['next_action'])}")
    print(f"  Last session: {qc.get('Last session', '—')}")
    print(f"  Branch:       {ctx['branch']}")
    print("")

    # Extractor status
    print("  Extractors:")
    for platform, info in state["extractors"].items():
        icon = "✓" if info["status"] == "DONE" else ("~" if info["status"] == "IN_PROGRESS" else "○")
        print(f"    {icon} {platform}: {info['status']}")

    # dbt status
    staging = state["dbt_models"]["staging"]
    marts   = state["dbt_models"]["marts"]
    print(f"\n  dbt models:")
    print(f"    staging: {len(staging)} ({', '.join(staging) or 'none'})")
    print(f"    marts:   {len(marts)} ({', '.join(marts) or 'none'})")
    print("═"*48 + "\n")


def cmd_update(args: list):
    """Manual update with specific fields."""
    kwargs = {}
    for arg in args:
        if arg.startswith("--file="):
            kwargs["current_file"] = arg[7:]
        elif arg.startswith("--action="):
            kwargs["last_action"] = arg[9:]
        elif arg.startswith("--next="):
            kwargs["next_action"] = arg[7:]
        elif arg.startswith("--gotcha="):
            kwargs["new_gotcha"] = arg[9:]
        elif arg.startswith("--note="):
            kwargs["session_note"] = arg[7:]

    if kwargs:
        update_memory(**kwargs)
    else:
        print("Usage: python3 context_manager.py update --file=X --action=Y --next=Z")


def cmd_status():
    """Quick status check."""
    state = analyze_project_state()
    ctx   = auto_extract_session_context()

    print(f"\nPhase {state['phase']} | Branch: {ctx['branch']}")
    print(f"Changed files: {len(ctx['changed_files'])}")
    for platform, info in state["extractors"].items():
        print(f"  {platform}: {info['status']}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "session-end":
        cmd_session_end()
    elif cmd == "session-start":
        cmd_session_start()
    elif cmd == "update":
        cmd_update(sys.argv[2:])
    elif cmd == "status":
        cmd_status()
    else:
        print("Commands:")
        print("  session-end    → auto-update MEMORY.md (called by Stop hook)")
        print("  session-start  → show current context (call at start)")
        print("  update         → manual update specific fields")
        print("  status         → quick project status")
