# Changelog

All notable changes to ZeroRadius are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note:** Auto-generated summaries can mask scope drift. Every unreleased
> change should appear under the *Unreleased* heading and the next release
> must regenerate this file from `git log <prev-tag>..<new-tag>` before tagging.

---

## [Unreleased]

### Security
- **Failing `radgroupcheck` now produces `Access-Reject` instead of `Access-Accept` with stripped reply attrs** ([#92](https://github.com/alexandervazquez98/ZeroRadius/issues/92)). The second SQL pass in the FreeRADIUS `authorize` section was invoked as `-sql` (continue on failure), so a `radgroupcheck` row whose check did not match silently stripped reply attributes and returned `Access-Accept` at the device's default privilege level. Switched the invocation to bare `sql` (line 441 of `radius/default.conf`) so the `rlm_sql` `fail` return aborts `authorize` and produces `Access-Reject` — matching the documented contract in [`docs/01-nas-provisioning.md` §2](docs/01-nas-provisioning.md#2-using-huntgroups-for-regional-segmentation). Locked with four new RADIUS protocol scenarios in `radius-tests/test_radius_huntgroup_enforcement.py` (covering: matching NAS, mismatching NAS, group with no `radgroupcheck` rows, user with no `radusergroup`). **BREAKING**: deployments with `radgroupcheck` rows that previously no-op'd silently will start rejecting on upgrade; audit existing `radgroupcheck` rows before rolling out.

---

## [v1.3.4] - 2026-10-09

The **Radius Cert Cleanup** release. Closes the 2 issues opened in the post-v1.3.3 audit round and removes an embedded RSA private key from the public repo. Both PATCH per the project's SemVer policy.

### Fixed
- **Container startup chowned the developer's working tree** ([#85](https://github.com/alexandervazquez98/ZeroRadius/issues/85), [PR #90](https://github.com/alexandervazquez98/ZeroRadius/pull/90), 24cd314). The \`radius\` service bind-mounted \`./radius/certs\` into the container, the \`Dockerfile\` symlinked \`/etc/freeradius/certs\` onto \`/etc/raddb/certs\`, and the entrypoint's \`chown -R freerad:freerad \$CERT_DIR\` walked through the symlink onto the host tree. \`git checkout\` / \`git stash\` then failed with \`Permission denied\` on \`radius/certs/server.key\` after every \`docker compose up\`. Fix: replaced the host bind mount with a top-level named volume \`radius_certs\`, removed the \`/etc/freeradius/certs\` symlink in the \`Dockerfile\`, and made the entrypoint generate a self-signed cert pair in the volume when it's empty (the prior \`./radius/certs\` was load-bearing for the \`eap\` module). The backend service mounts the same volume read-only at \`/app/radius-certs\` so it can still serve the CA cert via \`/nas\`. Chown now operates only on container-internal storage — no host tree is touched. End-to-end verified against a Catalyst 3650 switch (\`Current privilege level is 15\` after \`Access-Accept\`).
- **RSA private key committed to the public repo** ([#88](https://github.com/alexandervazquez98/ZeroRadius/issues/88), same PR). \`radius/certs/{ca,server}.{pem,key}\` were tracked in git, exposing a valid 1679-byte RSA private key downloadable without authentication. \`git rm --cached\` untracks the three files; \`.gitignore\` now lists \`radius/certs/*\` with a \`!radius/certs/.gitkeep\` exception so the directory survives a fresh clone but the certs can never be re-tracked. \`backend/tests/unit/test_cert_init.py\` rewritten to drive the entrypoint's openssl invocation in \`tmp_path\` instead of asserting the working tree, removing the implicit dependency on tracked artifacts.

### Out of scope (tracked in #89)
- The key is still in git history since \`c0b1625\` — full history rewrite via \`git filter-repo\` is issue #89 and will land in a separate, coordinated PR with announcement to contributors.

---

## [v1.3.3] - 2026-10-09

The **Issues Triage Part 2** release. Closes the remaining 2 issues from the post-#73 audit. Both are PATCH per the project's SemVer policy.

### Fixed
- **\`/dictionary/upload\` could not install the Cisco dictionary** ([#76](https://github.com/alexandervazquez98/ZeroRadius/issues/76), [PR #86](https://github.com/alexandervazquez98/ZeroRadius/pull/86), 739f340). The vendor-ID collision check in \`dictionary_loader.py\` used a hard-coded list of ~15 "built-in" vendor IDs that approximated the upstream FreeRADIUS image. Because \`radius/Dockerfile\` deliberately removes most vendor dictionaries and keeps only Microsoft, the list was wrong: \`POST /dictionary/upload\` rejected \`dictionary.cisco\` with vendor 9 even though Cisco was not present in the running container. Two contradictory rejection messages pointed at a "built-in FreeRADIUS vendor" that didn't exist in the image. Replaced the static list with a dynamic lookup that asks the \`radius-server\` container which vendor dictionaries are actually loaded (cached for the process lifetime, with an accurate static fallback of just Microsoft 311 for unit-test mode). Also ships \`backend/dictionaries/dictionary.cisco\` (minimal: \`VENDOR Cisco 9\`, \`Cisco-AVPair 1 string\`) so \`shell:priv-lvl=15\` authorization works out of the box. The \`dictionaries/*\` gitignore rule was refined to whitelist the project-shipped file while keeping operator-specific custom dicts ignored.
- **Frontend TLS cert filenames diverged across three sources** ([#79](https://github.com/alexandervazquez98/ZeroRadius/issues/79), [PR #87](https://github.com/alexandervazquez98/ZeroRadius/pull/87), c794aa1). The names referenced by \`frontend/nginx.conf\` (\`nginx.crt\`/\`nginx.key\`) did not match the names produced by \`generate_certs.py\` (\`server.pem\`) and the entrypoint fallback (\`nginx.crt\`/\`nginx.key\`). Aligned all three sources to \`server.crt\`/\`server.key\`. Also fixed the hardcoded \`SERVER_IP = "192.168.1.35"\` in \`generate_certs.py\` with a 4-tier resolver (\`SERVER_IP\` env var → UDP-socket probe → \`gethostbyname\` → 127.0.0.1 fallback) so the cert SAN matches the actual host. Locked the full \`nginx.conf\` ↔ \`generate_certs.py\` ↔ \`docker-entrypoint.sh\` ↔ \`tests\` symmetry matrix with 20 regression tests (3 of which are run against unmodified \`main\` and fail on the unfixed code).

### Notes
- The two PRs that were "Queued for v1.3.3" in v1.3.2's release notes are closed with this release.

---

## [v1.3.2] - 2026-10-08

The **Issues Triage** release. 4 fixes from the post-`#73` audit:
3 bugs that blocked real deployments and 1 docs mass-fix. All bump PATCH
per the project's SemVer policy (`fix/` and `docs/` → PATCH).

### Fixed
- **RADIUS healthcheck was probing TCP against a UDP port** ([#74](https://github.com/alexandervazquez98/ZeroRadius/issues/74), [PR #81](https://github.com/alexandervazquez98/ZeroRadius/pull/81), 9523196). The Linux `radius` container was stuck `unhealthy` forever because `nc -z -w2 127.0.0.1 1812` defaults to a TCP probe; RADIUS auth binds UDP. Added `-u`. `radius-syslog` (which `depends_on: backend: condition: service_healthy`) was collateral damage. Locked the contract with a 3-test regression guard covering both `docker-compose.yml` and `docker-compose.linux.yml` (the latter uses `network_mode: host` for `radius`, so the port assertion skips that case).
- **First clean deploy entered an infinite restart loop** ([#75](https://github.com/alexandervazquez98/ZeroRadius/issues/75), [PR #82](https://github.com/alexandervazquez98/ZeroRadius/pull/82), 2afdf26). `database/init.sql` seeds every table but does not stamp `alembic_version`; the startup hook called `alembic upgrade head` which re-ran the whole chain against an already-populated schema and crashed with `Duplicate column 'zone_id'`. `run_pending_migrations()` now detects the empty / missing `alembic_version` and stamps at head instead of upgrading. The schema from `init.sql` already matches head; only the bookmark was missing. Ships a 6-test regression suite.
- **All documented API paths used a non-existent `/api/v1` prefix** ([#77](https://github.com/alexandervazquez98/ZeroRadius/issues/77), [PR #83](https://github.com/alexandervazquez98/ZeroRadius/pull/83), 87f4a93). 171 `/api/v1/` occurrences across 26 docs files, every `curl` example returning 404. Mass-`sed s|/api/v1/|/|g`; symmetric 171/171 insertion/deletion count confirms only path prefixes were touched. `docs/api-reference.md` front-matter updated to state the no-prefix contract. Locked with a 2-test regression guard (live OpenAPI + static docs walk).
- **Backend port 8000 was never published** ([#78](https://github.com/alexandervazquez98/ZeroRadius/issues/78), [PR #84](https://github.com/alexandervazquez98/ZeroRadius/pull/84), 9ed455e). `docker-compose.yml` `backend` service had no `ports:` mapping, so `curl localhost:8000/health` and the Swagger UI at `/docs` were unreachable from the operator's shell. Added `127.0.0.1:8000:8000` (loopback only — not exposed to the network). Docs aligned. Locked with 2 unit tests asserting the port is published AND bound to loopback (not `0.0.0.0`).

### Added
- `backend/scripts/alembic.py` ([#80](https://github.com/alexandervazquez98/ZeroRadius/issues/80), same PR as #75). The `docs/deployment.md` §6.4 upgrade instructions referenced `python -m scripts.alembic upgrade head` but the module did not exist. Thin wrapper that forwards every argument to `alembic.command.<subcommand>` so the operator only needs to remember one command form.
- `backend/dictionaries/dictionary.cisco` (PR #86, [issue #76](https://github.com/alexandervazquez98/ZeroRadius/issues/76)). Ships a minimal Cisco vendor dict (vendor 9, `Cisco-AVPair 1 string`) so `shell:priv-lvl=15` authorization works out of the box. The `dictionaries/*` gitignore rule was refined to whitelist this project-shipped file while keeping operator-specific custom dicts ignored. **Not included in this release** — #86 was opened after this release was tagged and is queued for v1.3.3.

---

## [v1.3.1] - 2026-10-08

The **AI-Ready Documentation** release. Zero code changes; the bump is on
the docs side per the project's SemVer policy (`docs/` → PATCH). See
[PR #73](https://github.com/alexandervazquez98/ZeroRadius/pull/73).

### Added
- **RADIUS vendor-specific test scenarios** — 16 new scenarios covering Cisco WLC, Dahua CCTV, Proxy-MAC, and generic IP devices. New `send_access_request_vendor()` helper in `radius-tests/conftest.py` supports `Called-Station-Id`, `NAS-Identifier`, `NAS-Port-Type`. Existing VSA tests hardened to work without the Cisco dictionary. (`feat(radius)`, 9e39084)
- Dahua added to the VSA vendor consistency validation (`backend/app/services/vsa_guard.py`).
- **AI-agent-ready documentation foundation** ([`docs/00-agent-quickstart.md`](docs/00-agent-quickstart.md)) — clone → env → deploy → smoke-test → full pyramid in <10 minutes, with deterministic commands and expected output patterns. The agent contract is documented in the frontmatter of every foundational doc.

### Changed
- **Documentation overhaul** ([PR #73](https://github.com/alexandervazquez98/ZeroRadius/pull/73), 44 files, +4712 / −661 lines, 0 code changes):
  - `README.md` — badge v1.2.0 → v1.3.1; complete docs index; deploy quickstart.
  - `CHANGELOG.md` — full Keep-a-Changelog format (formerly truncated at v1.1.1).
  - `AGENTS.md` — removed dead `zero-radius-diagnose` reference; aligned with `.atl/skill-registry.md`.
  - [`docs/architecture.md`](docs/architecture.md) — five-container topology with Mermaid diagrams, full data model, process-level host layout, symptom→doc lookup table.
  - [`docs/deployment.md`](docs/deployment.md) — three compose files (main / test / Linux override); canonical env-var catalog (12 vars); secrets generation; TLS cert lifecycle; troubleshooting matrix.
  - [`docs/testing.md`](docs/testing.md) — AI-ready commands per layer (Vitest + pytest + pyrad + Playwright); markers reference; RADIUS precondition probe env vars.
  - [`docs/database.md`](docs/database.md) — full schema reference (RADIUS standard + ZeroRadius domain + `nas_cidr_ranges` view); Alembic migration chain; common queries.
  - [`docs/security-coverage.md`](docs/security-coverage.md) — OWASP Top 10:2021 threat catalog (A01–A10), each mapped to controls and integration tests.
  - [`docs/api-reference.md`](docs/api-reference.md) — endpoint index grouped by domain, with pagination and error shapes.
  - **Per-module docs** under `docs/modules/`: `access-policies`, `device-registry`, `network-segments`, `nas-categories`, `circuits`, `dictionaries`, `admin-users`, `syslog-dashboard`, `audit`, `rate-limiting`.
  - **Simulation recipes** under `docs/simulation/`: `00-overview` (framework) and `01..07` (basic Access-Request, VSA vendor scenarios, Cambium proxy baseline, network segments precedence, Access Policies resolution, circuits & bandwidth, JIT break-glass).
  - [`docs/06-cir-configuration-manual.md`](docs/06-cir-configuration-manual.md) — rewritten as a **legacy pointer** (HTML-comment-preserved v1.2.0 text inside) because the CIR / Privilege Map content was unified into the Access Policies module in v1.3.0.

### Removed
- Six tracked one-off debug scripts in `scripts/` (`check_hash.py`, `eapol_test.conf`, `test_mac.sh`, `test_mac_wrong.sh`, `test_mac_user.sql`, `test_groups_modal.py`) — untracked via `git rm --cached` (files retained on disk for historical reuse). New `scripts/` `.gitignore` rule with pointer to [`docs/simulation/00-overview.md` § 5](docs/simulation/00-overview.md#5-local-debug-scripts).
- Inconsistent terminology: `Privilege Map` → `Access Policies`; `/privilege-map` → `/access-policies`; `user_nas_privilege_map` → `access_policy_assignments` (renamed via Alembic migration `c0123d4`); stale references to the removed IAM module.

### Fixed
- Test: removed obsolete `test_category_reassign.py` (covered by the new CIR model tests).

---

## [v1.3.0] - 2026-04-25

The **Access Policies** consolidation release. CIR management and Privilege Map
merge into a single unified module with deterministic precedence rules, bulk
reassignment, category membership guard, and a CIR (circuit) model with
explicit resolution endpoint.

### Added
- **CIR model & resolution endpoint** (`feat(circuits)` e614aec). New `Circuit` table, dedicated management workflow, `/circuits/resolve` preview endpoint with `BandwidthProfile` association.
- **Access Policies** — single unified module replacing Privilege Map + CIR Manager (`feat(access-policies)` b34c5b1, PR #59). Three tabs in the UI: `AssignmentsTab`, `BandwidthProfilesTab`, `PreviewTab`.
- **Bulk category reassignment** for AccessPolicyAssignment (`feat(access-policies)` 3050091, PR #68).
- **Category membership guard** for AccessPolicyAssignment creation (`feat(access-policies)` 4a86284); wired into the router with `validate_category_membership` (cc6fd9c, bde396b, c2162a4).
- **`category_id` query filter** on `GET /nas` (`feat(api)` 3b98b49).
- **`cir_id` in assignment schema** so CIR ↔ AccessPolicy binding is explicit (`feat(circuits)` 77fcc8c).
- **Auto-migration + runtime schema validation** on backend startup (`feat(db)` 1c611e9, PR #62). Also added by 415546f for syslog-compliance.

### Fixed
- **Race condition & duplicate assignments** in category guard (`fix(access-policies)` cc6fd9c).
- **`nas.category_id` index + ordering + validation** for predictable filter behaviour (`fix(nas)` a4729cb).
- **CIR resolution correctness**: multiple test failures resolved (35f6194, c4fb94e).
- **`/resolve` route ordering** to avoid collision with `/{circuit_id}` (77fcc8c).
- **`cir_id` allowed to be null** for assignments (`fix(circuits)` 5b6fe0e).
- **Test criticality values** — corrected from deprecated `medium` to `standard` (e201728).
- Reverted a duplicate of the bulk-reassign commit (9407ba5).

### Removed
- `test_category_reassign.py` (7efe6e8 — superseded by CIR model tests).

---

## [v1.2.0] - 2026-04-24

The **security hardening + device registry + CIR foundation** release.
The Privilege Map → Access Policies path starts here with the native SQL-Group
hydration work and the removal of the obsolete IAM module.

### Added

#### Security hardening (three phases)
- **Phase 1** (`feat(security)` #35): JWT hardening, account lockout, CORS, security headers.
- **Phase 2** (`feat(security)` #38): rate limiting + critical IAM-NAC auth vulnerability fix.
- **Phase 3** (`feat(security)` #39, A01–A10): path traversal protections, role-based authorization, auth hardening, upload validation, audit checks. Adds eight dedicated security tests under `backend/tests/integration/test_security_*.py`.

#### Device registry (new)
- `DeviceRegistry` model with category resolution (`feat(device-registry)`).
- Bulk XLSX/CSV template with Categories sheet (`feat(device-registry)`) — later stabilised to CSV with category_id and MAC formats (`fix(device-registry)` x4 commits).
- Bulk stats endpoint.
- UI tab consolidated NAS Devices and Device Registry (`feat(ui)`).

#### CIR (foundation)
- Dedicated CIR management workflow (`feat(cir)` x2).
- `Calling-Station-Id` (MAC) support + security hardening (`feat(cir)`).

#### RADIUS
- **Auto-initialize certificates** on container startup (`feat(radius)` #33).
- Strict MAC isolation in authorization SQL queries (`fix(radius)`).
- Native SQL-Group hydration support (`refactor(radius)`, `fix(radius)` x8) — dynamic group attribute injection via `rlm_sql`.

#### Syslog
- High-load + system health dashboard (`feat`).
- ISO 27001 audit-trail compliance (`feat(security)`).
- Message filter + partial matching (`feat(syslog)`).

#### Other features
- **RADIUS groups management UI** with full CRUD (`feat(groups)` #29).
- **Searchable comboboxes** for vendor/dictionary selection and attribute selection (`feat(groups)` #30, #31).
- **NAS CA certificate download** button + cert verification enablement (`feat(nas)`).
- **Mount `radius-certs`** for the CA certificate download endpoint (`feat`).
- **Structured JSON logging, Error Boundaries, toast system** (`feat(phase2-g1)` #54).
- **Alembic** setup with the `network_segments` migration (`feat(alembic)`).
- **Cross-platform Docker Compose** with auto-detect Linux host networking (`feat(infra)`).
- **Local-first test workflow** (`feat(testing)`).

### Fixed
- **118 fix commits** in this release. Highlights (by area):
  - `fix(radius)` (28): UserLevel variants, attribute recognition, dynamic group attr handling, native hydration logical flow, env-based hydration toggle, `nas_based_authorization` aligned with the renamed `access_policy_assignments` table.
  - `fix(backend)` (18): linter strictness, FastAPI typing, import ordering.
  - `fix(device-registry)` (5): reject example/template rows in bulk import; CSV-over-XLSX template; remove serial_number.
  - `fix(nas)` (5): cascade nas IP updates to access_policy_assignments; reject hostnames in NAS names.
  - `fix(iam-nac)` (6): superseded by the IAM removal refactor (see Removed).
  - `fix(syslog)`, `fix(security)`, `fix(system)`, `fix(network-segments)`, `fix(alembic)`, `fix(certs)`, `fix(docker)`.
- MariaDB healthcheck spam resolved (`fix(db)`).
- `refactor(cir)`: future-annotations import removed (pydantic compatibility).

### Changed (refactors)
- **Native SQL-Group hydration** made the default path (`refactor(radius)`).
- **Removed obsolete IAM module**; rescued JIT access (`refactor`).
- **Simplified Policies page** — Macros tab removed; only RADIUS groups CRUD remains (`refactor(groups)` #30).
- **Privilege Map / CIR Manager extracted into a shared `privilege` service**; schemas cleaned; UI formats MACs canonically (`refactor(cir)`).
- Removed legacy group assignments in favor of access policies (`refactor(ui)`).

### Security
- All A01–A10 threats now have at least one regression test (phase 3 hardening).
- Rate limiting enabled by default for all auth and write endpoints.
- Native SQL-Group hydration disables previously-needed dynamic attribute injection logic, reducing attack surface.

---

## [v1.1.1] - 2026-03-29

### Added
- English-native master repository pitch (`README.md`).
- [`docs/01-nas-provisioning.md`](docs/01-nas-provisioning.md): user manual with NAS creation and Huntgroup Mermaid.js routing diagram.
- [`docs/02-iso27001-privilege-map.md`](docs/02-iso27001-privilege-map.md): security authorization flow for NAS-based Privilege Maps with ISO 27001 constraints.
- [`docs/03-jit-break-glass.md`](docs/03-jit-break-glass.md): complete sequence diagram defining the JIT Break-Glass operator request, execution, and expiration.

[Unreleased]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.3.1...HEAD
[v1.3.1]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.3.0...v1.3.1
[v1.3.0]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.2.0...v1.3.0
[v1.2.0]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.1.1...v1.2.0
[v1.1.1]: https://github.com/alexandervazquez98/ZeroRadius/releases/tag/v1.1.1
