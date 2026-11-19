# The feature loop, stage by stage

Part 5 of the book changes the same few files from phase to phase. These are the versions at each step, exactly as the book lists them, so you can compare your own work or replay the Red → Green → Refactor sequence.

| File | Book section | Goes to | What it is |
|---|---|---|---|
| [`router_stage1_stub.py`](router_stage1_stub.py) | Step 3.3 | `app/routers/orders.py` | The empty router: no endpoints yet |
| [`test_order_cancel_red.py`](test_order_cancel_red.py) | Part 5, Phase 1 (Red) | `tests/api/test_order_cancel.py` | The seven approved tests. Against the stub they give **7 failed, 1 passed** (the one pass is `test_health`) |
| [`router_stage2_green.py`](router_stage2_green.py) | Phase 2 (Green), Step 4 | `app/routers/orders.py` | The first implementation, with every rule inside the endpoint |
| [`services_orders.py`](services_orders.py) | Phase 3 (Refactor) | `app/services/orders.py` | The cancellation rules moved into a service |
| [`router_stage3_refactor.py`](router_stage3_refactor.py) | Phase 3 (Refactor) | `app/routers/orders.py` | The thin router that calls the service |

After Phase 3 the book continues in place: Phase 4b adds the documented error responses and the `order_id` bounds to the router, and Phase 4b and 4d add or strengthen tests. Those final versions are the ones in [`../shop-api/`](../shop-api/).

## Replaying the cycle

Work in a copy, never in this repository. From the copied project's root, with the test database running:

```bash
REPO=~/tdd-backend-claude-code    # wherever you cloned this repository

# Part 3 state
cp "$REPO/stages/router_stage1_stub.py" app/routers/orders.py
rm -f app/services/orders.py tests/api/test_order_cancel.py

# Phase 1 - Red: 7 failed, 1 passed
echo red > .tdd-phase
cp "$REPO/stages/test_order_cancel_red.py" tests/api/test_order_cancel.py
pytest -q

# Phase 2 - Green: check.sh exits 0
echo green > .tdd-phase
cp "$REPO/stages/router_stage2_green.py" app/routers/orders.py
bash scripts/check.sh

# Phase 3 - Refactor: still exits 0, tests untouched
cp "$REPO/stages/services_orders.py" app/services/orders.py
cp "$REPO/stages/router_stage3_refactor.py" app/routers/orders.py
bash scripts/check.sh

rm -f .tdd-phase .tdd-stop-attempts
```

`validate.sh` runs this same sequence, with commits between the phases and the Git checks the book teaches.
