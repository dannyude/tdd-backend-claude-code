#!/usr/bin/env python3
"""Assembles the companion site into _site/ (served by GitHub Pages).

    python3 site/build.py            # -> _site/
    python3 -m http.server -d _site  # preview at http://localhost:8000

Everything the page shows is read from this repository at build time: the stage files from
stages/, the 54 acceptance checks from validate.sh (each `rec` call, in order, under its `say`
section), the hook messages from shop-api/.claude/hooks/. The page is one HTML file with that
data inlined, the book's two fonts (subset to Latin) and the assets/ folder beside it.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "_site"
PDF = "Test-Driven-Backend-Development-with-Claude-Code.pdf"
PAGE_OFFSET = 6  # printed page n is PDF page n + 6

# Captured by replaying stages/README.md against the test database; see the commit message.
STAGES = [
    {
        "id": "stub", "label": "Stub", "where": "Step 3.3", "phase": "",
        "lead": "The empty router. The app runs, the health test passes, and there is no "
                "cancel endpoint yet.",
        "cmds": ["cp stages/router_stage1_stub.py app/routers/orders.py", "pytest -q"],
        "files": ["router_stage1_stub.py"],
        "out": [["pass", "1 passed in 0.03s"]],
    },
    {
        "id": "red", "label": "Red", "where": "Part 5 · Phase 1", "phase": "red",
        "lead": "Seven tests, written from the spec and committed alone. They fail for "
                "behavioural reasons: the endpoint doesn't exist, so every request is a 404.",
        "cmds": ["echo red > .tdd-phase",
                 "cp stages/test_order_cancel_red.py tests/api/test_order_cancel.py",
                 "pytest -q"],
        "files": ["test_order_cancel_red.py"],
        "out": [["fail", "FAILED tests/api/test_order_cancel.py::test_owner_cancels_pending_order"],
                ["fail", "FAILED tests/api/test_order_cancel.py::test_cancel_shipped_order_conflicts"],
                ["fail", "FAILED tests/api/test_order_cancel.py::test_cancel_other_users_order_not_found"],
                ["fail", "FAILED tests/api/test_order_cancel.py::test_cancel_missing_order_not_found"],
                ["fail", "FAILED tests/api/test_order_cancel.py::test_cancel_requires_auth"],
                ["fail", "FAILED tests/api/test_order_cancel.py::test_cancel_twice_is_idempotent"],
                ["fail", "FAILED tests/api/test_order_cancel.py::test_cancel_delivered_order_conflicts"],
                ["fail", "7 failed, 1 passed in 0.09s"]],
    },
    {
        "id": "green", "label": "Green", "where": "Part 5 · Phase 2", "phase": "green",
        "lead": "The tests are now locked. Claude writes the first implementation, with every "
                "rule inside the endpoint, until check.sh exits 0.",
        "cmds": ["echo green > .tdd-phase",
                 "cp stages/router_stage2_green.py app/routers/orders.py",
                 "bash scripts/check.sh"],
        "files": ["router_stage2_green.py"],
        "out": [["dim", "==> ruff lint"], ["dim", "==> ruff format"], ["dim", "==> mypy"],
                ["dim", "==> pytest"], ["pass", "8 passed in 0.06s"],
                ["pass", "All checks passed."]],
    },
    {
        "id": "refactor", "label": "Refactor", "where": "Part 5 · Phase 3", "phase": "green",
        "lead": "The cancellation rules move into a service and the router gets thin. Same "
                "tests, untouched, still green: behaviour unchanged.",
        "cmds": ["cp stages/services_orders.py app/services/orders.py",
                 "cp stages/router_stage3_refactor.py app/routers/orders.py",
                 "bash scripts/check.sh"],
        "files": ["services_orders.py", "router_stage3_refactor.py"],
        "out": [["dim", "==> ruff lint"], ["dim", "==> ruff format"], ["dim", "==> mypy"],
                ["dim", "==> pytest"], ["pass", "8 passed in 0.06s"],
                ["pass", "All checks passed."]],
    },
]
DEST = {
    "router_stage1_stub.py": "app/routers/orders.py",
    "test_order_cancel_red.py": "tests/api/test_order_cancel.py",
    "router_stage2_green.py": "app/routers/orders.py",
    "services_orders.py": "app/services/orders.py",
    "router_stage3_refactor.py": "app/routers/orders.py",
}

PARTS = [
    ("1", "The Big Picture", 1, "Why tests matter more when an AI writes the code, and the "
     "“two ways to make a test pass” problem.", ""),
    ("2", "Prerequisites", 9, "Install the tools; terminal basics; where Claude Code keeps "
     "its configuration.", ""),
    ("3", "Build the Foundation", 14, "The project, the Docker test database, pytest/Ruff/mypy, "
     "transaction-isolated fixtures, check.sh, the first commit.", "shop-api/scripts/check.sh"),
    ("4", "Guardrails", 43, "Hooks, the .tdd-phase marker, the test lock during Green and the "
     "Stop hook that won't let Claude finish while checks fail.", "shop-api/.claude/hooks/"),
    ("5", "The Feature Loop", 93, "Spec → Red → Green → Refactor → Verify → Review: migrations, "
     "Schemathesis, smoke test, mutation testing.", "stages/"),
    ("6", "Subagents", 130, "A test writer that works only from the spec, and a reviewer "
     "that can't edit.", "shop-api/.claude/agents/"),
    ("7", "The /tdd skill", 133, "The whole loop, packaged into one command.",
     "shop-api/.claude/skills/tdd/SKILL.md"),
    ("8", "CI/CD", 138, "GitHub Actions running the same checks, branch protection, the "
     "Docker image, a deploy job.", "shop-api/.github/workflows/ci.yml"),
    ("9", "Troubleshooting", 150, "Symptoms, causes and fixes; six ways tests can mislead "
     "you.", ""),
    ("10", "Your daily routine", 158, "The cheat sheet and the checklist before every pull "
     "request.", ""),
    ("A–C", "Appendices", 160, "uv and Poetry equivalents · glossary · the final project "
     "layout.", "shop-api/"),
]


def checks() -> list[dict]:
    """Every `rec` in validate.sh, first occurrence, under its section; BLOCKED-only skipped."""
    sec, order, status = "", [], {}
    for line in (ROOT / "validate.sh").read_text().splitlines():
        m = re.search(r'\bsay "([^"]+)"', line)
        if m and not line.lstrip().startswith("say()"):
            sec = m.group(1)
        for name, st in re.findall(r'\brec "((?:[^"\\]|\\.)*)" (PASS|FAIL|PARTIAL|BLOCKED)', line):
            name = name.replace("$PYV", "3.12")
            status.setdefault(name, set()).add(st)
            if name not in {c["name"] for c in order}:
                order.append({"section": sec, "name": name})
    return [c for c in order if status[c["name"]] != {"BLOCKED"}]


def fonts(dst: Path) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    latin = "".join(chr(c) for c in range(0x20, 0x7F)) + "·→←—–“”‘’…✓✗●•×▸▾"
    srcs = {
        "display.woff2": [ROOT / "assets/fonts/Caladea-Bold.ttf"],
        "mono.woff2": [Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")],
        "mono-bold.woff2": [Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")],
    }
    dst.mkdir(parents=True, exist_ok=True)
    for name, cands in srcs.items():
        src = next((p for p in cands if p.exists()), None)
        if src is None:
            print(f"  (skipping {name}: font not installed; the page falls back to system fonts)")
            continue
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        f = TTFont(src)
        s = subset.Subsetter(opts)
        s.populate(text=latin)
        s.subset(f)
        f.flavor = "woff2"
        f.save(dst / name)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for p in (ROOT / "assets").iterdir():
        if p.suffix in {".svg", ".png", ".mp4", ".gif"}:
            shutil.copy2(p, OUT / "assets" / p.name)
    shutil.copy2(ROOT / "book" / PDF, OUT / PDF)
    fonts(OUT / "fonts")

    hooks = ROOT / "shop-api/.claude/hooks"
    data = {
        "stages": STAGES,
        "files": {name: {"dest": dest, "src": (ROOT / "stages" / name).read_text()}
                  for name, dest in DEST.items()},
        "checks": checks(),
        "parts": [{"n": n, "title": t, "page": p, "pdf": p + PAGE_OFFSET, "what": w,
                   "path": path} for n, t, p, w, path in PARTS],
        "pdf": PDF,
        "hooks": {"lock": (hooks / "lock_tests.py").read_text(),
                  "stop": (hooks / "verify_on_stop.py").read_text()},
    }
    assert len(data["checks"]) == 54, f"expected 54 checks, found {len(data['checks'])}"
    html = (SITE / "index.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", payload)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"built {OUT.relative_to(ROOT)}/ · {len(data['checks'])} checks · "
          f"{len(data['files'])} stage files")


if __name__ == "__main__":
    main()
