---
goal: Establish the contract every simulation recipe in this folder follows, so an AI agent can chain simulations deterministically and an operator can audit the procedure.
audience: agent + human
prerequisites:
  - Stack healthy (see [`docs/00-agent-quickstart.md`](../00-agent-quickstart.md))
  - JWT obtainable as admin or superadmin
  - `radtest` available on the host (FreeRADIUS `freeradius-utils` package)
inputs:
  - Per-recipe: registered NAS, seeded users, optional category / segment / circuit
outputs:
  - Observable `Access-Accept` / `Access-Reject` verdict that maps to the recipe's claim
---

# Simulation Framework Overview

> **Use case:** an AI agent needs to simulate RADIUS authentication against
> NACs **already registered** through the API. This folder documents the
> exact procedure for each kind of simulation.

## 1. The contract every recipe follows

Each `docs/simulation/NN-*.md` file is structured so an AI agent can chain
them without re-reading source. The contract:

```yaml
goal:        # one sentence — what an agent confirms by following the recipe
prereqs:     # bullet list — NAS registered, user exists, etc.
inputs:      # env vars + DB seed steps
steps:       # numbered; each = (command, expected-output)
validate:    # how the agent confirms success (query + expected value)
failure:     # named failure patterns + recovery
backout:     # how to reverse the seed without polluting the next run
```

If a recipe deviates, the deviation is explicitly called out at the top.

## 2. The simulation toolbox

| Tool | Used for | Always available? |
|---|---|---|
| `radtest` | `Access-Request` from the host | needs `freeradius-utils` |
| `docker exec radius-server radtest …` | Same, from inside the container | always |
| `curl + /api/v1/...` | Provision users, NAS, categories, policies, circuits | always |
| `mysql -h db -u root …` | Inspect FreeRADIUS tables directly | only with DB shell |
| `docker logs radius-server` | FreeRADIUS debug (`-X`) output | always |
| `/api/v1/access-policies/preview` | Deterministic preview **before** sending RADIUS | always |
| `/api/v1/circuits/resolve` | CIR resolution preview | always |
| `/api/v1/audit/access` | Verify the post-auth trail landed | always |

> **Always preview before launching.** `POST /api/v1/access-policies/preview`
> and `GET /api/v1/circuits/resolve` give you the same answer FreeRADIUS will
> compute, without a UDP round-trip. If the preview disagrees with the
> simulation outcome, the bug is in the recipe — fix the seed first.

## 3. The fixture contract

Every simulation recipe operates against the **same seeded state** used by
`radius-tests/fixtures/seed_authorization_matrix.sql` and the new
`seed_vendor_scenarios.sql`. The matrix:

| User | Password | NAS-IP | Group | Marker |
|---|---|---|---|---|
| `segment_admin_a` | `testpassword` | `192.168.10.50` | `MatrixReaders` | `MATRIX-EXACT-*` reply attrs |
| `segment_reader_b` | `testpassword` | `192.168.10.51` | `MatrixReaders` | `MATRIX-RANGE-*` reply attrs |
| `cir_premium_user` | `cirpass!` | `192.168.10.50` | `Premium-CIR` | CIR values (`Cambium-Canopy-HPDLCIR := 51200`) |
| `jit_operator` | `jitpass!` | `192.168.10.50` | `JIT-Admins` (expires in 2h) | `Expiration := <timestamp>` |

If a recipe needs different fixtures, it **regenerates** the affected rows
and explicitly calls them out in `backout`.

## 4. Cleanup contract

Every recipe must end with one of:

- **Idempotent re-run** — the recipe can be re-executed any number of times
  and produce the same observable result.
- **Explicit backout** — a `backout:` section lists the `DELETE`s needed
  to restore the pre-recipe state.

Recipes **must not** leave behind state the next recipe didn't expect. If
they do, document it in `backout` and chain.

## 5. Local debug scripts (`scripts/`)

These are one-off helpers kept tracked by the repository because they
capture debug state from prior incidents. They are **not part of the
public surface** — never call them from a recipe. Listed here only so an
agent knows what they are if it stumbles across them:

| File | Origin / purpose | Status |
|---|---|---|
| `scripts/check_hash.py` | Hashing diagnostic used during password-hash migration | legacy, kept for replay |
| `scripts/test_mac.sh`, `test_mac_wrong.sh`, `test_mac_user.sql` | Cambium MAC-priority reproductions | legacy, kept for replay |
| `scripts/test_groups_modal.py` | Frontend modal smoke test | legacy, kept for replay |
| `scripts/eapol_test.conf` | FreeRADIUS EAP test config | legacy, kept for replay |

For active work, use the recipes in this folder — not these scripts.

## 6. Reading order suggestion

| Reader | Order |
|---|---|
| New AI agent on first run | `00-overview` → `01-basic-access-request` → (any other) |
| Operator debugging a specific failure | The matching recipe by topic |
| Reviewer evaluating scope | All 8 recipes in order |

## Cross-references

- **Stack provisioning:** [`docs/00-agent-quickstart.md`](../00-agent-quickstart.md)
- **Access Policies module:** [`docs/modules/access-policies.md`](../modules/access-policies.md)
- **Circuits module:** [`docs/modules/circuits.md`](../modules/circuits.md)
- **RADIUS test seeds:** [`radius-tests/fixtures/`](../../radius-tests/fixtures/)
- **RADIUS pytest contract:** [`radius-tests/README.md`](../../radius-tests/README.md)
