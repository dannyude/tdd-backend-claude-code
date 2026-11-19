#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys

# Maximum number of times Claude can be sent back
MAX_ATTEMPTS = 5

# Read the JSON supplied by Claude Code through stdin.
data = json.load(sys.stdin)

# Locate the project root.
project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd", ".")
root = pathlib.Path(project_dir)

# Locate the attempt counter.
counter = root / ".tdd-stop-attempts"

# Read the current TDD phase from the marker file.
phase_file = root / ".tdd-phase"
phase = phase_file.read_text().strip() if phase_file.exists() else ""

# Only enforce verification during the Green phase.
# In Red, failing tests are expected; with no marker, we're not doing TDD.
# Either way, remove any stale counter and allow Claude to stop.
if phase != "green":
    counter.unlink(missing_ok=True)
    sys.exit(0)

# Run the project's verification script.
result = subprocess.run(
    ["bash", "scripts/check.sh"],
    cwd=root,
    capture_output=True,
    text=True,
)

# If all checks pass, reset the counter and allow Claude to stop.
if result.returncode == 0:
    counter.unlink(missing_ok=True)
    sys.exit(0)

# Read the number of previous failed verification attempts.
attempts = int(counter.read_text()) if counter.exists() else 0

# If the retry limit has been reached, allow Claude to stop.
if attempts >= MAX_ATTEMPTS:
    counter.unlink(missing_ok=True)
    print(
        f"Checks still failing after {MAX_ATTEMPTS} attempts.",
        "Stopping for a human to review.",
        file=sys.stderr,
    )
    sys.exit(1)  # Non-blocking: Claude may stop.

# Record this failed attempt.
counter.write_text(str(attempts + 1))

# Capture the last 4,000 characters of the check output.
output = (result.stdout + result.stderr)[-4000:]

print(
    f"Not done — checks failing (attempt {attempts + 1} of {MAX_ATTEMPTS}):",
    file=sys.stderr,
)
print(output, file=sys.stderr)

sys.exit(2)  # Block the stop and send the failure output back to Claude.
