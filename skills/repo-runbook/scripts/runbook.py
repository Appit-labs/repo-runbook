#!/usr/bin/env python3
"""Propose, write, and drift-check a short repo runbook block in AGENTS.md.

    runbook.py scan  [root] [--json]
    runbook.py write [root] [--file AGENTS.md] [--repo NAME]
    runbook.py check [root] [--file AGENTS.md]
    runbook.py self-test

Manifests only: no source crawl, no network, stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

START = "<!-- runbook:start -->"
END = "<!-- runbook:end -->"
SKIP = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "__pycache__"}


def find_repos(root: Path) -> list[Path]:
    if (root / ".git").exists():
        return [root]
    found = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and p.name not in SKIP and (p / ".git").exists():
            found.append(p)
    return found or [root]


def read(p: Path, limit: int = 400_000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def json_file(p: Path) -> dict:
    try:
        return json.loads(read(p))
    except (json.JSONDecodeError, ValueError):
        return {}


def detect_python(repo: Path) -> dict:
    out = {}
    pyproject = repo / "pyproject.toml"
    text = read(pyproject) if pyproject.exists() else ""
    reqs = " ".join(read(p) for p in repo.glob("requirements*.txt"))
    deps = (text + " " + reqs).lower()
    if not (pyproject.exists() or reqs.strip()):
        return out
    has_venv = (repo / ".venv" / "bin" / "python").exists()
    py = ".venv/bin/python" if has_venv else "python3"
    if (repo / "uv.lock").exists():
        base = "uv run "
    elif (repo / "poetry.lock").exists():
        base = "poetry run "
    else:
        base = "" if has_venv else ""
    out["install"] = "uv sync" if (repo / "uv.lock").exists() else (
        "poetry install" if (repo / "poetry.lock").exists() else f"{py} -m pip install -r requirements.txt")
    if "pytest" in deps or (repo / "tests").is_dir() or (repo / "pytest.ini").exists():
        out["test"] = f"{base}pytest -q" if base else f"{py} -m pytest -q"
    if "ruff" in deps or (repo / "ruff.toml").exists() or ".ruff.toml" in deps:
        out["lint"] = f"{base}ruff check ."
    if "mypy" in deps or (repo / "mypy.ini").exists():
        out["typecheck"] = f"{base}mypy ."
    for runner in ("uvicorn", "gunicorn"):
        m = re.search(rf'{runner}\s+([\w.]+:app)', text)
        if m:
            out["run"] = f"{base}{runner} {m.group(1)} --reload"
            break
    if (repo / "alembic.ini").exists() or (repo / "alembic").is_dir():
        out["migrate"] = f"{base}alembic upgrade head"
    if (repo / "manage.py").exists():
        out["migrate"] = f"{py} manage.py migrate"
    return out


def detect_node(repo: Path) -> dict:
    pkg = repo / "package.json"
    if not pkg.exists():
        return {}
    data = json_file(pkg)
    scripts = data.get("scripts") or {}
    pm = "npm"
    if (repo / "pnpm-lock.yaml").exists():
        pm = "pnpm"
    elif (repo / "yarn.lock").exists():
        pm = "yarn"
    elif (repo / "bun.lockb").exists():
        pm = "bun"
    run = {"npm": "npm run", "pnpm": "pnpm", "yarn": "yarn", "bun": "bun run"}[pm]
    out = {"install": {"npm": "npm ci", "pnpm": "pnpm install", "yarn": "yarn",
                       "bun": "bun install"}[pm]}
    for key, names in (("test", ("test", "test:unit")), ("run", ("dev", "start")),
                       ("build", ("build",)), ("lint", ("lint", "lint:fix")),
                       ("typecheck", ("typecheck", "type-check", "tsc"))):
        for n in names:
            if n in scripts:
                out[key] = f"{run} {n}"
                break
    if "prisma" in json.dumps(data).lower():
        out["migrate"] = f"{pm} exec prisma migrate dev"
    return out


def detect_other(repo: Path) -> dict:
    out = {}
    if (repo / "go.mod").exists():
        out.update({"test": "go test ./...", "build": "go build ./...", "install": "go mod download"})
    if (repo / "Cargo.toml").exists():
        out.update({"test": "cargo test", "build": "cargo build", "install": "cargo fetch"})
    if (repo / "Makefile").exists():
        targets = re.findall(r"^([a-zA-Z][\w-]*):", read(repo / "Makefile"), re.M)
        if targets:
            out["make_targets"] = sorted({t for t in targets if t not in {"all", "clean"}})[:12]
    return out


def detect_services(repo: Path) -> list[str]:
    services: list[str] = []
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        p = repo / name
        if not p.exists():
            continue
        in_services = False
        for line in read(p).splitlines():
            if re.match(r"^[a-z]+", line) or re.match(r"^\S", line):
                in_services = line.strip() == "services:"
                continue
            m = re.match(r"^  ([a-zA-Z][\w-]*):\s*$", line)
            if m and in_services:
                services.append(m.group(1))
        break
    return services


def detect_env(repo: Path) -> list[str]:
    keys: list[str] = []
    for name in (".env.example", ".env.sample", ".env.template"):
        p = repo / name
        if p.exists():
            keys = re.findall(r"^([A-Z][A-Z0-9_]+)=", read(p), re.M)[:12]
            break
    return keys


def detect(repo: Path) -> dict:
    facts: dict = {}
    for part in (detect_python(repo), detect_node(repo), detect_other(repo)):
        for k, v in part.items():
            facts.setdefault(k, v)
    facts["services"] = detect_services(repo)
    facts["env_keys"] = detect_env(repo)
    facts["ci"] = [p.name for p in (repo / ".github" / "workflows").glob("*.yml")] if (repo / ".github" / "workflows").is_dir() else []
    return facts


def render(repo: Path, facts: dict) -> str:
    name = repo.name
    lines = [START, f"### Runbook: {name}", ""]
    order = [("install", "Install"), ("run", "Run"), ("test", "Test"), ("lint", "Lint"),
             ("typecheck", "Typecheck"), ("build", "Build"), ("migrate", "Migrate")]
    for key, label in order:
        if facts.get(key):
            lines.append(f"- **{label}:** `{facts[key]}`")
    if facts.get("make_targets"):
        lines.append(f"- **Make targets:** {', '.join('`' + t + '`' for t in facts['make_targets'])}")
    if facts.get("services"):
        lines.append(f"- **Services:** {', '.join(facts['services'])} (`docker compose up -d`)")
    if facts.get("env_keys"):
        lines.append(f"- **Env keys needed:** {', '.join('`' + k + '`' for k in facts['env_keys'])}")
    if facts.get("ci"):
        lines.append(f"- **CI:** {', '.join(facts['ci'][:4])}")
    lines.append("- **Not to run:** _(fill in: destructive commands, suites that need the prod DB)_")
    lines.append("- **Troubleshooting:** _(fill in: symptom -> cause -> fix, only for failures actually hit here)_")
    lines.append(END)
    return "\n".join(lines)


def block_span(text: str) -> tuple[int, int] | None:
    a = text.find(START)
    b = text.find(END)
    return (a, b + len(END)) if a != -1 and b != -1 else None


def cmd_scan(root: Path, as_json: bool) -> int:
    repos = find_repos(root)
    results = {str(r): detect(r) for r in repos}
    if as_json:
        print(json.dumps(results, indent=2))
        return 0
    for r in repos:
        print(render(r, results[str(r)]))
        print()
    return 0


def cmd_write(root: Path, target: str, repo_name: str | None) -> int:
    repo = next((r for r in find_repos(root) if repo_name is None or r.name == repo_name), None)
    if repo is None:
        print(f"no repo named {repo_name!r} under {root}", file=sys.stderr)
        return 2
    block = render(repo, detect(repo))
    path = root / target
    old = read(path) if path.exists() else ""
    span = block_span(old)
    new = (old[:span[0]] + block + old[span[1]:]) if span else (old.rstrip() + "\n\n" + block + "\n" if old else block + "\n")
    path.write_text(new, encoding="utf-8")
    print(f"{'updated' if span else 'wrote'} {path} ({len(block.splitlines())} lines)")
    return 0


def cmd_check(root: Path, target: str) -> int:
    path = root / target
    if not path.exists():
        print(f"{path} missing: run write")
        return 1
    facts = detect(find_repos(root)[0])
    fresh = render(find_repos(root)[0], facts)
    old = read(path)
    span = block_span(old)
    if span is None:
        print("no runbook block found: run write")
        return 1
    stale = [ln for ln in fresh.splitlines() if ln.startswith("- **") and ln.split("**")[1] not in old]
    if stale:
        print("stale:")
        for ln in stale:
            print("  " + ln)
        return 1
    print("runbook current")
    return 0


def self_test() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "demo"
        (repo / ".git").mkdir(parents=True)
        (repo / "uv.lock").write_text("")
        (repo / "pyproject.toml").write_text('[project]\ndependencies = ["pytest","ruff"]\n')
        (repo / "package.json").write_text(json.dumps({"scripts": {"test": "vitest", "dev": "vite"}}))
        (repo / "pnpm-lock.yaml").write_text("")
        (repo / "compose.yaml").write_text("services:\n  db:\n    image: postgres\n  redis:\n    image: redis\n")
        (repo / ".env.example").write_text("DATABASE_URL=\nREDIS_URL=\n")
        f = detect(repo)
        assert f["install"] == "uv sync", f
        assert f["test"].startswith("uv run pytest"), f
        assert f["run"] == "pnpm dev", f
        assert f["services"] == ["db", "redis"], f
        assert f["env_keys"] == ["DATABASE_URL", "REDIS_URL"], f
        block = render(repo, f)
        assert START in block and END in block and "uv sync" in block, block
        p = Path(tmp) / "AGENTS.md"
        p.write_text("# Repo\n\n" + block + "\n\n## Later\n")
        old = read(p)
        span = block_span(old)
        assert span and "# Later" in old[span[1]:], "marker span"
        print("self-test ok")
        return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cmd, args = argv[1], argv[2:]
    if cmd == "self-test":
        return self_test()
    flags = {a.lstrip("-"): True for a in args if a.startswith("--") and "=" not in a}
    opts = dict(a.lstrip("-").split("=", 1) for a in args if a.startswith("--") and "=" in a)
    paths = [a for a in args if not a.startswith("--")]
    root = Path(paths[0]).resolve() if paths else Path.cwd()
    target = opts.get("file", "AGENTS.md")
    if cmd == "scan":
        return cmd_scan(root, bool(flags.get("json")))
    if cmd == "write":
        return cmd_write(root, target, opts.get("repo"))
    if cmd == "check":
        return cmd_check(root, target)
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
