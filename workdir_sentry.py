#!/usr/bin/env python3
"""workdir_sentry.py - Claude Code SessionStart hook: warn when a session starts
outside this machine's canonical project directory.

WHY: Claude Code keys project memory (auto-memory), session history, and the
project CLAUDE.md to the working directory the session starts in. Start in the
wrong folder (home dir, System32 via an elevated shell, a synced copy of another
machine's folder) and the session silently loads the WRONG memory - or none.
Measured on one long-running workstation: 4370 sessions had started in $HOME and
2420 in C:\\Windows\\System32, vs 1921 in the actual project folder - more than
half of all sessions ran without their project context and nobody noticed.

INSTALL:
  1. Save this file, e.g. to ~/.claude/hooks/workdir_sentry.py
  2. Create ~/.claude/workdir_homes.json (see workdir_homes.example.json):
     maps each machine name to its canonical project dir, plus optional
     always-ok prefixes (worktrees, scratchpads, your vault...).
  3. Register a SessionStart hook in ~/.claude/settings.json:
       "hooks": { "SessionStart": [ { "hooks": [ { "type": "command",
         "command": "python3 ~/.claude/hooks/workdir_sentry.py", "timeout": 10 } ] } ] }
     (Windows: "python %USERPROFILE%\\.claude\\hooks\\workdir_sentry.py")

BEHAVIOR: prints ONE warning line (which lands in the model's context) when the
cwd is foreign; stays silent when the cwd is the canonical dir, an allowed
prefix, or the machine is not listed. Fail-open: any error = silence, a session
start is never blocked. A PowerShell 5.1 pipe prepends a UTF-8 BOM to stdin -
that is why the json.loads input is BOM-stripped; keep that if you edit.

Companion tip: also fix the ENTRY, not just the alarm - point your terminal's
default start directory at the project (Windows Terminal:
profiles.defaults.startingDirectory in its settings.json).
"""
import json
import os
import platform
import sys


def machine_key() -> str:
    return (os.environ.get("COMPUTERNAME") or platform.node().split(".")[0] or "").upper()


def norm(p: str) -> str:
    p = os.path.normpath(os.path.expanduser(p)).rstrip("\\/")
    return p.lower() if os.name == "nt" else p


def check(cwd: str, cfg: dict, key: str) -> str:
    """Return a warning line, or '' when everything is fine."""
    nodes = {k.upper(): v for k, v in cfg.get("nodes", {}).items()}
    home = nodes.get(key)
    if not home:
        return ""  # machine not registered -> stay silent
    ncwd, nhome = norm(cwd), norm(home)
    if ncwd == nhome or ncwd.startswith(nhome + os.sep):
        return ""
    for pref in cfg.get("always_ok_prefixes", []):
        np = norm(pref)
        if ncwd == np or ncwd.startswith(np + os.sep):
            return ""
    return (f"[workdir-sentry] WARNING: this session started in '{cwd}', but this "
            f"machine's canonical Claude project dir is '{home}'. Project memory, "
            f"session history and CLAUDE.md are keyed to the working directory, so "
            f"you are running with the WRONG (or no) project context. Restart the "
            f"session from '{home}' for real work here.")


def main() -> None:
    try:
        try:
            # lstrip BOM: a PowerShell 5.1 pipe prepends U+FEFF and json.loads rejects it
            payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
        except Exception:
            payload = {}
        cwd = payload.get("cwd") or os.getcwd()
        cfg_path = os.path.join(os.path.expanduser("~"), ".claude", "workdir_homes.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        msg = check(cwd, cfg, machine_key())
        if msg:
            print(msg)
    except BaseException:
        pass  # a sentry must never break session start
    sys.exit(0)


if __name__ == "__main__":
    main()
