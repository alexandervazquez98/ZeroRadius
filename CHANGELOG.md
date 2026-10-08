# Changelog

All notable changes to ZeroRadius are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note:** Auto-generated summaries can mask scope drift. Every unreleased
> change should appear under the *Unreleased* heading and the next release
> must regenerate this file from `git log <prev-tag>..<new-tag>` before tagging.

---

## [Unreleased]

### Added
- **RADIUS vendor-specific test scenarios** — 16 new scenarios covering Cisco WLC, Dahua CCTV, Proxy-MAC, and generic IP devices. New `send_access_request_vendor()` helper in `radius-tests/conftest.py` supports `Called-Station-Id`, `NAS-Identifier`, `NAS-Port-Type`. Existing VSA tests hardened to work without the Cisco dictionary. (`feat(radius)`, 9e39084)
- Dahua added to the VSA vendor consistency validation (`backend/app/services/vsa_guard.py`).

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

[Unreleased]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.3.0...HEAD
[v1.3.0]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.2.0...v1.3.0
[v1.2.0]: https://github.com/alexandervazquez98/ZeroRadius/compare/v1.1.1...v1.2.0
[v1.1.1]: https://github.com/alexandervazquez98/ZeroRadius/releases/tag/v1.1.1
