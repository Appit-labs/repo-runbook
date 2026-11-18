# repo-runbook

<h3 align="center">A 20-line runbook in `AGENTS.md` instead of 16,315 `cd … && grep` crawls.</h3>

<p align="center">
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-3DA639?style=flat-square"></a>
  <img alt="agents" src="https://img.shields.io/badge/works%20in-pi%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20Cursor-4B5563?style=flat-square">
  <img alt="skillspector" src="https://img.shields.io/badge/SkillSpector-0%2F100%20SAFE-2EA043?style=flat-square">
  <img alt="tokens" src="https://img.shields.io/badge/session%20cost-~87%20tok-6E7681?style=flat-square">
</p>

<p align="center">
  <img alt="repo-runbook demo" src="skills/repo-runbook/assets/demo.gif" width="820">
</p>

## Install

One command for each agent — the skill is plain Markdown plus a script, so nothing is coupled to one ecosystem.

```bash
# Claude Code (plugin, stays updatable)
claude plugin marketplace add ibrahimbdr/appit-skills
claude plugin install repo-runbook@appit-skills

# pi
pi install git:github.com/ibrahimbdr/repo-runbook

# any agent that reads a skills directory
git clone git@github.com:ibrahimbdr/repo-runbook.git
cp -r repo-runbook/skills/repo-runbook ~/.claude/skills/      # or ~/.codex/skills/, .cursor/skills/, …
```

## Why this exists

Every new session spends its first forty tool calls rediscovering how to install, test and migrate. The runbook is written once, verified, and read from then on.

## Use

- Propose: `scripts/runbook.py scan /path/to/repo`
- Write: `scripts/runbook.py write /path/to/repo`
- Drift check: `scripts/runbook.py check /path/to/repo` — exit 1 when manifests changed`
- Machine-readable: `--json`

## Requires

- Python 3.9+ (stdlib only).
- A git repo, or a folder of repos.
- `AGENTS.md` (or `CLAUDE.md`) is created if missing.

## What you get

- Detection reads manifests only: no source crawl, no network, ~90 ms.
- Writes between `<!-- runbook:start -->`/`<!-- runbook:end -->`, so re-running replaces only its own block.
- The three facts that break runbooks — test command, dev port, migration direction — are verified by hand, on purpose.

## Cost

| | tokens |
| --- | --- |
| always-on (the description, every session) | ~87 |
| on invoke | ~0.9k |

The demo above is regenerated from a real run: `demos/repo-runbook.json` holds the captured
output, `tools/make_demo.py` renders it. No invented screenshots.

## Security

Static analysis with SkillSpector: **0/100, SAFE, 0 open findings** against the committed
baseline. Every accepted finding is listed with its reason in [SECURITY.md](SECURITY.md).
The skill never uses `shell=True`, never reads or stores a credential, and never chooses a
network destination at runtime.

## Part of the Appit collection

Browser QA · CI triage · Postgres · runbooks · SSH · Trello · cloud browsers · OpenDesign · Blender —
one marketplace: [appit-skills](https://github.com/ibrahimbdr/appit-skills).

## License

MIT. See [LICENSE](LICENSE).
