# How to use this book

*Test-Driven Backend Development with Claude Code* is a hands-on book. You build one small service, **shop-api**, and one feature, **cancelling an order**, and along the way you set up the workflow you will reuse for every feature afterwards. This guide explains how to read it, how to follow along, and how to use this repository to check your work.

- [Before you start](#before-you-start)
- [Choose a reading path](#choose-a-reading-path)
- [The book, part by part](#the-book-part-by-part)
- [Following along with this repository](#following-along-with-this-repository)
- [Checking your work at each stage](#checking-your-work-at-each-stage)
- [Shortcuts](#shortcuts)
- [When something goes wrong](#when-something-goes-wrong)
- [FAQ](#faq)
- [Questions](#questions)

---

## Before you start

You will need the tools from Part 2 (p. 9):

| Tool | Why |
|---|---|
| Python 3.12 or newer, with `venv` | Runs the app and every tool |
| Docker | A throwaway PostgreSQL for the tests (port 5433) |
| Git | Commits the tests separately so any later change to them is visible; feeds CI |
| Claude Code | Writes tests and code, runs them, fixes failures |
| A GitHub account | For CI/CD in Part 8 (not needed before then) |
| GitHub CLI `gh` (optional) | Opens pull requests from the terminal |

The book's commands assume **Linux**. On Windows, use **WSL**: every command then works unchanged. You should be comfortable reading Python. Everything else, from the terminal to hooks, is explained as you go.

How to read the book's code blocks:
- The small label on each block says where it goes: a **file path**, **Terminal**, or **Type in Claude Code**.
- Lines starting with `#` in terminal blocks are comments.
- A file listing labelled with a path is the **complete file** unless the text says it is a change to an existing one, as in Phase 4b and 4d.

## Choose a reading path

**New to TDD, or to Claude Code?** Read in order, Part 1 to Part 10, and build as you go. Part 3, the foundation, takes about an hour the first time.

**You already know TDD and pytest?** Skim Parts 1–2, then:
1. Part 3, Steps 3.5–3.8: the pytest configuration, the transaction-isolated fixtures and `check.sh`. These are the pieces everything else depends on.
2. Part 4: the hooks. This is the core idea of the book.
3. Part 5: the feature loop, including Phase 4's extra verification.
4. Parts 6–8 as you need them.

**You only want the guardrails for your own project?** Read Section 1.2, then Part 4. Take `.claude/hooks/`, `.claude/settings.json` and `scripts/check.sh` from [`shop-api/`](../shop-api/), and adapt `check.sh` to your project's tools.

## The book, part by part

Page numbers are the printed numbers in the PDF.

| Part | Page | What you do | Where it ends up in this repository |
|---|---|---|---|
| **1 · The Big Picture** | 1 | Learn why tests matter more when an AI writes the code, and the "two ways to make a test pass" problem the book solves | — |
| **2 · Prerequisites** | 9 | Install the tools; terminal basics; where Claude Code keeps its configuration | — |
| **3 · Build the Foundation** | 14 | Create the project, dependencies, the minimal app, the Docker test database, pytest/Ruff/mypy config, the fixtures, `check.sh`, `.gitignore`, `CLAUDE.md`, first commit | `shop-api/app/` (skeleton), `docker-compose.test.yml`, `pyproject.toml`, `tests/conftest.py`, `tests/test_health.py`, `scripts/check.sh`, `.gitignore`, `CLAUDE.md`; router stub in [`stages/router_stage1_stub.py`](../stages/router_stage1_stub.py) |
| **4 · Guardrails** | 43 | How hooks work; the `.tdd-phase` marker; the hook that locks tests during Green; the Stop hook that won't let Claude finish while checks fail; registering and testing them | `shop-api/.claude/hooks/lock_tests.py`, `verify_on_stop.py`, `shop-api/.claude/settings.json` |
| **5 · The Feature Loop** | 93 | Phase 0 spec → 1 Red → 2 Green → 3 Refactor → 4 verification (migrations, Schemathesis, smoke test, mutation testing) → 5 review and ship | [`stages/`](../stages/) for Phases 1–3; final `app/routers/orders.py`, `app/services/orders.py`, `tests/api/test_order_cancel.py`, `migrations/`, `schemathesis.toml` |
| **6 · Subagents** | 130 | A test writer that works only from the spec, and a reviewer that can't edit | `shop-api/.claude/agents/` |
| **7 · The /tdd skill** | 133 | Package the whole loop into one command | `shop-api/.claude/skills/tdd/SKILL.md` |
| **8 · CI/CD** | 138 | Put the project on GitHub; a workflow that runs the migration round-trip and `check.sh`; branch protection; the Docker image; a deploy job | `shop-api/.github/workflows/ci.yml`, `Dockerfile`, `.dockerignore` |
| **9 · Troubleshooting** | 150 | Symptoms, causes and fixes; six ways tests can mislead you | — |
| **10 · Your daily routine** | 158 | The cheat sheet and the checklist before every pull request | — |
| **Appendices** | 160 | A: uv and Poetry equivalents · B: glossary · C: the final project layout | C matches [`shop-api/`](../shop-api/) |

## Following along with this repository

The book is designed to be **built by hand**: "do them by hand once, so you understand every piece" (Part 3). So:

1. **Build your own project in a separate folder**, following the book from Step 3.1:

   ```bash
   mkdir -p ~/code && cd ~/code
   mkdir shop-api && cd shop-api      # Step 3.1 continues from here
   ```

   Don't build inside your clone of this repository; keep this repository as the reference.

2. **Type the code yourself** (or have Claude write it, as the book shows from Part 5 on), then **compare** with the reference when a step is done.

3. **Expect a few differences.** They are by design:
   - `requirements.txt`: yours comes from `pip freeze` on your machine (Step 3.2). The one here pins the versions the book was tested with.
   - `migrations/versions/<id>_create_orders_table.py`: Alembic generates a random revision id, so your file name and id differ. The `upgrade()` and `downgrade()` bodies should match.
   - `.venv/`, caches, `.tdd-phase`, `.tdd-stop-attempts`: local working files, never committed.

## Checking your work at each stage

[`shop-api/`](../shop-api/) is the **final** state. During Part 5, compare against [`stages/`](../stages/) instead, because the code changes from phase to phase:

| After… | `app/routers/orders.py` should match | Also compare |
|---|---|---|
| Step 3.3 (minimal app) | `stages/router_stage1_stub.py` | — |
| Part 5, Phase 1 (Red) | (still the stub) | `tests/api/test_order_cancel.py` ↔ `stages/test_order_cancel_red.py` |
| Phase 2 (Green) | `stages/router_stage2_green.py` | tests unchanged since the Red commit |
| Phase 3 (Refactor) | `stages/router_stage3_refactor.py` | `app/services/orders.py` ↔ `stages/services_orders.py` |
| Phase 4b and 4d | `shop-api/app/routers/orders.py` | `tests/api/test_order_cancel.py` ↔ `shop-api/tests/api/test_order_cancel.py` |

For example, after Phase 3:

```bash
diff ~/code/shop-api/app/routers/orders.py  stages/router_stage3_refactor.py
diff ~/code/shop-api/app/services/orders.py stages/services_orders.py
```

And at the end of the book, the whole project:

```bash
diff -r ~/code/shop-api shop-api \
  -x .git -x .venv -x __pycache__ -x .mypy_cache -x .ruff_cache -x .pytest_cache \
  -x mutants -x .hypothesis -x .schemathesis -x requirements.txt -x versions
```

The real test, though, is the book's own definition of done: `bash scripts/check.sh` exits 0.

## Shortcuts

**Skip Part 3 and start at the feature loop.** Copy the finished project and take it back to the state Part 5 starts from:

```bash
REPO=~/tdd-backend-claude-code        # wherever you cloned this repository
mkdir -p ~/code && cp -r "$REPO/shop-api" ~/code/shop-api && cd ~/code/shop-api
cp "$REPO/stages/router_stage1_stub.py" app/routers/orders.py
rm -f app/services/orders.py tests/api/test_order_cancel.py
rm -rf migrations alembic.ini        # Phase 4a creates these
git init && git add . && git commit -m "chore: project skeleton with test harness"
git branch -M main
```

Then set up the virtual environment and database as in the [quick start](../README.md#quick-start-run-the-finished-project), and begin Part 5, Phase 0. This is exactly the starting point `validate.sh` uses.

**Just watch the workflow run.** `bash validate.sh` replays Red → Green → Refactor, the hooks and the migrations from a clean copy, and prints a PASS/FAIL table. See [VERIFY.md](VERIFY.md).

## When something goes wrong

Part 9 (p. 150) has the full table. The ones readers hit most:

| Symptom | Fix |
|---|---|
| `command not found: pytest` (or ruff, mypy, alembic) | The virtual environment isn't active: `source .venv/bin/activate` |
| `Connection refused` on port 5433 | Start the test database: `docker compose -f docker-compose.test.yml up -d` |
| `port is already allocated` on 5433 | A container from an earlier run still holds it: `docker ps --filter publish=5433`, then `docker rm -f <id>` |
| `Future attached to a different loop` | Both `asyncio_default_fixture_loop_scope` and `asyncio_default_test_loop_scope` must be `"session"` (Step 3.5) |
| The autogenerated migration is empty | The database already had the tables. Restart the test database, then autogenerate again (Phase 4a) |
| Hook doesn't fire | Start `claude` from the project root, run `/hooks`, and test the script by hand (Step 4.7) |
| Claude keeps getting sent back by the Stop hook | The checks really fail, or `.tdd-phase` was left at `green`: `rm -f .tdd-phase .tdd-stop-attempts` when you're not doing TDD |

## FAQ

**Do I need Claude Code for every part?** No. Part 3 and the hand tests in Step 4.7 run in an ordinary terminal. Claude Code is needed from Step 4.6's `/hooks` check onwards, for the feature loop in Part 5, and for Parts 6–7.

**Can I use uv or Poetry instead of pip?** Yes. Appendix A (p. 160) maps every pip command, and says what else to update.

**Why doesn't the CI workflow run in this repository?** GitHub only runs workflows from a repository's own `.github/workflows/` at its root. `shop-api/.github/workflows/ci.yml` is meant for *your* shop-api repository, which you create in Part 8, Step 8.5.

**Is the `X-User-Id` header real authentication?** No. It keeps the example small, and the book says so (Step 3.3). Replace it with proper JWT/OAuth2 before anything goes to production.

**The hooks block Claude from editing tests — can Claude get around them?** The test lock covers the `Edit` and `Write` tools. A shell command could still change a file, which is why the book calls the hook "a guardrail, not a jail" and uses Git as the second line of defence (Step 4.7).

## Questions

Email **[danielude98@gmail.com](mailto:danielude98@gmail.com)**. For mistakes in the book or the code, please [open an issue](../../../issues) with the page number.
