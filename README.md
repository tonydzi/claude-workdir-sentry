# claude-workdir-sentry

A tiny Claude Code add-on that warns you when you start a session in the wrong folder, so Claude does not quietly lose your project memory and CLAUDE.md.

**Who it's for:** Claude Code users who open sessions from a terminal, a scheduled task or the desktop app and sometimes land in the home folder.
**What you get:** one warning line on the first turn of a wrong-folder session, and total silence when you are in the right folder.

## Quick start
1. Save `workdir_sentry.py` to `~/.claude/hooks/`.
2. Copy `workdir_homes.example.json` to `~/.claude/workdir_homes.json` and put your machine name and your main project folder in it.
3. Add the hook to `~/.claude/settings.json` (exact snippet is in "For AI agents" below).
4. Run `python workdir_sentry.py --selftest`.

**Done when:** the self-test prints `PASS`, and a session started in your home folder shows a `[workdir-sentry] WARNING` line.

> Want an AI agent to do it for you? Paste this to Claude Code / Codex / Cursor:
> "Read the 'For AI agents' section of https://github.com/tonydzi/claude-workdir-sentry and set it up for me."

## For AI agents

### Preconditions
- Python 3 (stdlib only). On Windows the command is `python`; on macOS and Linux use `python3`.
- Claude Code with hooks enabled (`~/.claude/settings.json`).
- Ask the human: their main project folder (absolute path), and which folders are on purpose outside it (scratch dirs, worktrees, a notes vault).
- Get the machine name with `python -c "import os,platform;print((os.environ.get('COMPUTERNAME') or platform.node().split('.')[0]).upper())"`.

### Install
```bash
git clone https://github.com/tonydzi/claude-workdir-sentry
mkdir -p ~/.claude/hooks
cp claude-workdir-sentry/workdir_sentry.py ~/.claude/hooks/workdir_sentry.py
cp claude-workdir-sentry/workdir_homes.example.json ~/.claude/workdir_homes.json
```
Then merge this into `~/.claude/settings.json` (keep existing hooks; add, do not replace):
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
On Windows use `python "%USERPROFILE%\\.claude\\hooks\\workdir_sentry.py"` as the command.

### Configure
Edit `~/.claude/workdir_homes.json`:
- `nodes`: replace the example entries with `"<MACHINE-NAME-UPPERCASE>": "<project dir>"`. Both values come from the human and the machine-name command above. A machine not listed means the hook stays silent.
- `always_ok_prefixes`: folders where starting a session is fine (from the human).

### Verify
```bash
python3 ~/.claude/hooks/workdir_sentry.py --selftest
```
Expected: prints `PASS (12 cases)` and exits 0 (case count may differ in newer versions; `PASS` is what matters).
Optional dry run: `python3 ~/.claude/hooks/workdir_sentry.py --check <some-path>` shows what the hook would say for that path.

### Uninstall / rollback
Remove the `SessionStart` entry from `~/.claude/settings.json`, then `rm ~/.claude/hooks/workdir_sentry.py ~/.claude/workdir_homes.json`. Keep a copy of `settings.json` before editing.

### Rules for the agent
- Back up `~/.claude/settings.json` before editing and preserve all other hooks.
- Never invent the project folder or machine name; ask the human.
- The hook only warns. Do not change the human's terminal or working directory settings without asking.

## Details

**One tiny SessionStart hook that tells Claude (and you) when a session started in the wrong folder — before you lose a day of context.**

## The problem this fixes

Claude Code keys three things to the directory a session **starts in**:

1. **Project memory** (auto-memory) — lives in `~/.claude/projects/<encoded-cwd>/memory/`
2. **Session history** — same per-directory bucket
3. **Your project `CLAUDE.md`** — loaded from the cwd upward

Start a session in the wrong folder and none of that loads, which is the one thing [workdir_sentry.py](workdir_sentry.py) watches for. No error, no warning — Claude just quietly behaves like it has amnesia. You've probably seen the symptoms without knowing the cause:

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

**More than half of all sessions ran without their project context** — and through 2026 nobody noticed for months, because nothing ever complains.

> **Read the denominator before you quote this number.** `~/.claude/projects/<slug>/` also
> contains `subagents/*.jsonl` — subagent transcripts, marked `"isSidechain": true`. They never
> open a memory store and never fire `SessionStart`, so counting `**/*.jsonl` measures the wrong
> population (thanks to [@JhouCode](https://github.com/anthropics/claude-code/issues/82056) for
> catching this). Count `<slug>/*.jsonl` only.
>
> The bias does **not** have a fixed direction. Re-measuring one node of our fleet with the filter
> named: 1797 real sessions vs 613 subagent transcripts; **63.1%** of real sessions keyed to an
> empty store, but only **47.3%** if you count recursively — because 606 of those 613 subagent
> transcripts sit under the one slug that *does* have a store. A subagent inherits its parent's
> project, and parents are the healthy projects, so the passenger is systematically healthy and
> drags the rate *down*. Whether it inflates or deflates depends on which sessions spawn subagents
> on your box. Name your filter; don't assume its sign.

### Quick self-diagnosis (30 seconds)

Look at `~/.claude/projects/` — every directory name encodes a start-cwd, and [workdir_sentry.py](workdir_sentry.py) reads the same encoding. If you see a fat `C--Users-<you>` or `C--Windows-System32` next to your real project dir, you have this problem.

## The fix (two halves)

**Half 1 — the alarm.** [workdir_sentry.py](workdir_sentry.py) runs at every session start (SessionStart hook). It compares the session's cwd against your machine's canonical project directory and, when they differ, prints one warning line that lands directly in the model's context:

> `[workdir-sentry] WARNING: this session started in 'C:\Users\me', but this machine's canonical Claude project dir is 'D:\projects\main'. Project memory, session history and CLAUDE.md are keyed to the working directory... Restart from 'D:\projects\main' for real work here.`

So the *model itself* knows it's homeless and tells you on turn one — instead of you discovering it a week later, which is the entire return on [workdir_sentry.py](workdir_sentry.py).

Design choices, so you can trust it in your hook chain:

- **Silent when healthy.** Exact canonical folder, allowed prefix from [workdir_homes.example.json](workdir_homes.example.json), or unlisted machine → prints nothing.
  A *subdirectory* of the canonical dir gets a softer `NOTE`, not silence: CLAUDE.md still loads
  (it is searched cwd-upward) but memory and history are keyed to the **exact** start dir, so a
  subdir has its own empty bucket. Earlier versions of [workdir_sentry.py](workdir_sentry.py) stayed silent there — and the selftest asserted that silence, which is how the bug survived. Both this and the `"/"`-as-canonical-dir disarm were
  reported by [@JhouCode](https://github.com/anthropics/claude-code/issues/82056).
- **Fail-open.** Any error (missing config, broken JSON, weird stdin) makes the hook go silent and exit 0. A watchdog must never block a session start.
- **Zero dependencies.** Stdlib Python 3, one file — [workdir_sentry.py](workdir_sentry.py), about 40 effective lines.
- **BOM-hardened.** PowerShell 5.1 pipes prepend a UTF-8 BOM to stdin; [workdir_sentry.py](workdir_sentry.py) strips it before parsing (this exact BOM broke two of our own tools before we learned).

**Half 2 — the entry.** The alarm tells you you're lost; fixing the *door* stops you getting lost. Point your terminal's default start directory at the project:

- **Windows Terminal:** `settings.json` → `"profiles": { "defaults": { "startingDirectory": "D:\\projects\\main" } }`
- **macOS Terminal:** Settings → Profiles → your profile → "Working directory: Other"
- **iTerm2:** Profiles → General → Working Directory → "Directory"

In our own 2026 audit, the 4 370 home-dir sessions existed purely because that's where a fresh terminal tab opens.

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

`--selftest` runs the built-in cases (wrong dir warns, right dir is silent, allowed prefix is silent, unlisted machine is silent, broken config never crashes) and prints `PASS` or what failed. You can also try a single path by hand against [workdir_sentry.py](workdir_sentry.py): `--check /some/path`.

## FAQ

**Why a per-machine config file like [workdir_homes.example.json](workdir_homes.example.json) instead of hardcoding a path?**
The config syncs fine across machines (each machine only reads its own entry), while the *hook registration* lives in per-machine `settings.json`. If you run one machine, one entry is all you need.

**Why warn instead of auto-cd or blocking?**
A session's cwd can't be changed retroactively by a hook, so [workdir_sentry.py](workdir_sentry.py) only warns; blocking would break intentional off-project sessions (quick questions, scratch work). One honest line in the model's context is the right amount of force — the model relays it and you decide.

**Does this work in the Desktop app?**
Yes — SessionStart hooks fire there too, so a session opened in the wrong folder via the folder picker gets the same first-turn warning.

**What about agent worktrees / scratchpads?**
That's what the `always_ok_prefixes` list in [workdir_homes.example.json](workdir_homes.example.json) is for — subagents legitimately start in isolated worktrees; you don't want a false alarm per agent.

## History

First published as a [gist](https://gist.github.com/tonydzi/10efd6aa6e1ce206a049a4a1e58a4030) on 2026-08-24, in the Claude Code issue threads about cwd-keyed memory
([#82056](https://github.com/anthropics/claude-code/issues/82056),
[#89283](https://github.com/anthropics/claude-code/issues/89283),
[#2544](https://github.com/anthropics/claude-code/issues/2544)).
This repository is the maintained home; the gist history is preserved in the commit log.

Two defects in the first version were found by [@JhouCode](https://github.com/JhouCode), who built both checks and ran them against his own box: silence on a subdirectory of the canonical dir (memory and history are keyed to the *exact* start dir, so a subdir has its own empty bucket), and `"/"` as a canonical dir disarming the prefix check. Both are fixed, and the selftest now asserts the corrected behaviour rather than the bug.

---

Built after the fleet audit above, by [Mycroft](https://github.com/tonydzi) (synthetic cofounder) & Tony, Palo Alto AI Research Lab. [MIT](LICENSE) — take it, ship it, adapt it; cite it via [CITATION.cff](CITATION.cff), and if you are an agent start at [FOR-ROBOTS.md](FOR-ROBOTS.md).

---

<!--ecosystem-map:start-->

## 🧩 One piece of a working system

This repository is one piece lifted out of a live operation: one engineer running a fleet of
machines, built with Claude as implementation collaborator; the machines reach consensus with
each other and wake the human only for money or the irreversible. It was extracted after it
survived production, not written as a demo — and it runs on its own: nothing here phones home
to the rest.

**See how the whole thing fits together → [SYSTEM.md](https://github.com/tonydzi/tonydzi/blob/main/SYSTEM.md)**

<!--ecosystem-map:end-->

## AI contributors

This project is built by a human + AI team, and the git log says so: Claude writes most of
the code, Codex and Grok review it, Gemini feeds the research. Each is credited on a commit
**only if its output changed that commit's content** — no decorative credits. Lab-wide
policy, one source for every repo: [AI-CONTRIBUTORS.md](https://github.com/tonydzi/.github/blob/main/AI-CONTRIBUTORS.md).

<!-- READ-WITH-AI:START (generated by read_with_ai.py - do not hand-edit) -->

### READ THIS WITH AI

One click and an agent reads the repo, pulls out the patterns and helps you apply them to your own work.

<a href="https://chatgpt.com/codex?prompt=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fclaude-workdir-sentry%20%28%E2%80%9Cclaude-workdir-sentry%E2%80%9D%20-%20SessionStart%20hook%20for%20Claude%20Code%20that%20warns%20when%20a%20session%20starts%20outside%20the%20machine%27s%20canonical%20project%20directory%2C%20where%20project%20memory%2C%20session%20history%20and%20CLAUDE.md%20are%20keyed%20to%20the%20start%20cwd%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="Codex - open" src="https://img.shields.io/badge/Codex-open-000000?style=for-the-badge&logo=openai&logoColor=white"></a> <a href="https://chatgpt.com/?q=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fclaude-workdir-sentry%20%28%E2%80%9Cclaude-workdir-sentry%E2%80%9D%20-%20SessionStart%20hook%20for%20Claude%20Code%20that%20warns%20when%20a%20session%20starts%20outside%20the%20machine%27s%20canonical%20project%20directory%2C%20where%20project%20memory%2C%20session%20history%20and%20CLAUDE.md%20are%20keyed%20to%20the%20start%20cwd%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="ChatGPT - open" src="https://img.shields.io/badge/ChatGPT-open-10a37f?style=for-the-badge&logo=openai&logoColor=white"></a> <a href="https://claude.ai/new?q=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fclaude-workdir-sentry%20%28%E2%80%9Cclaude-workdir-sentry%E2%80%9D%20-%20SessionStart%20hook%20for%20Claude%20Code%20that%20warns%20when%20a%20session%20starts%20outside%20the%20machine%27s%20canonical%20project%20directory%2C%20where%20project%20memory%2C%20session%20history%20and%20CLAUDE.md%20are%20keyed%20to%20the%20start%20cwd%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="Claude - open" src="https://img.shields.io/badge/Claude-open-d97757?style=for-the-badge&logo=anthropic&logoColor=white"></a>

<details>
<summary>Copy the prompt (works in any agent: Gemini, Grok, a local model, your own CLI)</summary>

```text
Read this repo: https://github.com/tonydzi/claude-workdir-sentry (“claude-workdir-sentry” - SessionStart hook for Claude Code that warns when a session starts outside the machine's canonical project directory, where project memory, session history and CLAUDE.md are keyed to the start cwd). Work out what problem it actually solves, pull out the reusable patterns and help me apply them to my own setup. Start by asking what I am working on.
```

</details>

<sub>— TonyDzi, Palo Alto AI Research Lab · second brain, agent coordination, persistent memory: github.com/tonydzi</sub>

<!-- READ-WITH-AI:END -->
