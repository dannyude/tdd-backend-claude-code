# Test-Driven Backend Development with Claude Code

**From first test to CI/CD** · Python · FastAPI · SQLAlchemy · PostgreSQL

The companion repository for the book by **Daniel Ude**. The book teaches one complete, repeatable way to build backend features with Claude Code, so that Claude proves its own work with tests before anything is called done. That proof is then carried all the way to GitHub, where every change is checked automatically and shipped when it passes.

This repository holds the book itself, the finished project you build while reading it, the intermediate versions of the code at each Red → Green → Refactor step, and the acceptance test that runs the book's whole workflow end to end.

📖 **[Read the book (PDF)](book/Test-Driven-Backend-Development-with-Claude-Code.pdf)** · 🧭 **[How to use this book](docs/GUIDE.md)** · ✅ **[Verify it yourself](docs/VERIFY.md)**

---

## What you will build

A small FastAPI + async SQLAlchemy + PostgreSQL service called **shop-api**, and one feature built end to end: **cancelling an order**. Around it you set up everything that makes Claude Code work test-first:

- **A real test harness:** PostgreSQL in Docker, transaction-isolated pytest fixtures, and one script, `scripts/check.sh`, that is the single definition of "done" (Ruff, Ruff format, mypy, pytest).
- **Guardrails:** two Claude Code hooks. One locks the tests while Claude implements. The other won't let Claude finish while the checks fail.
- **The feature loop:** Spec → Red → Green → Refactor → Verify → Review, with migration round-trips, Schemathesis contract fuzzing, a smoke test and mutation testing.
- **Subagents and a `/tdd` skill:** a separate test writer and an independent reviewer, and the whole loop packaged into one command.
- **CI/CD:** a GitHub Actions workflow that runs the same checks on every push, plus a Docker image and a deploy job.

## What is in this repository

| Path | What it is |
|---|---|
| [`book/`](book/) | The book, as a PDF |
| [`shop-api/`](shop-api/) | The finished project, exactly as the book's listings and commands produce it (Appendix C) |
| [`stages/`](stages/) | The code at each step of the feature loop, so you can compare your work or replay the cycle ([map](stages/README.md)) |
| [`validate.sh`](validate.sh) | The acceptance test: rebuilds the project from a clean checkout and runs every step of the workflow |
| [`docs/GUIDE.md`](docs/GUIDE.md) | How to use the book: reading paths, a part-by-part map, and how to follow along with this repository |
| [`docs/VERIFY.md`](docs/VERIFY.md) | How to run the acceptance test, and the manual check for the Claude Code hooks |

## Quick start: run the finished project

You need **Linux** (or WSL on Windows), **Python 3.12+**, **Docker** and **Git**, plus Claude Code for the parts that use it (installation: Part 2 of the book).

```bash
git clone https://github.com/dannyude/tdd-backend-claude-code.git
cd tdd-backend-claude-code/shop-api

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

docker compose -f docker-compose.test.yml up -d   # PostgreSQL for the tests, on port 5433
bash scripts/check.sh                             # ends with "All checks passed."
```

Then open Claude Code in the same folder (`claude`) and run `/hooks`: you should see the two guardrail hooks the book builds in Part 4.

When you are done: `docker compose -f docker-compose.test.yml down`.

> The quick start runs the *finished* project. To learn the workflow, build it yourself by following the book, and use this repository to check your work. [docs/GUIDE.md](docs/GUIDE.md) explains how.

## How this book was checked

Every listing in the book was compared with the files in this repository, and `validate.sh --full` ran the whole documented workflow on Python 3.12 and 3.14: **54 of 54 checks passed** on each. That covers setup, Red → Green → Refactor and the hooks, migrations, Schemathesis, mutation testing, the Docker image and its `.dockerignore`. The hooks were also checked live in a real Claude Code session: they loaded, blocked a test edit during Green, and refused to let Claude finish while the checks failed.

Tested with Python 3.12 and 3.14 · Docker 29.9.3 · postgres:16 · FastAPI 0.165.0 · SQLAlchemy 2.1.9 · Pydantic 2.14.4 · pytest 9.2.0 · pytest-asyncio 1.5.0 · Ruff 0.17.5 · mypy 2.4.1 · Alembic 1.20.1 · Schemathesis 4.33.4 · mutmut 3.8.1.

## Questions, corrections and feedback

- **Questions about the book:** email me at **[danielude98@gmail.com](mailto:danielude98@gmail.com)**.
- **Found a mistake?** Please [open an issue](../../issues) with the page number and what you expected. A failing command with its full output is the most useful thing you can send.

## License

- **The code** (everything except `book/`) is released under the [MIT License](LICENSE). Use it freely in your own projects.
- **The book** (`book/`) is © 2026 Daniel Ude, all rights reserved. You may read it and share the link to this repository, but please don't republish or sell it.
