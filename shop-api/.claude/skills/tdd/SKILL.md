---
name: tdd
description: Implement a backend feature test-first (endpoint, service or bug fix).
disable-model-invocation: true
---

Implement the requested feature using strict test-driven development.

1. PLAN
   Turn the request into numbered behaviours and test cases.
   Show them to me and wait for my approval before editing files.

2. RED
   Run `echo red > .tdd-phase`.
   Use the test-writer subagent to write tests from the approved specification.
   Run the tests and confirm each fails for the expected behavioural reason.
   Commit only the test files.
   Record this commit as the latest approved Red-phase reference.

3. GREEN
   Run `echo green > .tdd-phase`.
   Implement the minimum application code needed to make the tests pass.
   Never edit anything under tests/.
   Run `bash scripts/check.sh` after meaningful changes.
   Continue until the checks pass.

4. REFACTOR
   Improve the structure, readability and separation of concerns.
   Keep the tests locked.
   Behaviour must not change, and the checks must remain green.

5. ADDITIONAL VERIFICATION
   If models or the database schema changed, generate and inspect
   the migration. Verify the upgrade / downgrade / upgrade round-trip
   against the test database.

   Apply the relevant additional verification from Part 5, Phase 4:
   Schemathesis, smoke tests and mutation testing where appropriate.

6. INDEPENDENT REVIEW
   Use the reviewer subagent to inspect `git diff main...HEAD`.
   Alternatively, use Claude Code's `/code-review` command.

   Read the findings and fix genuine problems.
   If a finding reveals missing behaviour, return to RED:
   add a failing test, confirm the failure, commit the approved
   test change, and then return to GREEN.

   Do not silently change tests during GREEN.

7. FINAL VERIFICATION AND CLEANUP
   Run `bash scripts/check.sh` and confirm it exits with 0.

   Compare the current tests against the latest approved Red-phase commit:

   `git diff <latest-red-commit> -- tests/`

   `git status --short -- tests/`

   Investigate any unexplained test changes before proceeding.

   Once verification is complete, run:

   `rm -f .tdd-phase .tdd-stop-attempts`

   Summarise the tests added, files changed, verification results,
   and anything deliberately left untested.
