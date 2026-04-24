# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When writing Go tests, using teatest, or adding test coverage. | go-testing | C:\Users\Alex\.claude\skills\go-testing\SKILL.md |
| When creating a GitHub issue, reporting a bug, or requesting a feature. | issue-creation | C:\Users\Alex\.claude\skills\issue-creation\SKILL.md |
| When creating a pull request, opening a PR, or preparing changes for review. | branch-pr | C:\Users\Alex\.claude\skills\branch-pr\SKILL.md |
| When user says "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen". | judgment-day | C:\Users\Alex\.claude\skills\judgment-day\SKILL.md |
| When user asks to create a new skill, add agent instructions, or document patterns for AI. | skill-creator | C:\Users\Alex\.claude\skills\skill-creator\SKILL.md |
| When the user mentions "worktree", "git worktree", multiple working folders, or asks to create/remove/visualize parallel checkouts. | git-worktree | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\git-worktree\SKILL.md |
| When writing, modifying, or executing tests in ZeroRadius — any layer. Also triggers automatically before any git commit on feat, fix, or refactor. | zero-radius-testing | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\zero-radius-testing\SKILL.md |
| Cuando el usuario pide revisar el servidor, hacer pruebas remotas o diagnosticar ZeroRadius en el server. | remote-diag | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\remote-diag\SKILL.md |
| Use when the user wants to quickly describe what they want to build and get a complete proposal with design, specs, and tasks ready for implementation. | openspec-propose | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-propose\SKILL.md |
| Use when the user wants to start implementing, continue implementation, or work through tasks. | openspec-apply-change | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-apply-change\SKILL.md |
| Use when the user wants to think through something before or during a change. | openspec-explore | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-explore\SKILL.md |
| Use when the user wants to finalize and archive a change after implementation is complete. | openspec-archive-change | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-archive-change\SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### go-testing
- Prefer table-driven tests with `t.Run` subtests for multiple cases.
- Test Bubbletea state transitions via `Model.Update()`; use teatest for full flows.
- Use golden files only for stable rendered output; support explicit update flow.
- Mock side effects behind interfaces; use `t.TempDir()` for filesystem work.
- Standard commands: `go test ./...`, `go test -run Name`, `go test -cover`, `go test -short`.

### issue-creation
- Always search for duplicates before creating a new issue.
- Blank issues are disabled; MUST use the repo bug or feature template.
- New issues get `status:needs-review`; no PR before maintainer adds `status:approved`.
- Questions belong in Discussions, not Issues.
- Use conventional-commit style titles like `fix(scope): ...` or `feat(scope): ...`.

### branch-pr
- Every PR MUST link an approved issue and include exactly one `type:*` label.
- Branch names MUST match `type/description` with lowercase `a-z0-9._-` only.
- Commit messages MUST follow conventional commits; never add AI attribution.
- Run required checks before opening or merging; shell scripts need shellcheck.
- PR body must include issue linkage, summary bullets, file table, and test plan.

### judgment-day
- Resolve project standards from the skill registry BEFORE launching judges.
- Launch two blind judges in parallel; never let them know about each other.
- Treat findings as confirmed only when both judges agree.
- Re-judge after confirmed critical fixes; theoretical warnings are info only.
- After two fix rounds, stop and ask the user whether to continue iterating.

### skill-creator
- Create a skill only for reusable, non-trivial patterns.
- Use complete frontmatter with `name`, `description`, license, and metadata.
- Put actionable rules first; keep examples minimal and focused.
- Prefer local `references/` over duplicating docs or linking web URLs.
- Register every new skill in `AGENTS.md` after creation.

### git-worktree
- One branch can exist in only one worktree at a time.
- Prefer `git worktree add -b <branch>` when creating a new worktree.
- Verify path and branch before removing a worktree.
- On Windows/OneDrive lock failures, close editors, retry, then prune stale metadata.
- Use directory junctions for local `.agents/` tooling instead of copying it into worktrees.

### zero-radius-testing
- After any feat/fix/refactor, run the full relevant ZeroRadius test layer before commit.
- Never hide skipped tests; report exactly what ran, passed, failed, and coverage.
- Backend default fast path: `./scripts/test-backend-fast.sh`; frontend: `./scripts/test-frontend-fast.sh`.
- Schema or model changes REQUIRE `tests/unit/test_schema_sync.py`.
- Frontend tests use Vitest + Testing Library + MSW v2; pages using toast state must render under `ToastProvider`.

### remote-diag
- Use the dedicated SSH identity `~/.ssh/id_zeroradius_diag` for remote access.
- Work in `~/radius` on host `192.168.1.212` as user `alex`.
- Check container and DB health before backend operations.
- Prefer targeted `docker-compose restart <service>` and logs over destructive resets.
- Never expose passwords in logs; use `sudo` only when strictly necessary and explain why.

### openspec-propose
- Do not proceed without a clear change description or change name.
- Create the change, then generate artifacts in dependency order until apply-ready.
- Read dependency artifacts before writing the next artifact.
- Use templates and instruction payloads as constraints, not literal output.
- If the change already exists, ask whether to continue it or create a new one.

### openspec-apply-change
- Select the correct active change before implementation; never guess when ambiguous.
- Read all context files returned by OpenSpec instructions before editing code.
- Implement tasks minimally and mark each task complete immediately.
- Pause on ambiguity, blockers, or design mismatches instead of improvising.
- On completion, report session progress and whether the change is archive-ready.

### openspec-explore
- Explore mode is for thinking, not implementation.
- Read code and artifacts freely, but do not write production code.
- Use diagrams, comparisons, and tradeoff framing to clarify options.
- If a decision crystallizes, offer to capture it in proposal/spec/design/tasks.
- If the user wants implementation, tell them to exit explore mode first.

### openspec-archive-change
- Never guess the target change when multiple active changes exist.
- Warn about incomplete artifacts or tasks, but allow archive after explicit confirmation.
- Assess delta spec sync before archiving and show the combined impact summary.
- Archive into `openspec/changes/archive/YYYY-MM-DD-<change>/` preserving metadata.
- Report whether specs were synced, skipped, or not applicable.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\AGENTS.md | Index — references files below |
| zero-radius-diagnose | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\zero-radius-diagnose\SKILL.md | Referenced by AGENTS.md; path currently missing |
| zero-radius-testing | C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\zero-radius-testing\SKILL.md | Referenced by AGENTS.md |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
