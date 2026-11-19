import json
import os
import pathlib
import sys

# 1. Read the JSON supplied by Claude Code through stdin.
data = json.load(sys.stdin)

# 2. Extract the arguments supplied to the tool.
tool_input = data.get("tool_input", {})

# 3. Extract the path of the file Claude wants to modify.
path = tool_input.get("file_path", "")

# 4. Get the project root directory.
project_dir = os.environ.get(
    "CLAUDE_PROJECT_DIR",
    data.get("cwd", "."),
)

# 5. Locate the .tdd-phase marker file.
phase_file = pathlib.Path(project_dir) / ".tdd-phase"

# 6. Read the current TDD phase.
phase = phase_file.read_text().strip() if phase_file.exists() else ""

# 7. Check whether the target file is inside a tests directory.
is_test_file = "tests" in pathlib.Path(path).parts

# 8. Block test modifications during the Green phase.
if phase == "green" and is_test_file:
    print(
        "Green phase: tests are locked. Fix the implementation. "
        "If the test itself is wrong, stop and explain why.",
        file=sys.stderr,
    )
    sys.exit(2)

# 9. Otherwise, allow the proposed tool call.
sys.exit(0)
