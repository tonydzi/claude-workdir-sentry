#!/usr/bin/env python3
"""workdir_sentry.py — Claude Code SessionStart hook: one warning line when a
session starts outside this machine's canonical project directory.

WHY THIS EXISTS
    Claude Code keys project memory, session history and CLAUDE.md to the
    directory a session STARTS in. Start in the wrong folder (your home dir,
    System32 via an elevated shell, a synced copy of another machine's
    project) and the session silently loads the wrong — usually empty —
    context. Nothing errors. Nothing warns. Claude just gets amnesia.

    Measured on one long-running workstation: 4370 sessions had started in
    $HOME and 2420 in System32, vs 1921 in the actual project folder. More
    than half of all sessions ran context-less, unnoticed, for months.

WHAT IT DOES
    At session start it compares the session's cwd with the canonical
    project dir you declared for this machine in ~/.claude/workdir_homes.json.
    Mismatch -> it prints ONE line, which Claude Code feeds into the model's
    context, so the model itself knows it's homeless and says so on turn one.
    Match / allowed prefix / unlisted machine -> silence (a healthy watchdog
    is a quiet watchdog).

SAFETY CONTRACT (read this before adding to your hook chain)
    * fail-open: ANY error -> print nothing, exit 0. A sentry must never
      block or slow a session start.
    * zero dependencies: stdlib only, one file.
    * BOM-hardened: a PowerShell 5.1 pipe prepends U+FEFF to stdin, which
      makes json.loads throw. We strip it. (This exact byte silently broke
      two of our own tools before we learned. Keep the strip if you edit.)

USAGE
    as a hook   : register in settings.json (see README.md)
    --check P   : dry-run one path, see what the hook would say
                  (no config yet -> a worded hint, never a traceback)
    --selftest  : run the built-in cases, print PASS/FAIL (exit 0/1)

CONFIG (~/.claude/workdir_homes.json)
    {
      "nodes":              { "<MACHINE-NAME>": "<canonical project dir>" },
      "always_ok_prefixes": [ "<dirs where odd cwds are intentional>" ]
    }
    Machine names are matched against COMPUTERNAME / hostname, upper-cased.
    always_ok_prefixes = agent worktrees, scratch dirs, a notes vault —
    places where a non-canonical cwd is on purpose and must not alarm.
"""
import json
import os
import platform
import sys


def machine_key() -> str:
    """This machine's name, upper-cased: COMPUTERNAME on Windows, hostname elsewhere."""
    return (os.environ.get("COMPUTERNAME") or platform.node().split(".")[0] or "").upper()


def norm(p: str) -> str:
    """Normalize a path for comparison: expanduser, collapse separators,
    drop trailing slashes, case-fold on Windows (its filesystems are
    case-insensitive; comparing raw strings would miss D:\\Proj vs d:\\proj)."""
    p = os.path.normpath(os.path.expanduser(p)).rstrip("\\/")
    return p.lower() if os.name == "nt" else p


def check(cwd: str, cfg: dict, key: str) -> str:
    """Core rule. Returns the warning text, or '' when everything is fine.

    Pure function on purpose: no I/O, no env — so it's trivially testable
    (see selftest below) and you can lift it into your own tooling.
    """
    nodes = {k.upper(): v for k, v in cfg.get("nodes", {}).items()}
    home = nodes.get(key)
    if not home:
        return ""  # machine not registered -> not our business, stay silent
    ncwd, nhome = norm(cwd), norm(home)
    if ncwd == nhome or ncwd.startswith(nhome + os.sep):
        return ""  # inside the canonical dir -> healthy, silent
    for pref in cfg.get("always_ok_prefixes", []):
        np = norm(pref)
        if ncwd == np or ncwd.startswith(np + os.sep):
            return ""  # intentional off-project place (worktree, scratch) -> silent
    return (f"[workdir-sentry] WARNING: this session started in '{cwd}', but this "
            f"machine's canonical Claude project dir is '{home}'. Project memory, "
            f"session history and CLAUDE.md are keyed to the working directory, so "
            f"you are running with the WRONG (or no) project context. Restart the "
            f"session from '{home}' for real work here.")


def _load_cfg() -> dict:
    cfg_path = os.path.join(os.path.expanduser("~"), ".claude", "workdir_homes.json")
    # utf-8-sig: tolerate a BOM here too (editors on Windows love adding one)
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def selftest() -> int:
    """Built-in cases so you can trust the sentry before wiring it in."""
    cfg = {"nodes": {"BOX": "D:/proj"}, "always_ok_prefixes": ["D:/ok"]}
    cases = [
        ("canonical dir is silent",        check("D:/proj", cfg, "BOX") == ""),
        ("subdir of canonical is silent",  check("D:/proj/sub/deep", cfg, "BOX") == ""),
        ("allowed prefix is silent",       check("D:/ok/x", cfg, "BOX") == ""),
        ("foreign dir warns",              "WARNING" in check("C:/Users/me", cfg, "BOX")),
        # the warning must NAME the canonical dir — an alarm that doesn't say
        # where to go just adds anxiety, not a fix
        ("warning names the home dir",     "D:/proj" in check("C:/Users/me", cfg, "BOX")),
        ("unlisted machine is silent",     check("C:/Users/me", cfg, "GHOST") == ""),
        ("empty config never crashes",     check("C:/anything", {}, "BOX") == ""),
    ]
    failed = [name for name, ok in cases if not ok]
    print("FAIL: " + ", ".join(failed) if failed else "PASS (%d cases)" % len(cases))
    return 1 if failed else 0


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--check" in sys.argv:
        # dry-run one path with the real config: what would the hook say?
        # Unlike hook mode this talks to a HUMAN, so errors are worded, not silent.
        idx = sys.argv.index("--check") + 1
        if idx >= len(sys.argv):
            sys.exit("usage: workdir_sentry.py --check <path>")
        path = sys.argv[idx]
        try:
            cfg = _load_cfg()
        except FileNotFoundError:
            sys.exit("no config yet — create ~/.claude/workdir_homes.json first "
                     "(copy workdir_homes.example.json from this gist and edit it)")
        except Exception as e:
            sys.exit("config exists but can't be read (%s: %s) — "
                     "fix ~/.claude/workdir_homes.json" % (type(e).__name__, e))
        msg = check(path, cfg, machine_key())
        print(msg or "(silent — '%s' is fine on %s)" % (path, machine_key()))
        sys.exit(0)
    # ---- hook mode: everything below is fail-open by contract ----
    try:
        try:
            # lstrip BOM: PowerShell 5.1 pipes prepend U+FEFF, json.loads rejects it
            payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
        except Exception:
            payload = {}
        cwd = payload.get("cwd") or os.getcwd()
        msg = check(cwd, _load_cfg(), machine_key())
        if msg:
            print(msg)
    except BaseException:
        pass  # a sentry must never break a session start
    sys.exit(0)


if __name__ == "__main__":
    main()
