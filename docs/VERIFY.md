# Verify it yourself

Two checks prove that the book's workflow works on your machine: an automated acceptance test, and a five-minute manual check of the Claude Code hooks.

## 1. The acceptance test: `validate.sh`

`validate.sh` builds the project from a clean copy of [`shop-api/`](../shop-api/), then runs the workflow the book documents, step by step, using the real tools. Nothing is simulated.

```bash
bash validate.sh          # core workflow, about 5 minutes
bash validate.sh --full   # adds the final-state checks, Schemathesis, mutmut and the Docker image
```

**Needs:** Linux (or WSL), Python 3.12+, Docker, Git and a network connection (it installs packages). It uses port **5433** for PostgreSQL and **8000/8001** for the app, so stop anything else on those ports first.

**Where it works:** a new `book-acceptance-<pid>/shop-api` under `$AUDIT_TMP_ROOT` (default: `$TMPDIR`, else `/tmp`). The project is left there afterwards so you can inspect it. Logs and a version manifest go to that run's own `validation-run-<timestamp>-<pid>/` directory.

```bash
export AUDIT_TMP_ROOT=~/book-runs     # optional: keep runs somewhere roomier than /tmp
bash validate.sh --full 2>&1 | tee run.log
echo "exit code: ${PIPESTATUS[0]}"
```

### What it checks

| Section | What runs |
|---|---|
| 0–3 Setup | Python ≥ 3.12, Docker, the Step 3.2 installs, `requirements-dev.txt`, a version manifest, PostgreSQL on 5433 |
| 4 Foundation | The health test, `check.sh` on the Step 3.3 skeleton, the first commit on `main`, then Ruff, Ruff format, mypy and pytest one by one |
| 5 Red | The 7 tests fail for behavioural reasons ("7 failed, 1 passed"), not import or fixture errors; the Stop hook lets Claude stop; the commit contains only the test file |
| 6–7 Green, Refactor | `check.sh` passes; the approved tests are unchanged (`git diff <red-commit> -- tests/`, `git status`); the commit history; `git diff main...HEAD` |
| 8 Guardrails | The lock hook (blocks in Green, allows app edits and Red edits); the Stop hook (allows on pass, blocks on failure, gives up after 5 attempts, inactive with no marker) |
| 9 Migrations | `alembic init`, the three documented edits to `env.py`, an empty database, the initial migration, the upgrade/downgrade/upgrade round-trip, and the empty-migration warning |
| 10 `--full` | The out-of-range id test; Ruff, format, mypy, pytest and `check.sh` on the final project; the rebuilt project matches `shop-api/`; `/health`; Schemathesis unpinned and seeded (the seeded run must actually cancel order 1); mutmut (all mutants killed); the Docker build, `/health` in the container, and `.dockerignore` |

Every check is PASS, FAIL, PARTIAL or BLOCKED. **Only PASS counts as success.** If anything else appears, the run ends with `NOT ALL CHECKS PASSED` and exit code 1.

## 2. The live hook check

`validate.sh` runs the hook *scripts* directly. It cannot prove that Claude Code loads `.claude/settings.json` and fires them during a real session. That takes five minutes by hand.

### Setup

Use a project from a passing run (the `project kept at:` path `validate.sh` prints), not your own work and not this repository:

```bash
cd <the "project kept at:" path>
source .venv/bin/activate
docker compose -f docker-compose.test.yml up -d    # the Stop hook runs check.sh, which needs the database
bash scripts/check.sh                              # must end "All checks passed."
git add -A && git commit -qm "baseline for the live hook check"
echo green > .tdd-phase
claude
```

### Steps

Record PASS or FAIL for each. A step you can't complete is BLOCKED, not a pass.

1. **The hooks are registered.** Type `/hooks`. You should see a `PreToolUse` hook with matcher `Edit|Write` running `.claude/hooks/lock_tests.py`, and a `Stop` hook running `.claude/hooks/verify_on_stop.py`, both marked as project settings.
2. **A test edit is blocked during Green.** Ask: *"Edit `tests/api/test_order_cancel.py` and change the first assertion to expect 418."* PASS: the edit is refused with `Green phase: tests are locked…`, and `git status --short tests/` (in another terminal) is empty.
3. **An application edit is allowed.** Ask Claude to add or change the docstring of `cancel_order` in `app/services/orders.py`. PASS: the `Update(app/services/orders.py)` goes through with no hook error. This is the control for step 2.
4. **The Stop hook blocks while checks fail.** In another terminal:
   ```bash
   sed -i 's/order.status = "cancelled"/order.status = "canceled"/' app/services/orders.py
   ```
   Then tell Claude *"That's all for now, thanks."* PASS: the session shows `Not done — checks failing (attempt 1 of 5)` with the failing output, and Claude keeps working instead of ending the turn. Claude may well fix the code itself.
5. **The Stop hook allows a stop once checks pass.** With the checks green again, let Claude finish. PASS: the turn ends normally and `ls .tdd-stop-attempts` reports no such file.

Claude Code keeps a transcript of every session under `~/.claude/projects/`. If a screen capture is ambiguous, the transcript shows exactly which tool ran and what each hook returned.

### Afterwards

```bash
rm -f .tdd-phase .tdd-stop-attempts
docker compose -f docker-compose.test.yml down
```
