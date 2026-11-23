---
name: repo-runbook
description: Write a short, verified runbook for a repo (how to install, run, test, lint, migrate, and which ports/env it needs) into AGENTS.md so later sessions stop re-discovering it. Use when starting work in an unfamiliar repo, when a session begins with grep/sed crawling to find the test command, when onboarding someone, or when the runbook looks stale.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
license: MIT
---

# Repo runbook

A new session in a repo you have worked in before should not spend its first 40
tool calls grepping for the test command. It reads the runbook instead.

Two halves: `scripts/runbook.py` detects the mechanical facts, you verify the few
that matter and write the one-line context a scanner cannot know.

**Not for:** architecture docs, API reference or onboarding prose — this block is only install/run/test/lint/migrate/ports/env, kept short because every future session pays for it.

## Portability

Works in any agent that can run shell commands (pi, Claude Code, Codex, Cursor,
Gemini CLI, …): the instructions are plain Markdown and the helper is a stdlib
script. Commands use `$SKILL_DIR` for this skill's own directory — the folder that
holds this `SKILL.md`. Set it once per session, for example:

```bash
SKILL_DIR=~/.claude/skills/repo-runbook     # or ~/.codex/skills/…, ~/.pi/agent/skills/…, .cursor/skills/…
```

## When to run

- First working session in a repo, or after a stack change (new package manager,
  new service, new migration tool).
- A session that crawled through the tree looking for commands is proof the
  runbook is missing or stale.

## 1. Detect

```
python3 "$SKILL_DIR/scripts/runbook.py" scan [root]
```

It prints a proposed runbook block and writes nothing. It reads manifests only
(no source crawl): `pyproject.toml`, `requirements*.txt`, `uv.lock`,
`package.json` + lockfiles, `Makefile`, `justfile`, `docker-compose*.yml`,
`Dockerfile`, `.env*`, alembic/prisma/django config, CI config, and README
headings. Multi-repo folder: it lists each repo separately.

## 2. Verify before writing

Detection is a guess; a wrong runbook is worse than none. Check the three that
break most often, each with one cheap command:

1. **Test command** — run the narrowest real test (`pytest -q --collect-only`,
   `npm test -- --listTests`). If collection fails, the command is wrong.
2. **Dev server + port** — start it once (`--dry-run` where available) or read
   the actual bind address from source. Record the port you saw, not the default.
3. **Migrations** — the upgrade command must be the one that applies, not the one
   that creates.

Add what no scanner can see, one line each: which env var must come from the
secret store, which service must be running for tests (Postgres? Redis? broker),
which test suite is safe to run fully, and anything destructive to avoid.

## 3. Write it

```
python3 "$SKILL_DIR/scripts/runbook.py" write [root] --repo <name>
```

The block lands in `AGENTS.md` between `<!-- runbook:start -->` and
`<!-- runbook:end -->`, so re-running replaces only its own block. If the repo
uses `CLAUDE.md` instead, pass `--file CLAUDE.md`. Never create a second
competing file: if either exists, use it.

Keep the block under ~40 lines. It is loaded into every future session, so every
line costs tokens in all of them. No tables of every script — the commands you
actually run, nothing else.

The block ships two placeholders: **Not to run** and **Troubleshooting**. Fill them
only where you have evidence — a destructive command you actually saw documented, a
failure you actually hit. For troubleshooting, write the symptom as the user sees it,
then the cause, then the fix. A guess in this block is worse than a blank, because the
next session will trust it.

## 4. Check for drift

```
python3 "$SKILL_DIR/scripts/runbook.py" check [root]
```

Exits 1 when the file's manifest facts changed (dependency files newer than the
runbook block, commands no longer in `package.json`, a new service in the compose
file). Run it at the start of a session in a repo you last touched a while ago;
refresh only what drifted.

## Rules

- Commands are copy-pasteable exactly as written: absolute venv path or the
  package manager prefix, `cd` included if needed.
- Never put secrets, tokens, or real connection strings in the block: name the
  env var instead.
- Absolute paths of this machine stay out; the block must be valid for anyone who
  clones the repo.
- If the repo has no `AGENTS.md`/`CLAUDE.md`, the script creates `AGENTS.md`.
  Don't touch other files.
