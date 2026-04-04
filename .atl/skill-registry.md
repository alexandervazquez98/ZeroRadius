# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

Generated: 2026-04-03

---

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When writing Go tests, using teatest, or adding test coverage | go-testing | C:/Users/polop/.claude/skills/go-testing/SKILL.md |
| When user asks to create a new skill, add agent instructions, or document patterns for AI | skill-creator | C:/Users/polop/.claude/skills/skill-creator/SKILL.md |
| When creating a pull request, opening a PR, or preparing changes for review | branch-pr | C:/Users/polop/.claude/skills/branch-pr/SKILL.md |
| When creating a GitHub issue, reporting a bug, or requesting a feature | issue-creation | C:/Users/polop/.claude/skills/issue-creation/SKILL.md |
| When user says "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen" | judgment-day | C:/Users/polop/.claude/skills/judgment-day/SKILL.md |

## Project Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When writing, modifying, or executing tests in ZeroRadius — any layer. Auto-triggers before any git commit on feat, fix, or refactor | zero-radius-testing | C:/Users/polop/OneDrive/PROGRAMMING/zeroradius/.agents/skills/zero-radius-testing/SKILL.md |
| When user asks to diagnose, review, deploy or troubleshoot ZeroRadius server; "revisar el servidor"; test/deploy servers | zero-radius-diagnose | C:/Users/polop/OneDrive/PROGRAMMING/zeroradius/.agents/zero-radius-diagnose/SKILL.md |

---

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### go-testing
- Use table-driven tests: `tests := []struct{ name, input, expected string }{ ... }` for multi-case functions
- Test Bubbletea Model state: `newModel, _ := m.Update(tea.KeyMsg{...}); m = newModel.(Model)`
- Full TUI flows: `teatest.NewTestModel()` + `tm.Send()` + `tm.WaitFinished()` + `tm.FinalModel()`
- Golden files: compare `m.View()` against `testdata/*.golden`; regenerate with `-update` flag, never edit by hand
- Mock system info via struct injection (`m.SystemInfo = &system.SystemInfo{...}`), not env vars
- Test file per source file: `model.go` → `model_test.go`; skip slow integration tests with `-short`
- Run all: `go test ./...` | verbose TUI: `go test -v ./internal/tui/...` | update goldens: `go test -update ./...`

### skill-creator
- SKILL.md frontmatter MUST have: name, description (with "Trigger:" keyword), license: Apache-2.0, metadata.author, metadata.version
- Structure: `skills/{name}/SKILL.md` + optional `assets/` (templates/schemas) and `references/` (local doc links only)
- `references/` must point to LOCAL file paths — NEVER web URLs
- After creation, register in `AGENTS.md` index table
- Check `skills/` for duplicates before creating — skip if already exists
- Keep code examples minimal; no lengthy explanations; no troubleshooting sections; no Keywords section

### branch-pr
- Every PR MUST link an approved issue: body MUST contain `Closes #N`, `Fixes #N`, or `Resolves #N`
- Branch naming regex: `^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)\/[a-z0-9._-]+$`
- PR MUST have exactly one `type:*` label: type:bug, type:feature, type:docs, type:refactor, type:chore, type:breaking-change
- Commit format: `type(scope): description` — NO Co-Authored-By trailers
- Run `shellcheck scripts/*.sh` before pushing
- Linked issue MUST have `status:approved` — PRs without it are blocked by GitHub Actions

### issue-creation
- NEVER create blank issues — MUST use `bug_report.yml` or `feature_request.yml` template
- Issue gets `status:needs-review` automatically; maintainer adds `status:approved` to unlock PRs
- PRs can only be opened AFTER the linked issue has `status:approved`
- Questions go to Discussions — NOT issues
- Search for duplicates first: `gh issue list --search "keyword"`
- Bug title: `fix(scope): description` | Feature title: `feat(scope): description`

### judgment-day
- NEVER review code as orchestrator — launch TWO blind judges as parallel async delegates
- WARNING (real) = normal user can trigger it; WARNING (theoretical) = contrived/impossible scenario
- Theoretical warnings are INFO — do NOT fix, do NOT re-judge, do NOT count toward APPROVED threshold
- After Round 1, show verdict table and ASK user before fixing — never auto-fix
- Fix Agent is a SEPARATE delegation — never reuse a judge as fixer
- After 2 fix iterations, ASK user before continuing — never auto-escalate
- APPROVED = 0 confirmed CRITICALs + 0 confirmed real WARNINGs (theoretical warnings may remain)
- NEVER commit/push between fix and re-judgment; re-judgment is mandatory before any terminal action
- Inject Project Standards from skill registry into BOTH judge prompts AND Fix Agent prompt

### zero-radius-testing
- Fast local is the DEFAULT: on Windows or local machine, run ONLY fast local tests (no Docker)
- Docker (`docker-compose.test.yml`) is an ADDITIONAL layer for integration/RADIUS/E2E — never replaces fast local
- On test servers or hosts with Docker available, use Docker for heavy layers when applicable
- ALWAYS use `python -m pytest` — never `pytest` directly (not on PATH on Windows)
- Prefer repo wrappers first: `./scripts/test-backend-fast.sh` and `./scripts/test-frontend-fast.sh`
- Backend fast tests assume `backend/.venv`; script sources `.env.test.example` defaults then overlays `.env.test` if present; coverage enabled by default, `--no-cov` is opt-in
- Frontend Vitest on Windows: `cmd /c "node_modules\.bin\vitest.cmd run"` — NEVER `npm run test` in PowerShell
- Run `test_schema_sync.py` after ANY change to `models.py` or `init.sql` — catches model↔DDL drift
- MSW MUST be v2: `import { http, HttpResponse } from 'msw'` — NEVER `rest` from v1
- Use `<AuthProvider initialToken="fake-token">` in tests — do NOT mock localStorage
- Wrap tests with `ToastProvider` when rendering pages/components that call `useToast()`
- GroupsPage needs 5 MSW handlers: `/api/groups/list`, `/api/groups/check`, `/api/groups/reply`, `/api/nas`, `/api/dictionary/attributes`
- NAS creation tests: `shared_secret` must be 32+ chars
- Coverage threshold: 59% (`--cov-fail-under=59`) — do NOT raise without adding tests first
- NEVER commit with failing tests; regression test format: `test_regression_<bug_description>`
- RADIUS tests need `@pytest.mark.radius` — skip in CI: `python -m pytest -m "not radius"`
- Infrastructure tests (certs, Docker, Linux-specific) need `@pytest.mark.infra` — skip in fast local: `python -m pytest -m "not radius and not infra"`
- RADIUS env var: `RADIUS_PORT` (default: 1812), NOT `RADIUS_AUTH_PORT`
- RADIUS tests cwd: `cd radius-tests` then `python -m pytest . -v -m radius` — NOT from backend/ or project root
- Docker test stack: `docker compose -f docker-compose.test.yml up -d` → backend on `localhost:8001`, DB on `localhost:3307`, RADIUS on `localhost:1812`
- E2E has TWO modes: (1) fast local with backend on `:8000` (vite proxy auto-routes), (2) Docker stack with backend on `:8001` (change vite proxy target in `vite.config.js`)
- Integration fast (httpx/SQLite) ≠ integration cross-service (Docker): fast integration runs without Docker; cross-service needs `docker-compose.test.yml`

### zero-radius-diagnose
- ALWAYS ask "¿Estás en casa o en la oficina?" BEFORE any SSH connection — determines available servers
- Oficina: `192.168.1.212`, password `9191289913aA`, workdir `~/radius/`
- Casa-pruebas: `192.168.1.37`, key `~/.ssh/id_ed25519_radius_test`, workdir `~/ZeroRadius/`
- Casa-deploy: `192.168.1.35`, key `~/.ssh/id_ed25519_deploy`, workdir `~/ZeroRadius/`
- NEVER run `docker compose down` — use `docker compose restart <service>` or rebuild to avoid DB data loss
- FreeRADIUS "Duplicate attribute" → remove conflicting dict from `/etc/raddb/custom_dictionaries/`
- `radius-server` uses `network_mode: host` + `DB_HOST: 172.17.0.1` (Docker gateway IP)

---

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md | C:/Users/polop/OneDrive/PROGRAMMING/zeroradius/AGENTS.md | Index — references files below |
| zero-radius-diagnose SKILL.md | C:/Users/polop/OneDrive/PROGRAMMING/zeroradius/.agents/zero-radius-diagnose/SKILL.md | Referenced by AGENTS.md |
| zero-radius-testing SKILL.md | C:/Users/polop/OneDrive/PROGRAMMING/zeroradius/.agents/skills/zero-radius-testing/SKILL.md | Referenced by AGENTS.md |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
