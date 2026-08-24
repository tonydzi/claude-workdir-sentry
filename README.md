# Claude Code workdir sentry

**One tiny SessionStart hook that tells Claude (and you) when a session started in the wrong folder — before you lose a day of context.**

## The problem this fixes

Claude Code keys three things to the directory a session **starts in**:

1. **Project memory** (auto-memory) — lives in `~/.claude/projects/<encoded-cwd>/memory/`
2. **Session history** — same per-directory bucket
3. **Your project `CLAUDE.md`** — loaded from the cwd upward

Start a session in the wrong folder and none of that loads. No error, no warning — Claude just quietly behaves like it has amnesia. You've probably seen the symptoms without knowing the cause:

- *"Claude ignores my CLAUDE.md rules"* — sometimes the file was never in context at all
- *"My chat history / memory disappeared"* — it's sitting in a different project bucket
- *"Claude feels dumber on this machine"* — it's running without your project context

### How common is this really?

We audited one long-running workstation (a machine in a 6-node Claude Code fleet):

| Where sessions actually started | Count |
|---|---|
| `C:\Users\<user>` (terminal's default tab dir) | 4 370 |
| `C:\Windows\System32` (elevated shells, scheduled tasks) | 2 420 |
| The actual project folder | 1 921 |

**More than half of all sessions ran without their project context** — and nobody noticed for months, because nothing ever complains.

### Quick self-diagnosis (30 seconds)

Look at `~/.claude/projects/` — every directory name encodes a start-cwd. If you see a fat `C--Users-<you>` or `C--Windows-System32` next to your real project dir, you have this problem.

## The fix (two halves)

**Half 1 — the alarm.** `workdir_sentry.py` runs at every session start (SessionStart hook). It compares the session's cwd against your machine's canonical project directory and, when they differ, prints one warning line that lands directly in the model's context:

> `[workdir-sentry] WARNING: this session started in 'C:\Users\me', but this machine's canonical Claude project dir is 'D:\projects\main'. Project memory, session history and CLAUDE.md are keyed to the working directory... Restart from 'D:\projects\main' for real work here.`

So the *model itself* knows it's homeless and tells you on turn one — instead of you discovering it a week later.

Design choices, so you can trust it in your hook chain:

- **Silent when healthy.** Right folder, allowed folder, or unlisted machine → prints nothing.
- **Fail-open.** Any error (missing config, broken JSON, weird stdin) → silence and exit 0. A watchdog must never block a session start.
- **Zero dependencies.** Stdlib Python 3, one file, ~40 effective lines.
- **BOM-hardened.** PowerShell 5.1 pipes prepend a UTF-8 BOM to stdin; the hook strips it before parsing (this exact BOM broke two of our own tools before we learned).

**Half 2 — the entry.** The alarm tells you you're lost; fixing the *door* stops you getting lost. Point your terminal's default start directory at the project:

- **Windows Terminal:** `settings.json` → `"profiles": { "defaults": { "startingDirectory": "D:\\projects\\main" } }`
- **macOS Terminal:** Settings → Profiles → your profile → "Working directory: Other"
- **iTerm2:** Profiles → General → Working Directory → "Directory"

In our audit, the 4 370 home-dir sessions existed purely because that's where a fresh terminal tab opens.

## Install (2 minutes)

1. Save `workdir_sentry.py` to `~/.claude/hooks/workdir_sentry.py`.
2. Copy `workdir_homes.example.json` to `~/.claude/workdir_homes.json` and edit it: your machine name(s) → canonical project dir, plus `always_ok_prefixes` for places where non-canonical cwds are *intentional* (agent worktrees, scratch dirs, a notes vault).
3. Register the hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
          "command": "python3 \"$HOME/.claude/hooks/workdir_sentry.py\"",
          "timeout": 10 } ] }
    ]
  }
}
```

On Windows use `python "%USERPROFILE%\\.claude\\hooks\\workdir_sentry.py"`.

4. Sanity-check without restarting anything:

```bash
python3 ~/.claude/hooks/workdir_sentry.py --selftest
```

`--selftest` runs the built-in cases (wrong dir warns, right dir is silent, allowed prefix is silent, unlisted machine is silent, broken config never crashes) and prints `PASS` or what failed. You can also try a single path by hand: `--check /some/path`.

## FAQ

**Why a per-machine config file instead of hardcoding a path?**
The config syncs fine across machines (each machine only reads its own entry), while the *hook registration* lives in per-machine `settings.json`. If you run one machine, one entry is all you need.

**Why warn instead of auto-cd or blocking?**
A session's cwd can't be changed retroactively by a hook, and blocking would break intentional off-project sessions (quick questions, scratch work). One honest line in the model's context is the right amount of force — the model relays it and you decide.

**Does this work in the Desktop app?**
Yes — SessionStart hooks fire there too, so a session opened in the wrong folder via the folder picker gets the same first-turn warning.

**What about agent worktrees / scratchpads?**
That's what `always_ok_prefixes` is for — subagents legitimately start in isolated worktrees; you don't want a false alarm per agent.

---

Built after the fleet audit above, by [Mycroft](https://github.com/tonydzi) (synthetic cofounder) & Tony, Palo Alto AI Research Lab. MIT — take it, ship it, adapt it.
