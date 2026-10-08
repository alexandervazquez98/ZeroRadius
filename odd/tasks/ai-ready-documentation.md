# Feature: AI-Ready Documentation Overhaul

**Status:** Planning → Implementation
**Created:** 2026-10-08
**Branch:** `feat/ai-ready-documentation`
**Base:** `origin/main` @ `9e39084e`
**Engram mirror:** zeroradius / topic `zeroradius-doc-overhaul-2026-10`

## Intent

Close every documentation gap surfaced in the 2026-10-08 audit, and restructure the docs so that an AI agent can autonomously **deploy**, **test**, and **simulate with registered NACs**.

The current docs (1006 lines / 41 KB / 13 files) have **7 OUTDATED**, **10+ GAPS**, and **6 INCONSISTENCIES**. docs/06 actively misrepresents the codebase (claims "no CIR UI" but `CircuitPage.jsx` exists with router, service, tests). CHANGELOG is 162 commits behind.

## Scope (in / out)

**In scope:**
- Refresh top-level docs (README, CHANGELOG, AGENTS)
- Rewrite docs/06 to reflect CIR/Circuits module reality
- Add AI-agent-ready foundational docs (`00-agent-quickstart`, `architecture`, `deployment`, `database`)
- Refresh `docs/testing.md` with deterministic commands for each test layer
- Add granular module docs (`docs/modules/`) for undocumented backend routers and frontend pages
- Add security-coverage catalog (A01–A10)
- Add simulation recipes for live NAC scenarios
- Fix inconsistencies: `Privilege Map` → `Access Policies`, `/privilege-map` → `/access-policies`, drop removed-IAM references
- Either gitignore or document debug scripts in `scripts/`

**Out of scope (separate features, not part of this change):**
- Actual code/feature changes (zero behavior changes to backend or frontend)
- Cleanup of `_local_backup/wip-snapshot-2026-10-08/` (separate decision)
- Working on the `feat/*` branches on origin (db-schema-validation, syslog-compliance, etc.)
- Implementing new features (e.g., a CIR metrics UI — that's `sdd/cir-metrics-ui`)

## Design

### Document architecture (target)

```
README.md                                     # Entry point, badge v1.3.0, complete index, deploy quickstart
CHANGELOG.md                                  # v1.1.1 → v1.3.0 + post-v1.3.0 entries
AGENTS.md                                     # Skills registry (corrected)
LICENSE                                       # If missing, add TODO note

docs/
├── 00-agent-quickstart.md                    # NEW: AI-agent entry point. ~3 min to "running stack"
├── architecture.md                           # NEW: components, data flow, ports, networking
├── deployment.md                             # NEW: docker-compose, env vars, secrets, troubleshooting
├── testing.md                                # REFRESH: AI-ready commands per test layer
├── database.md                               # NEW: schema reference, alembic migrations, views
├── api-reference.md                          # NEW: endpoint catalog (read-only / write operations)
├── security-coverage.md                      # NEW: A01-A10 threat catalog

├── modules/                                  # NEW: per-module documentation
│   ├── access-policies.md                    # The unified module (replaces docs/06)
│   ├── device-registry.md                    # Includes bulk CSV flow
│   ├── network-segments.md
│   ├── nas-categories.md                     # Refresh from docs/05
│   ├── dictionaries.md                       # NEW
│   ├── admin-users.md                        # NEW
│   ├── syslog-dashboard.md                   # NEW (WebSocket viewer lives in docs/04 + dashboard here)
│   ├── audit.md                              # NEW (radpostauth + admin audit + export)
│   └── rate-limiting.md                      # NEW (middleware/force_password_change.py)

├── simulation/                               # NEW: NAC simulation recipes for AI agents
│   ├── 00-overview.md
│   ├── 01-basic-access-request.md
│   ├── 02-vsa-vendor-scenarios.md
│   ├── 03-cambium-proxy-baseline.md
│   ├── 04-network-segments-precedence.md
│   ├── 05-access-policies-resolution.md
│   ├── 06-circuits-and-bandwidth.md
│   └── 07-jit-break-glass.md

├── 01-nas-provisioning.md                    # REFRESH (AI-ready)
├── 02-iso27001-privilege-map.md              # REFRESH (rename to "Access Policies" terminology)
├── 03-jit-break-glass.md                     # REFRESH
├── 04-live-log-viewer.md                     # REFRESH (correct any drift)
├── 05-nas-categories.md                      # REFRESH (move to modules/, or keep here as legacy)
└── 06-cir-configuration-manual.md            # REWRITE (replace with modules/access-policies.md link + archived pointer)
```

### AI-ready doc contract

Each new top-level / module / simulation doc follows `cognitive-doc-design` principles:

1. **Frontmatter** (YAML):
   - `goal:` — one sentence — what an agent achieves after reading
   - `audience:` — `agent` / `human` / `both`
   - `prerequisites:` — list of paths/conditions
   - `inputs:` — list of env vars, fixtures, NAS records needed
   - `outputs:` — observable signals of success
2. **Goal** section (one paragraph)
3. **Prerequisites** (concrete commands: `git status`, `docker ps`, etc.)
4. **Steps** (numbered; each step = one focused action + verbatim command + expected output pattern)
5. **Validation** (programmatic checks: HTTP status codes, log lines, DB queries)
6. **Failure modes** (named patterns + recovery)
7. **Cross-references** (relative links to other docs)

This contract lets an AI agent parse the doc, follow steps, validate against expected outputs, and recover from known failures.

### Branch and commit strategy

- Branch: `feat/ai-ready-documentation` (created)
- One work-unit commit per Phase (3 commits total for 3 phases)
- Within each phase, sub-changes can be staged individually via `git add -p` if useful, but the merge commit is per phase
- Conventional commits: `docs(<scope>): <summary>`
- No commits to `main` directly
- Push + PR remain user decisions

## Task Breakdown

### Phase 1 — Foundation (must this session)

- [ ] **1.1** `docs/.gitignore` add `_local_backup/` (or document why not)
- [ ] **1.2** `README.md` — refresh: badge to `v1.3.0`, complete docs index (include `00..06` + `architecture` etc.), deploy quickstart, links
- [ ] **1.3** `CHANGELOG.md` — regenerate from git log: `v1.2.0` (groups of feat/fix/refactor commits), `v1.3.0` (latest), `Unreleased` (post-v1.3.0)
- [ ] **1.4** `AGENTS.md` — fix dead `zero-radius-diagnose` reference; add `zero-radius-testing` (canonical from `.atl/skill-registry.md`); note `.atl/skill-registry.md` is the source of truth
- [ ] **1.5** `docs/00-agent-quickstart.md` — NEW: AI-agent entry point (clone → env → deploy → smoke test → run all 4 test layers)
- [ ] **1.6** `docs/architecture.md` — NEW: components (`backend`, `frontend`, `radius`, `rsyslog`, `mariadb`), networking/ports, data flow diagrams (Mermaid), dependency graph (Alembic → SQL views like `nas_cidr_ranges`)
- [ ] **1.7** `docs/deployment.md` — NEW: docker-compose stacks (main + test + linux), env vars catalog, secrets/certs lifecycle, troubleshooting matrix
- [ ] **1.8** `docs/testing.md` — REFRESH: AI-ready commands per layer (fronted/backend/radius/e2e), expected outputs, marker-based selection, fast vs full pyramid, CI plan
- [ ] **1.9** `docs/database.md` — NEW: ER diagram (textual/Mermaid), tables (radcheck, radreply, radgroupcheck, radgroupreply, app_audit_log, radpostauth, radacct, plus ZeroRadius domain tables), Alembic migrations timeline, SQL views (`nas_cidr_ranges`)
- [ ] **1.10** `docs/security-coverage.md` — NEW: A01-A10 catalog referencing `backend/tests/integration/test_security_*.py`
- [ ] **1.11** Commit Phase 1 (work-unit): `docs(scope): phase 1 - foundation & audit remediation`

### Phase 2 — Modules API & Reference (next session or continuation)

- [ ] **2.1** `docs/modules/access-policies.md` — NEW: replaces docs/06, CIR + Privilege Map + Bulk + Preview, 3 tabs UI, API endpoints, priority/precedence rules
- [ ] **2.2** `docs/modules/device-registry.md` — NEW: bulk CSV flow (template → upload → validation → stats), API endpoints
- [ ] **2.3** `docs/modules/network-segments.md` — NEW: CIDR overlap validation, segment-based targeting
- [ ] **2.4** `docs/modules/nas-categories.md` — NEW: refresh from docs/05 with current endpoint catalog
- [ ] **2.5** `docs/modules/dictionaries.md` — NEW: upload/rename/content, dictionary loader service
- [ ] **2.6** `docs/modules/admin-users.md` — NEW: unlock + role hierarchy
- [ ] **2.7** `docs/modules/syslog-dashboard.md` — NEW
- [ ] **2.8** `docs/modules/audit.md` — NEW: admin audit + radpostauth access + export
- [ ] **2.9** `docs/modules/rate-limiting.md` — NEW
- [ ] **2.10** `docs/api-reference.md` — NEW: endpoint catalog per router (read/write, role required, request/response shape, status codes)
- [ ] **2.11** Refresh `docs/01-nas-provisioning.md`, `docs/02-iso27001-privilege-map.md` (rename or merge), `docs/03-jit-break-glass.md`, `docs/04-live-log-viewer.md`
- [ ] **2.12** Rewrite `docs/06` as redirect → `docs/modules/access-policies.md` (legacy pointer)
- [ ] **2.13** Refresh `radius-tests/README.md` (now 7 test files, not 3)
- [ ] **2.14** Commit Phase 2 (work-unit): `docs(scope): phase 2 - modules & api reference`

### Phase 3 — Simulation Recipes & Cleanup (next session or continuation)

- [ ] **3.1** `docs/simulation/00-overview.md` — agent contract, simulation framework, fixture contract
- [ ] **3.2** `docs/simulation/01-basic-access-request.md` — happy-path + reject path with `radtest`
- [ ] **3.3** `docs/simulation/02-vsa-vendor-scenarios.md` — 16 vendor scenarios from `test_radius_vendor_scenarios.py`
- [ ] **3.4** `docs/simulation/03-cambium-proxy-baseline.md` — direct vs proxied MAC priority
- [ ] **3.5** `docs/simulation/04-network-segments-precedence.md` — segment CIDR + exception ranges
- [ ] **3.6** `docs/simulation/05-access-policies-resolution.md` — IP vs category vs segment resolution
- [ ] **3.7** `docs/simulation/06-circuits-and-bandwidth.md` — CIR resolution with `BandwidthProfile`
- [ ] **3.8** `docs/simulation/07-jit-break-glass.md` — JIT grant + expiration flow
- [ ] **3.9** Decide on `scripts/{check_hash,test_mac*,test_groups_modal,eapol_test}.*`: gitignore or document
- [ ] **3.10** Cleanup pass: doc cross-reference audit (relative links), consistent terminology check
- [ ] **3.11** Commit Phase 3 (work-unit): `docs(scope): phase 3 - simulation recipes & cleanup`

## Success Criteria

1. **Closing the audit**: every OUTDATED item from the 2026-10-08 audit is corrected; every GAPS module has a corresponding doc; every inconsistency is resolved.
2. **AI-agent readiness**: an agent reading `docs/00-agent-quickstart.md` can:
   - Clone the repo and produce a running stack in under 10 minutes (deployment commands copy-paste-able).
   - Identify which test layer applies to a given code change (`docs/testing.md` lookup).
   - Run the test pyramid end-to-end (`./scripts/test-all.sh --full`).
   - Provision a NAS, write an Access Policy, simulate `Access-Request` → `Access-Accept/Reject`, observe `Live Log Viewer` events.
3. **No code changes**: only documentation changes. `git diff main -- 'backend/**/*.py' 'frontend/**/*.jsx' 'radius/**/*.conf'` returns empty.
4. **Compile-able references**: every cross-reference between docs resolves (no broken relative links).
5. **Terminology consistency**: `Access Policies` used consistently (not `Privilege Map`); `/access-policies` used (not `/privilege-map`); no stale `IAM` references in docs.

## Risks & Open Questions

1. **Phase 3 simulation recipes** depend on a running FreeRADIUS server with seeded users. Each recipe must include deterministic seed steps so the agent can reproduce.
2. **Documentation volume** — three phases may exceed a single session. Reasonable to stop after Phase 1, validate, then continue.
3. **`docs/06 → modules/access-policies.md` migration** — keep docs/06 as a redirect/pointer, or delete entirely?
4. **`scripts/{check_hash,test_mac*}`** — gitignore or document? These are debug helpers; risk: deleting them later is harder than tracking them.

## Out-of-session follow-ups

- Open PR for the feature branch (push + gh pr create are user decisions).
- After merge, address any doc feedback from review.
- Clean up `_local_backup/wip-snapshot-2026-10-08/` (separate decision).
