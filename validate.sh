#!/usr/bin/env bash
# =============================================================================
#  Acceptance test for "Test-Driven Backend Development with Claude Code"
#
#  Runs the workflow the book documents, from a clean checkout, and prints a
#  PASS/FAIL table. Nothing here is simulated: every step runs the real tools.
#
#  Requirements: Python 3.12+, Docker, git, and a network connection.
#  Usage:  bash validate.sh            # core workflow (about 5 minutes)
#          bash validate.sh --full     # adds Schemathesis, mutmut and Docker
#
#  Every check is recorded as PASS, FAIL, PARTIAL or BLOCKED. Only PASS counts
#  as success: any other status makes the run fail with a non-zero exit code.
#  Each run writes its logs to its own directory, so runs never mix evidence.
# =============================================================================
set -uo pipefail

AUDIT_TMP_ROOT="${AUDIT_TMP_ROOT:-${TMPDIR:-/tmp}}"
mkdir -p "$AUDIT_TMP_ROOT" || {
  echo "Cannot create audit temporary directory: $AUDIT_TMP_ROOT" >&2
  exit 2
}
[[ -w "$AUDIT_TMP_ROOT" ]] || {
  echo "Audit temporary directory is not writable: $AUDIT_TMP_ROOT" >&2
  exit 2
}

export AUDIT_TMP_ROOT
export TMPDIR="$AUDIT_TMP_ROOT"
export TMP="$AUDIT_TMP_ROOT"
export TEMP="$AUDIT_TMP_ROOT"
export CLAUDE_CODE_TMPDIR="${CLAUDE_CODE_TMPDIR:-$AUDIT_TMP_ROOT}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
WORK="$AUDIT_TMP_ROOT/book-acceptance-$$"
LOGDIR="$AUDIT_TMP_ROOT/validation-run-$RUN_ID"      # this run's logs, and nothing else
mkdir -p "$LOGDIR" || { echo "Cannot create log directory: $LOGDIR" >&2; exit 2; }
export LOGDIR
COMPOSE_PROJECT_NAME="book-acceptance-$$"
export COMPOSE_PROJECT_NAME
FULL=0; [[ "${1:-}" == "--full" ]] && FULL=1
RESULTS=(); FAILED=0

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
# Only PASS is success. FAIL, PARTIAL and BLOCKED all make the run fail.
rec()  { RESULTS+=("$1|$2|$3"); [[ "$2" != PASS ]] && FAILED=1; printf '   [%s] %s %s\n' "$2" "$1" "${3:+- $3}"; }

# Print a failed check.sh run in full - no truncation, plus mypy's one-line-per-error form.
dump_check() {
  echo "   ---- $1: complete scripts/check.sh output ----"
  sed 's/^/   /' "$2"
  echo "   ---- $1: mypy app --no-pretty ----"
  mypy app --no-pretty --show-error-codes 2>&1 | sed 's/^/   /'
  echo "   ---- $1: ruff format --diff ----"
  ruff format --diff . 2>&1 | sed 's/^/   /'
  echo "   ---------------------------------------------"
}
need() { command -v "$1" >/dev/null || { echo "missing prerequisite: $1"; exit 2; }; }

# Compose scopes "exec" to its own project, and the project name changes between runs,
# so a container left over from an earlier run is invisible to compose yet still holds
# port 5433. Remove our own leftovers, then talk to the endpoint the tests actually use.
free_5433() {
  local ids names
  ids=$(docker ps -aq --filter publish=5433 --filter name=test-db 2>/dev/null)
  if [[ -n "$ids" ]]; then
    names=$(docker ps -a --format '{{.Names}}' --filter publish=5433 --filter name=test-db | tr '\n' ' ')
    docker rm -f $ids >/dev/null 2>&1
    echo "   reclaimed port 5433 from: $names"
  fi
  return 0
}
pg_sql() {
  python3 - "$1" <<'PYSQL' 2>/dev/null
import asyncio, sys, asyncpg
async def main():
    c = await asyncpg.connect("postgresql://test:test@localhost:5433/test")
    print(await c.fetchval(sys.argv[1]))
    await c.close()
asyncio.run(main())
PYSQL
}
wait_pg() { for i in $(seq 1 30); do [[ "$(pg_sql 'select 1')" == "1" ]] && return 0; sleep 1; done; return 1; }

say "0. Preflight"
echo "   run id: $RUN_ID"
echo "   logs:   $LOGDIR"
need python3; need git
PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
if python3 -c 'import sys;sys.exit(0 if sys.version_info[:2]>=(3,12) else 1)'; then
  rec "Python $PYV (book requires 3.12+)" PASS ""
else
  rec "Python $PYV (book requires 3.12+)" FAIL "upgrade Python, or the book's minimum is wrong"
fi
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then DOCKER=1; rec "Docker available" PASS "$(docker --version)"
else DOCKER=0; rec "Docker available" FAIL "needed for the test database"; fi

say "1. Clean checkout of the project as the book builds it"
mkdir -p "$WORK" && cp -r "$HERE/shop-api" "$WORK/shop-api" && cd "$WORK/shop-api"
git init -q . && git config user.email acceptance@test && git config user.name acceptance
# A reader has no migrations/ or alembic.ini until Phase 4a runs alembic init.
# Keep shop-api/'s copies to compare against what Phase 4a generates.
mkdir -p "$WORK/canonical-migrations" && cp -r migrations alembic.ini "$WORK/canonical-migrations/"
rm -rf migrations alembic.ini
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
NFILES=$(find . -type f -not -path './.git/*' | wc -l)
[[ -f app/main.py && -f scripts/check.sh && $NFILES -ge 30 ]] \
  && rec "project tree created" PASS "$NFILES files in $WORK/shop-api" \
  || rec "project tree created" FAIL "only $NFILES files, or app/main.py and scripts/check.sh missing"

say "2. Virtual environment and dependencies (Step 3.2)"
python3 -m venv .venv && source .venv/bin/activate
pip install -q --upgrade pip
if pip install -q fastapi uvicorn "sqlalchemy[asyncio]" asyncpg alembic; then rec "runtime dependencies" PASS ""
else rec "runtime dependencies" FAIL "pip install failed"; fi
pip freeze > requirements.txt
if pip install -q pytest pytest-asyncio httpx ruff mypy respx; then rec "development dependencies" PASS ""
else rec "development dependencies" FAIL "pip install failed"; fi
pip install -q -r requirements-dev.txt && rec "requirements-dev.txt resolves" PASS "" || rec "requirements-dev.txt resolves" FAIL ""
MANIFEST="$LOGDIR/book-versions.txt"
python3 - <<'PYV'
import importlib.metadata as md
import os
import platform

out = [f"python=={platform.python_version()}"]
for p in ["fastapi", "uvicorn", "sqlalchemy", "asyncpg", "alembic", "pydantic", "pytest",
          "pytest-asyncio", "httpx", "ruff", "mypy", "respx", "schemathesis", "mutmut"]:
    try:
        out.append(f"{p}=={md.version(p)}")
    except md.PackageNotFoundError:
        out.append(f"{p}=NOT INSTALLED")
print("   versions:", ", ".join(out))
with open(os.path.join(os.environ["LOGDIR"], "book-versions.txt"), "w") as f:
    f.write("\n".join(out) + "\n")
PYV
RC_MANIFEST=$?
if [[ $RC_MANIFEST -ne 0 ]]; then
  rec "version manifest written" FAIL "the version script exited with $RC_MANIFEST"
elif [[ ! -s "$MANIFEST" ]]; then
  rec "version manifest written" FAIL "$MANIFEST is missing or empty"
elif grep -q "NOT INSTALLED" "$MANIFEST"; then
  rec "version manifest written" FAIL "$(grep 'NOT INSTALLED' "$MANIFEST" | tr '\n' ' ')"
else
  rec "version manifest written" PASS "$(wc -l < "$MANIFEST") packages in $MANIFEST"
fi

say "3. Test database (Step 3.4)"
if [[ $DOCKER == 1 ]]; then
  free_5433
  docker compose -f docker-compose.test.yml up -d >$LOGDIR/compose-up.log 2>&1
  if wait_pg
  then rec "PostgreSQL on 5433" PASS "postgres:16, answering at localhost:5433"
  else rec "PostgreSQL on 5433" FAIL "nothing answering on 5433"
       sed 's/^/   /' $LOGDIR/compose-up.log; fi
else rec "PostgreSQL on 5433" FAIL "Docker unavailable"; fi

say "4. The harness itself (Step 3.7 and 3.8)"
chmod +x scripts/check.sh
cp "$HERE/stages/router_stage1_stub.py" app/routers/orders.py
rm -f tests/api/test_order_cancel.py app/services/orders.py   # back to the Step 3.3 skeleton
if pytest -q tests/test_health.py >$LOGDIR/h.log 2>&1; then rec "first test passes (test_health)" PASS "$(tail -1 $LOGDIR/h.log)"
else rec "first test passes (test_health)" FAIL "$(tail -3 $LOGDIR/h.log | tr '\n' ' ')"; fi
if bash scripts/check.sh >$LOGDIR/c0.log 2>&1; then rec "check.sh passes on the skeleton" PASS ""
else rec "check.sh passes on the skeleton" FAIL "$(grep -vE '^(==>|$)' $LOGDIR/c0.log | tail -2 | tr '\n' ' ')"
     dump_check skeleton $LOGDIR/c0.log; fi
git add -A && git commit -qm "chore: project skeleton with test harness"
git branch -M main                                   # Step 3.11
[[ "$(git rev-parse --abbrev-ref HEAD)" == main ]] \
  && rec "first commit is on main (Step 3.11)" PASS "" \
  || rec "first commit is on main (Step 3.11)" FAIL "branch is $(git rev-parse --abbrev-ref HEAD)"

say "4b. Tool-by-tool diagnostics (so one run tells us everything)"
ruff check . >$LOGDIR/diag-ruff-check.log 2>&1
RC_LINT=$?
ruff format --diff . >$LOGDIR/diag-ruff-format.log 2>&1
RC_FMT=$?
mypy app >$LOGDIR/diag-mypy.log 2>&1
RC_MYPY=$?
pytest -q >$LOGDIR/diag-pytest.log 2>&1
RC_PYTEST=$?
if [[ $RC_LINT == 0 ]]; then rec "ruff check ." PASS "no lint findings"
else rec "ruff check ." FAIL "$(tail -1 $LOGDIR/diag-ruff-check.log)"
     echo "   ---- ruff check output ----"; sed 's/^/   /' $LOGDIR/diag-ruff-check.log | head -30; fi
if [[ $RC_FMT == 0 ]]; then rec "ruff format --check ." PASS "already formatted"
else rec "ruff format --check ." FAIL "$(grep -c '^--- ' $LOGDIR/diag-ruff-format.log) file(s) would be reformatted"
     echo "   ---- ruff format diff ----"; sed 's/^/   /' $LOGDIR/diag-ruff-format.log | head -40; fi
[[ $RC_MYPY == 0 ]] && rec "mypy app" PASS "clean" \
  || rec "mypy app" FAIL "$(tail -1 $LOGDIR/diag-mypy.log)"
[[ $RC_PYTEST == 0 ]] && rec "pytest (skeleton)" PASS "$(tail -1 $LOGDIR/diag-pytest.log)" \
  || rec "pytest (skeleton)" FAIL "$(tail -2 $LOGDIR/diag-pytest.log | tr '\n' ' ')"
echo "   full logs: $LOGDIR/diag-*.log"

say "5. Phase 1 - RED"
git checkout -qb feature/cancel-order
echo red > .tdd-phase
cp "$HERE/stages/test_order_cancel_red.py" tests/api/test_order_cancel.py  # the 7-test spec as Part 5 lists it
pytest -q >$LOGDIR/red.log 2>&1; RC=$?
BEHAVIOURAL=$(grep -cE "assert [0-9]{3} == [0-9]{3}" $LOGDIR/red.log)
WRONGKIND=$(grep -oE "ImportError|ModuleNotFoundError|fixture '[^']+' not found|ConnectionRefused|OperationalError|ProgrammingError|InternalError|AttributeError|NameError|TypeError|RuntimeError|errors? during collection" $LOGDIR/red.log | sort -u | tr '\n' ' ')
SUMMARY=$(grep -E "^[0-9]+ (failed|passed|error)" $LOGDIR/red.log | tail -1)
if [[ $RC -ne 0 && $BEHAVIOURAL -gt 0 && -z "$WRONGKIND" ]]; then
  rec "tests fail for the right reason" PASS "$BEHAVIOURAL behavioural assertion failures - $SUMMARY"
elif [[ -n "$WRONGKIND" ]]; then
  rec "tests fail for the right reason" FAIL "wrong kind of failure: $WRONGKIND| $SUMMARY"
  echo "   ---- pytest output (tail) ----"; sed 's/^/   /' $LOGDIR/red.log | tail -40
else
  rec "tests fail for the right reason" FAIL "rc=$RC, $BEHAVIOURAL behavioural failures | $SUMMARY"
  echo "   ---- pytest output (tail) ----"; sed 's/^/   /' $LOGDIR/red.log | tail -40
fi
[[ "$SUMMARY" == *"7 failed, 1 passed"* ]] \
  && rec "Red output matches the book (7 failed, 1 passed)" PASS "$SUMMARY" \
  || rec "Red output matches the book (7 failed, 1 passed)" FAIL "got: $SUMMARY"
# Red is where failing tests are expected, so the Stop hook must let Claude stop.
P=$PWD
echo "{\"cwd\":\"$P\"}" | python3 .claude/hooks/verify_on_stop.py >/dev/null 2>&1; RC_STOP_RED=$?
if [[ $RC_STOP_RED == 0 && ! -e .tdd-stop-attempts ]]; then
  rec "stop hook allows stopping during red (tests failing)" PASS "exit 0, no counter"
else
  rec "stop hook allows stopping during red (tests failing)" FAIL "exit $RC_STOP_RED, counter=$(cat .tdd-stop-attempts 2>/dev/null || echo none)"
fi
git add tests/api/test_order_cancel.py && git commit -qm "test: cancel order spec"
RED_COMMIT=$(git rev-parse HEAD)
RED_FILES=$(git show --name-only --format= "$RED_COMMIT" | sed '/^$/d' | tr '\n' ' ')
[[ "$RED_FILES" == "tests/api/test_order_cancel.py " ]] \
  && rec "tests committed alone" PASS "${RED_COMMIT:0:12} contains only tests/api/test_order_cancel.py" \
  || rec "tests committed alone" FAIL "${RED_COMMIT:0:12} contains: $RED_FILES"

say "6. Phase 2 - GREEN"
echo green > .tdd-phase
cp "$HERE/stages/router_stage2_green.py" app/routers/orders.py
if bash scripts/check.sh >$LOGDIR/green.log 2>&1; then rec "check.sh exits 0 after implementing" PASS ""
else rec "check.sh exits 0 after implementing" FAIL "$(grep -vE '^(==>|$)' $LOGDIR/green.log | tail -2 | tr '\n' ' ')"
     dump_check green $LOGDIR/green.log; fi
[[ -z "$(git diff $RED_COMMIT -- tests/)" ]] && rec "approved tests unchanged (git diff)" PASS "empty diff" || rec "approved tests unchanged (git diff)" FAIL "tests were modified"
[[ -z "$(git status --short -- tests/)" ]] && rec "no stray test files (git status)" PASS "" || rec "no stray test files (git status)" FAIL "$(git status --short -- tests/ | tr '\n' ' ')"
git add app/ && git commit -qm "feat: cancel order endpoint"
GREEN_FILES=$(git show --name-only --format= HEAD | sed '/^$/d' | tr '\n' ' ')
[[ -n "$GREEN_FILES" && -z "$(git show --name-only --format= HEAD | sed '/^$/d' | grep -v '^app/')" ]] \
  && rec "implementation committed without test changes" PASS "$GREEN_FILES" \
  || rec "implementation committed without test changes" FAIL "commit contains: $GREEN_FILES"

say "7. Phase 3 - REFACTOR"
cp "$HERE/stages/services_orders.py" app/services/orders.py
cp "$HERE/stages/router_stage3_refactor.py" app/routers/orders.py
if bash scripts/check.sh >$LOGDIR/refactor.log 2>&1; then rec "check.sh still exits 0 after refactor" PASS "behaviour unchanged"
else rec "check.sh still exits 0 after refactor" FAIL "$(grep -vE '^(==>|$)' $LOGDIR/refactor.log | tail -2 | tr '\n' ' ')"
     dump_check refactor $LOGDIR/refactor.log; fi
[[ -z "$(git diff $RED_COMMIT -- tests/)" ]] && rec "tests still untouched" PASS "" || rec "tests still untouched" FAIL ""
git add app/ && git commit -qm "refactor: move cancel rules into service"
ORDER=$(git log --format=%s | head -4 | tr '\n' '|')
if [[ "$ORDER" == "refactor: move cancel rules into service|feat: cancel order endpoint|test: cancel order spec|chore: project skeleton with test harness|" ]]
then rec "commit history" PASS "$(git log --oneline | head -4 | tr '\n' ' | ')"
else rec "commit history" FAIL "unexpected order: $ORDER"; fi
if git diff --stat main...HEAD >$LOGDIR/diff-main.log 2>&1 && [[ -s $LOGDIR/diff-main.log ]]; then
  rec "git diff main...HEAD works (Phase 5 review)" PASS "$(tail -1 $LOGDIR/diff-main.log)"
else
  rec "git diff main...HEAD works (Phase 5 review)" FAIL "$(tail -1 $LOGDIR/diff-main.log)"
fi

say "8. Guardrails (Part 4)"
echo green > .tdd-phase
P=$PWD
printf '{"cwd":"%s","tool_input":{"file_path":"%s/tests/api/test_order_cancel.py"}}' "$P" "$P" | python3 .claude/hooks/lock_tests.py >/dev/null 2>&1
[[ $? == 2 ]] && rec "lock hook blocks a test edit during green" PASS "exit 2" || rec "lock hook blocks a test edit during green" FAIL ""
printf '{"cwd":"%s","tool_input":{"file_path":"%s/app/main.py"}}' "$P" "$P" | python3 .claude/hooks/lock_tests.py >/dev/null 2>&1
[[ $? == 0 ]] && rec "lock hook allows an app edit during green" PASS "exit 0" || rec "lock hook allows an app edit during green" FAIL ""
echo red > .tdd-phase
printf '{"cwd":"%s","tool_input":{"file_path":"%s/tests/api/test_order_cancel.py"}}' "$P" "$P" | python3 .claude/hooks/lock_tests.py >/dev/null 2>&1
[[ $? == 0 ]] && rec "lock hook allows a test edit during red" PASS "exit 0" || rec "lock hook allows a test edit during red" FAIL ""
echo green > .tdd-phase
echo "{\"cwd\":\"$P\"}" | python3 .claude/hooks/verify_on_stop.py >/dev/null 2>&1
[[ $? == 0 ]] && rec "stop hook allows stopping when checks pass" PASS "exit 0" || rec "stop hook allows stopping when checks pass" FAIL ""
mv scripts/check.sh "$WORK/real_check.sh"; printf '#!/usr/bin/env bash\nexit 1\n' > scripts/check.sh
echo "{\"cwd\":\"$P\"}" | python3 .claude/hooks/verify_on_stop.py >/dev/null 2>&1
[[ $? == 2 ]] && rec "stop hook blocks stopping when checks fail" PASS "exit 2, counter=$(cat .tdd-stop-attempts)" || rec "stop hook blocks stopping when checks fail" FAIL ""
SEQ="2"
for i in 2 3 4 5 6; do echo "{\"cwd\":\"$P\"}" | python3 .claude/hooks/verify_on_stop.py >/dev/null 2>&1; SEQ="$SEQ $?"; done
[[ "$SEQ" == "2 2 2 2 2 1" && ! -e .tdd-stop-attempts ]] \
  && rec "stop hook gives up after 5 attempts" PASS "exit codes: $SEQ; counter removed" \
  || rec "stop hook gives up after 5 attempts" FAIL "exit codes: $SEQ"
rm -f .tdd-phase
echo "{\"cwd\":\"$P\"}" | python3 .claude/hooks/verify_on_stop.py >/dev/null 2>&1
[[ $? == 0 ]] && rec "stop hook is inactive with no marker" PASS "exit 0 even though checks fail" || rec "stop hook is inactive with no marker" FAIL ""
mv "$WORK/real_check.sh" scripts/check.sh; rm -f .tdd-stop-attempts .tdd-phase

say "9. Phase 4a - migrations"
if [[ $DOCKER == 1 ]]; then
  # One-time setup, exactly as Phase 4a describes it.
  alembic init -t async migrations >$LOGDIR/alembic-init.log 2>&1
  python3 - <<'PATCH'
# the three edits Phase 4a tells you to make to the generated migrations/env.py
p = 'migrations/env.py'; s = open(p).read()
if 'app.db.base' not in s:
    tmpl = ('import asyncio\nfrom logging.config import fileConfig\n\n'
            'from sqlalchemy import pool\nfrom sqlalchemy.engine import Connection\n'
            'from sqlalchemy.ext.asyncio import async_engine_from_config\n\n'
            'from alembic import context\n')
    want = ('import asyncio\nimport os\nfrom logging.config import fileConfig\n\n'
            'from alembic import context\nfrom sqlalchemy import pool\n'
            'from sqlalchemy.engine import Connection\n'
            'from sqlalchemy.ext.asyncio import async_engine_from_config\n\n'
            'import app.models  # noqa: F401\nfrom app.db.base import Base\n')
    assert tmpl in s, 'alembic template import block not as expected - update validate.sh'
    s = s.replace(tmpl, want, 1)
    # directly below `config = context.config`, as Phase 4a instructs
    s = s.replace('config = context.config',
                  'config = context.config\n\nconfig.set_main_option(\n    "sqlalchemy.url",\n'
                  '    os.environ.get(\n        "DATABASE_URL",\n'
                  '        "postgresql+asyncpg://test:test@localhost:5433/test",\n    ),\n)', 1)
    s = s.replace('target_metadata = None', 'target_metadata = Base.metadata', 1)
    open(p, 'w').write(s)
PATCH
  RC_PATCH=$?
  if [[ $RC_PATCH == 0 ]] && cmp -s migrations/env.py "$WORK/canonical-migrations/migrations/env.py"; then
    rec "env.py after the documented edits matches shop-api/" PASS ""
  else
    rec "env.py after the documented edits matches shop-api/" FAIL "patch rc=$RC_PATCH"
    diff "$WORK/canonical-migrations/migrations/env.py" migrations/env.py | sed 's/^/   /' | head -30
  fi
  export DATABASE_URL="postgresql+asyncpg://test:test@localhost:5433/test"
  # Phase 4a: autogenerate diffs the models against the live database. The test runs above
  # already built the tables with create_all, so restart the database first, as the book says.
  docker compose -f docker-compose.test.yml down --remove-orphans >/dev/null 2>&1 || true
  free_5433
  docker compose -f docker-compose.test.yml up -d >$LOGDIR/compose-up2.log 2>&1
  DB_READY=0; wait_pg && DB_READY=1
  EMPTY=$(pg_sql "select to_regclass('public.orders') is null and to_regclass('public.alembic_version') is null")
  if [[ "$DB_READY" == 1 && "$EMPTY" == "True" ]]; then
    rec "migration database starts empty" PASS "fresh container; orders and alembic_version both absent"
  else
    rec "migration database starts empty" FAIL "reachable=$DB_READY, empty=${EMPTY:-unknown}"
    sed 's/^/   /' $LOGDIR/compose-up2.log
  fi
  # The initial migration.
  if alembic revision --autogenerate -m "create orders table" >$LOGDIR/m1.log 2>&1; then
    REV=$(ls -t migrations/versions/*.py 2>/dev/null | head -1)
    if [[ -n "$REV" && -f "$REV" ]] \
      && grep -Eq "op\\.create_table\\([[:space:]]*['\"]orders['\"]" "$REV" \
      && grep -Eq "op\\.drop_table\\([[:space:]]*['\"]orders['\"]" "$REV"; then
      rec "autogenerate the initial migration" PASS "$(basename "$REV") creates the orders table"
    else
      rec "autogenerate the initial migration" FAIL "migration is empty - no create_table(\"orders\") in $(basename "${REV:-none}")"
      echo "   ---- generated migration ----"; sed 's/^/   /' "${REV:-/dev/null}"
    fi
    CANON_REV=$(ls "$WORK"/canonical-migrations/migrations/versions/*.py 2>/dev/null | head -1)
    if [[ -n "$CANON_REV" ]] && diff <(sed -n '/^def upgrade/,$p' "$REV") <(sed -n '/^def upgrade/,$p' "$CANON_REV") >/dev/null; then
      rec "generated migration matches shop-api/'s" PASS "upgrade() and downgrade() identical"
    else
      rec "generated migration matches shop-api/'s" FAIL "compare $REV with $CANON_REV"
    fi
  else rec "autogenerate the initial migration" FAIL "$(tail -2 $LOGDIR/m1.log | tr '\n' ' ')"; fi
  if alembic upgrade head >$LOGDIR/m2.log 2>&1 && alembic downgrade -1 >>$LOGDIR/m2.log 2>&1 && alembic upgrade head >>$LOGDIR/m2.log 2>&1
  then
    EXISTS=$(pg_sql "select to_regclass('public.orders') is not null")
    [[ "$EXISTS" == "True" ]] \
      && rec "upgrade / downgrade / upgrade round-trip" PASS "orders table present after upgrade" \
      || rec "upgrade / downgrade / upgrade round-trip" FAIL "commands succeeded but the orders table is absent"
  else rec "upgrade / downgrade / upgrade round-trip" FAIL "$(tail -2 $LOGDIR/m2.log | tr '\n' ' ')"; fi
  # Phase 4a's warning: autogenerate against an up-to-date database writes an empty migration.
  if alembic revision --autogenerate -m "no model change" >$LOGDIR/m3.log 2>&1; then
    NOOP=$(ls -t migrations/versions/*no_model_change*.py 2>/dev/null | head -1)
    if [[ -n "$NOOP" ]] && ! grep -q "op\." "$NOOP" && sed -n '/^def upgrade/,/^def downgrade/p' "$NOOP" | grep -q '^    pass'; then
      rec "autogenerate with no model change is empty (Phase 4a warning)" PASS "upgrade() is just pass; file removed"
    else
      rec "autogenerate with no model change is empty (Phase 4a warning)" FAIL "$(basename "${NOOP:-none}") is not empty"
    fi
    rm -f "$NOOP"
  else rec "autogenerate with no model change is empty (Phase 4a warning)" FAIL "$(tail -2 $LOGDIR/m3.log | tr '\n' ' ')"; fi
else rec "migrations" BLOCKED "Docker unavailable"; fi

if [[ $FULL == 1 ]]; then
  say "10. Phase 4b-d and Part 8 (full run)"
  # Phase 4b's own fixes: documented error responses, and a bounded order_id; Phase 4d's test fixes.
  cp "$HERE/shop-api/app/routers/orders.py" app/routers/orders.py
  cp "$HERE/shop-api/tests/api/test_order_cancel.py" tests/api/
  if pytest -q tests/api/test_order_cancel.py::test_cancel_order_with_oversized_id_returns_422 >$LOGDIR/p4b.log 2>&1
  then rec "Phase 4b fix: out-of-range id rejected" PASS "$(tail -1 $LOGDIR/p4b.log)"
  else rec "Phase 4b fix: out-of-range id rejected" FAIL "$(tail -3 $LOGDIR/p4b.log | tr '\n' ' ')"; fi
  # The final project, checked as a whole: every tool, then the check script itself.
  ruff check . >$LOGDIR/final-ruff-check.log 2>&1 && rec "final: ruff check ." PASS "" \
    || { rec "final: ruff check ." FAIL "$(tail -1 $LOGDIR/final-ruff-check.log)"; sed 's/^/   /' $LOGDIR/final-ruff-check.log | head -30; }
  ruff format --check . >$LOGDIR/final-ruff-format.log 2>&1 && rec "final: ruff format --check ." PASS "$(tail -1 $LOGDIR/final-ruff-format.log)" \
    || { rec "final: ruff format --check ." FAIL "$(tail -1 $LOGDIR/final-ruff-format.log)"; ruff format --diff . 2>&1 | sed 's/^/   /' | head -40; }
  mypy app >$LOGDIR/final-mypy.log 2>&1 && rec "final: mypy app" PASS "$(tail -1 $LOGDIR/final-mypy.log)" \
    || { rec "final: mypy app" FAIL "$(tail -1 $LOGDIR/final-mypy.log)"; sed 's/^/   /' $LOGDIR/final-mypy.log | head -30; }
  pytest -q >$LOGDIR/final-pytest.log 2>&1 && rec "final: pytest -q" PASS "$(tail -1 $LOGDIR/final-pytest.log)" \
    || { rec "final: pytest -q" FAIL "$(tail -1 $LOGDIR/final-pytest.log)"; tail -40 $LOGDIR/final-pytest.log | sed 's/^/   /'; }
  if bash scripts/check.sh >$LOGDIR/final-check.log 2>&1; then rec "final: bash scripts/check.sh" PASS "$(tail -1 $LOGDIR/final-check.log)"
  else rec "final: bash scripts/check.sh" FAIL "$(grep -vE '^(==>|$)' $LOGDIR/final-check.log | tail -2 | tr '\n' ' ')"
       dump_check final $LOGDIR/final-check.log; fi
  # The rebuilt project must be shop-api/: same source files, nothing extra, nothing missing.
  TREEDIFF=$(diff -rq "$HERE/shop-api" . \
      -x .git -x .venv -x __pycache__ -x .mypy_cache -x .ruff_cache -x .pytest_cache \
      -x requirements.txt -x versions 2>&1)
  [[ -z "$TREEDIFF" ]] && rec "final project matches shop-api/" PASS "" \
    || { rec "final project matches shop-api/" FAIL "$(echo "$TREEDIFF" | head -3 | tr '\n' ' ')"; echo "$TREEDIFF" | sed 's/^/   /'; }
  uvicorn app.main:app --port 8000 >$LOGDIR/uv.log 2>&1 & UVPID=$!; sleep 4
  curl -fsS "http://localhost:8000/health" >$LOGDIR/health.json 2>/dev/null \
    && rec "smoke test: /health" PASS "$(cat $LOGDIR/health.json)" || rec "smoke test: /health" FAIL ""
  pip install -q schemathesis
  # (a) Unpinned: Schemathesis keeps exploring the id space. This is the run that
  #     surfaced the 2**63 crash, so the config file is moved aside for it.
  mv schemathesis.toml "$WORK/st-config-$$.toml" 2>/dev/null
  st run http://localhost:8000/openapi.json --header "X-User-Id: 1" >$LOGDIR/st.log 2>&1; RC_ST=$?
  ST_COUNT=$(grep -m1 -E '[0-9]+ generated' $LOGDIR/st.log | tr -s ' ')
  if [[ $RC_ST == 0 ]]; then
    ST_NOTE=""; grep -q "Missing test data" $LOGDIR/st.log && ST_NOTE=" (with the expected 'Missing test data' warning)"
    rec "Schemathesis (unpinned)" PASS "no contract violations; $ST_COUNT$ST_NOTE"
  else
    rec "Schemathesis (unpinned)" FAIL "$(grep -m1 -E '^[0-9]+ (failure|error)' $LOGDIR/st.log || tail -1 $LOGDIR/st.log)"
    echo "   ---- schemathesis output ----"; sed 's/^/   /' $LOGDIR/st.log
  fi
  # (b) Seeded and pinned: an empty database answers every generated request with 404,
  #     so a clean run proves nothing until the cancellation rules have actually run.
  pg_sql "insert into orders (id, owner_id, status) values (1, 1, 'pending')
          on conflict (id) do update set owner_id = 1, status = 'pending' returning id" >/dev/null
  mv "$WORK/st-config-$$.toml" schemathesis.toml 2>/dev/null
  BEFORE_200=$(grep -cE '"POST /orders/1/cancel HTTP/1.1" 200' $LOGDIR/uv.log)
  st run http://localhost:8000/openapi.json --header "X-User-Id: 1" >$LOGDIR/st2.log 2>&1; RC_ST2=$?
  AFTER_200=$(grep -cE '"POST /orders/1/cancel HTTP/1.1" 200' $LOGDIR/uv.log)
  if grep -q "Missing test data" $LOGDIR/st2.log; then
    rec "Schemathesis reaches the business logic" FAIL "every request still answered 404 - the cancel rules never ran"
    echo "   ---- schemathesis output ----"; sed 's/^/   /' $LOGDIR/st2.log
  elif [[ $RC_ST2 == 0 && $((AFTER_200 - BEFORE_200)) -gt 0 ]]; then
    rec "Schemathesis reaches the business logic" PASS "$(grep -m1 -E '[0-9]+ generated' $LOGDIR/st2.log | tr -s ' '); $((AFTER_200 - BEFORE_200)) requests cancelled order 1 (200)"
  else
    rec "Schemathesis reaches the business logic" FAIL "rc=$RC_ST2, 200 responses on order 1: $((AFTER_200 - BEFORE_200)); $(grep -m1 -E '^[0-9]+ (failure|error)' $LOGDIR/st2.log || tail -1 $LOGDIR/st2.log)"
    echo "   ---- schemathesis output ----"; sed 's/^/   /' $LOGDIR/st2.log
  fi
  kill $UVPID 2>/dev/null
  if pip install -q mutmut; then
    if timeout 900 mutmut run >$LOGDIR/mut.log 2>&1; then MRC=0; else MRC=$?; fi
    # mutmut draws a spinner with carriage returns; the last counter is "done/total".
    MUT_PROGRESS=$(tr '\r' '\n' < $LOGDIR/mut.log | grep -oE '[0-9]+/[0-9]+' | tail -1 || true)
    if [[ $MRC == 124 ]]; then
      rec "mutmut run" FAIL "timed out after 900 seconds"
      tail -25 $LOGDIR/mut.log | sed 's/^/   /'
    elif [[ $MRC != 0 ]]; then
      rec "mutmut run" FAIL "mutmut exited with code $MRC"
      tail -25 $LOGDIR/mut.log | sed 's/^/   /'
    elif ! mutmut results --all true >$LOGDIR/mut-results-all.log 2>&1; then
      rec "mutmut run" FAIL "could not read the mutation results"
    else
      # One line per mutant, "name: status". Count from the results, not the spinner.
      TOTAL=$(grep -cE ': [a-z ]+$' $LOGDIR/mut-results-all.log)
      KILLED=$(grep -cE ': killed$' $LOGDIR/mut-results-all.log)
      SURVIVED=$(grep -cE ': survived$' $LOGDIR/mut-results-all.log)
      TIMEOUT=$(grep -cE ': timeout$' $LOGDIR/mut-results-all.log)
      UNCHECKED=$(grep -cE ': not checked$' $LOGDIR/mut-results-all.log)
      OTHER=$((TOTAL - KILLED - SURVIVED - TIMEOUT - UNCHECKED))
      COUNTS="$TOTAL mutants: $KILLED killed, $SURVIVED survived, $TIMEOUT timeout, $UNCHECKED not checked, $OTHER other; progress $MUT_PROGRESS"
      if [[ $TOTAL -gt 0 && $KILLED == "$TOTAL" && "$MUT_PROGRESS" == "$TOTAL/$TOTAL" ]]; then
        rec "mutmut run" PASS "$COUNTS"
      elif [[ $TOTAL == 0 ]]; then
        rec "mutmut run" FAIL "no mutants were generated; $COUNTS"
      else
        rec "mutmut run" FAIL "$COUNTS"
        grep -vE ': killed$' $LOGDIR/mut-results-all.log | sed 's/^/   /'
      fi
    fi
  else
    rec "mutmut run" FAIL "pip install mutmut failed"
  fi
  if [[ $DOCKER == 1 ]]; then
    # Every .dockerignore entry must be present in the build context, or the check proves
    # nothing. Create harmless placeholders for the ones that do not exist yet.
    CREATED=()
    mk_dummy() {  # path, kind (file|dir)
      if [[ ! -e "$1" ]]; then
        if [[ $2 == dir ]]; then mkdir -p "$1" && echo "placeholder" > "$1/placeholder.txt"
        else mkdir -p "$(dirname "$1")" && echo "PLACEHOLDER=not-a-real-secret" > "$1"; fi
        CREATED+=("$1")
      fi
    }
    mk_dummy .env file; mk_dummy .tdd-phase file; mk_dummy .tdd-stop-attempts file
    mk_dummy CLAUDE.local.md file; mk_dummy .claude/settings.local.json file
    mk_dummy mutants dir; mk_dummy .mypy_cache dir; mk_dummy .ruff_cache dir; mk_dummy .pytest_cache dir
    mk_dummy app/__pycache__ dir
    IGNORED=(.git .venv .env .tdd-phase .tdd-stop-attempts CLAUDE.local.md .claude/settings.local.json
             mutants .mypy_cache .ruff_cache .pytest_cache app/__pycache__)
    PRESENT=0; for p in "${IGNORED[@]}"; do [[ -e "$p" ]] && PRESENT=$((PRESENT + 1)); done
    docker build -t shop-api . >$LOGDIR/build.log 2>&1 && rec "docker build" PASS "" || rec "docker build" FAIL "$(tail -3 $LOGDIR/build.log | tr '\n' ' ')"
    # Look inside the image itself, not a running container.
    IMG_LISTING=$(docker run --rm --entrypoint sh shop-api -c 'cd /app && find . -maxdepth 3' 2>/dev/null)
    if [[ -z "$IMG_LISTING" ]] || ! grep -qx './app/main.py' <<< "$IMG_LISTING"; then
      rec ".dockerignore keeps excluded paths out of the image" FAIL "could not list /app in the image"
    else
      LEAKED=""
      for p in "${IGNORED[@]}"; do
        grep -qx "./$p" <<< "$IMG_LISTING" && LEAKED="$LEAKED $p"
      done
      grep -qE '/(__pycache__|\.mypy_cache|\.ruff_cache|\.pytest_cache)$' <<< "$IMG_LISTING" && LEAKED="$LEAKED (a cache directory below the root)"
      if [[ -n "$LEAKED" ]]; then
        rec ".dockerignore keeps excluded paths out of the image" FAIL "leaked into the image:$LEAKED"
      elif [[ $PRESENT != ${#IGNORED[@]} ]]; then
        rec ".dockerignore keeps excluded paths out of the image" PARTIAL "only $PRESENT of ${#IGNORED[@]} paths were in the build context"
      else
        rec ".dockerignore keeps excluded paths out of the image" PASS "all ${#IGNORED[@]} paths were in the build context (${#CREATED[@]} as placeholders); none are in /app"
      fi
    fi
    for p in "${CREATED[@]}"; do rm -rf "$p"; done
    docker run --rm -d --name shop-api-acc -p 8001:8000 \
      --add-host=host.docker.internal:host-gateway \
      -e DATABASE_URL="postgresql+asyncpg://test:test@host.docker.internal:5433/test" \
      shop-api >/dev/null 2>&1
    for i in $(seq 1 15); do curl -fsS http://localhost:8001/health >$LOGDIR/h2.json 2>/dev/null && break; sleep 1; done
    if [[ -s $LOGDIR/h2.json ]]; then rec "container serves /health" PASS "$(cat $LOGDIR/h2.json)"
    else rec "container serves /health" FAIL "no response on 8001"
         echo "   ---- docker logs ----"; docker logs shop-api-acc 2>&1 | tail -20 | sed 's/^/   /'; fi
    docker rm -f shop-api-acc >/dev/null 2>&1
  else
    rec "docker build" BLOCKED "Docker unavailable"
  fi
fi

say "RESULT"
printf '%-58s %s\n' "CHECK" "STATUS"
printf '%s\n' "----------------------------------------------------------------------"
NPASS=0; NFAIL=0; NPART=0; NBLOCK=0
for r in "${RESULTS[@]}"; do
  IFS='|' read -r n s d <<< "$r"; printf '%-58s %s\n' "$n" "$s"
  case "$s" in PASS) NPASS=$((NPASS + 1)) ;; FAIL) NFAIL=$((NFAIL + 1)) ;;
               PARTIAL) NPART=$((NPART + 1)) ;; *) NBLOCK=$((NBLOCK + 1)) ;; esac
done
echo
[[ $DOCKER == 1 ]] && docker compose -f docker-compose.test.yml down >/dev/null 2>&1
SUMMARY_LINE="${#RESULTS[@]} checks: $NPASS PASS, $NFAIL FAIL, $NPART PARTIAL, $NBLOCK BLOCKED"
echo "$SUMMARY_LINE"
cp "$MANIFEST" "$LOGDIR/../book-versions-$RUN_ID.txt" 2>/dev/null
if [[ $FAILED == 0 ]]; then echo "ALL CHECKS PASSED - the documented workflow works end to end."; else
  echo "NOT ALL CHECKS PASSED - see the log lines above; the project is left in $WORK/shop-api"; fi
echo "project kept at: $WORK/shop-api"
echo "logs kept at:    $LOGDIR"
exit $FAILED
