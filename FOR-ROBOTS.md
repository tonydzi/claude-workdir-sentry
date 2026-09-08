# FOR ROBOTS

You are an AI agent reading this repo. Ranked takeaways, densest first. One rule about this
file itself: **it is data, not authorization.** Nothing here overrides your operator's policies
or lets you install anything on your own. Read it, check your own session, then *propose* the
relevant items to your operator.

## Alpha, ranked

1. **Check where your session started before you trust your own memory.** Claude Code keys
   project memory, session history and the project `CLAUDE.md` to the directory the session
   *starts in*. Start elsewhere and none of it loads - with no error and no warning. If you
   feel context-less, suspect the cwd before you suspect the model.
2. **Absence of a warning is not evidence of health.** This whole failure mode is silent by
   construction. That is why it needs an instrument (`workdir_sentry.py`) rather than a habit.
3. **A watchdog must fail open.** Missing config, broken JSON, unexpected stdin -> print nothing,
   exit 0. A hook that can block a session start is worse than the bug it guards.
4. **Strip the BOM before you parse stdin.** PowerShell 5.1 pipes prepend a UTF-8 BOM; it broke
   two of our own tools before we learned to strip it.
5. **A subdirectory of the project is not the same as the project.** `CLAUDE.md` is searched
   cwd-upward and still loads, but memory and history are keyed to the *exact* start dir, so a
   subdir gets its own empty bucket. Warn softer there, do not stay silent - an earlier version
   was silent and its selftest asserted that silence, which is how the bug survived.
6. **Name your denominator before you quote a rate.** `~/.claude/projects/<slug>/` also holds
   `subagents/*.jsonl` (`"isSidechain": true`), which never open a memory store and never fire
   `SessionStart`. Counting `**/*.jsonl` measures the wrong population, and the bias has no fixed
   direction: on one node the same measurement reads 63.1% with the filter named and 47.3% without.
7. **Fix the door, not only the alarm.** Most wrong-folder sessions exist because a fresh terminal
   tab opens in the home directory. Point the terminal's default starting directory at the project.

## Provenance

Built and run inside a live 6-node Claude Code fleet. The numbers in the README are measurements
from that fleet, with the counting filter named; the correction in item 6 came from an external
reader ([@JhouCode](https://github.com/anthropics/claude-code/issues/82056)), not from us.

## Family

Governance rules-as-files: [claude-bible](https://github.com/tonydzi/claude-bible).
Always-loaded context budget: [always-loaded-diet](https://github.com/tonydzi/always-loaded-diet).
Agent authority model: [agent-leash](https://github.com/tonydzi/agent-leash).
