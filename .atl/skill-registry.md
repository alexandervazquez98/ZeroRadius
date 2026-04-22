# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When creating a pull request, opening a PR, or preparing changes for review | `branch-pr` | `C:\Users\Alex\.config\opencode\skills\branch-pr\SKILL.md` |
| When writing Go tests, using teatest, or adding test coverage | `go-testing` | `C:\Users\Alex\.config\opencode\skills\go-testing\SKILL.md` |
| When creating a GitHub issue, reporting a bug, or requesting a feature | `issue-creation` | `C:\Users\Alex\.config\opencode\skills\issue-creation\SKILL.md` |
| When user says “judgment day” / adversarial dual review keywords | `judgment-day` | `C:\Users\Alex\.config\opencode\skills\judgment-day\SKILL.md` |
| When user asks to create a new skill or agent instructions | `skill-creator` | `C:\Users\Alex\.config\opencode\skills\skill-creator\SKILL.md` |
| When user mentions worktree / parallel folders / create-remove worktree | `git-worktree` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\git-worktree\SKILL.md` |
| When user wants to start/continue implementing OpenSpec tasks | `openspec-apply-change` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-apply-change\SKILL.md` |
| When user wants to finalize/archive an OpenSpec change | `openspec-archive-change` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-archive-change\SKILL.md` |
| When user wants to think through ideas before/during change | `openspec-explore` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-explore\SKILL.md` |
| When user wants one-step OpenSpec proposal generation | `openspec-propose` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\openspec-propose\SKILL.md` |
| When writing/modifying/running tests in ZeroRadius (auto for feat/fix/refactor) | `zero-radius-testing` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\zero-radius-testing\SKILL.md` |

## Compact Rules

### branch-pr
- Every PR MUST link an approved issue (`status:approved`) and include exactly one `type:*` label.
- Branch names MUST match `type/description` (`feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert`).
- Use conventional commits; no invalid types/scopes.
- Run shellcheck on modified scripts before PR.
- PR body must include issue linkage (`Closes/Fixes/Resolves #N`) and concise summary/test plan.

### go-testing
- Use table-driven tests as default for Go logic.
- Test Bubbletea state transitions via `Model.Update()` and message simulation.
- For TUI integration, use `teatest.NewTestModel` and assert final model state.
- Use golden files for stable `View()` output snapshots when UI text/layout matters.
- Cover both success and error paths explicitly.

### issue-creation
- Use template-based issues only (bug_report.yml or feature_request.yml); blank issues are blocked.
- New issues enter with `status:needs-review`; PRs wait until maintainer adds `status:approved`.
- Ask contributors to check duplicates before opening.
- Route Q&A to Discussions, not Issues.
- Keep required fields complete (repro, expected/actual, env, affected area).

### judgment-day
- Run two blind parallel judges (same target, no cross-talk), then synthesize confirmed/suspect findings.
- Resolve/inject project standards from skill registry before launching judges.
- Classify warnings as **real** vs **theoretical**; theoretical issues are informational.
- Ask user before fixing confirmed issues after Round 1.
- Re-judge after critical fixes; escalate to user after 2 iterations if issues persist.

### skill-creator
- Create skills only for reusable, recurring patterns; avoid one-off or duplicate documentation.
- Follow strict SKILL.md frontmatter (`name`, `description+Trigger`, `license`, `metadata`).
- Keep critical patterns actionable and concise; avoid fluff.
- Prefer local references (`references/`) over external URLs.
- Register new skills in project agent index (e.g., AGENTS.md).

### git-worktree
- One branch per worktree; don’t checkout same branch in multiple worktrees.
- Prefer `git worktree add -b <branch>` when creating new worktrees.
- Verify path/branch before removal.
- On Windows lock errors, close handles then retry; if needed, remove stale admin dir and `git worktree prune`.
- Keep branch hygiene: short-lived feature/fix branches, local `wip/*` for unfinished work.

### openspec-apply-change
- Select change explicitly (infer only when unambiguous); announce selected change.
- Read `openspec status --json` and `openspec instructions apply --json` before coding.
- Read all `contextFiles` first; don’t assume fixed artifact names.
- Implement tasks sequentially and update task checkboxes immediately.
- Pause and ask on ambiguity/blockers instead of guessing.

### openspec-archive-change
- Never auto-guess change to archive; prompt user selection when not explicit.
- Check incomplete artifacts/tasks and warn; proceed only with user confirmation.
- Assess delta spec sync status before archive and present sync options.
- Archive to date-prefixed folder under `openspec/changes/archive/`.
- Preserve clear summary of schema, location, sync result, and warnings.

### openspec-explore
- Explore mode is thinking/investigation only: read/search freely, no implementation.
- Use adaptive questioning and diagrams; don’t force rigid questionnaires.
- Ground analysis in real code paths and existing artifacts.
- Offer artifact capture (proposal/design/spec/tasks) when decisions crystallize.
- If user asks implementation, request leaving explore mode first.

### openspec-propose
- Derive or confirm a clear change scope/name before creating artifacts.
- Create change scaffold first, then follow CLI artifact dependency order.
- Use `openspec instructions <artifact> --json`; treat context/rules as constraints, not output text.
- Re-check status after each artifact until `applyRequires` are done.
- Stop to ask user only when context is critically unclear.

### zero-radius-testing
- For `feat`/`fix`/`refactor`, run relevant tests before calling work done.
- Never commit with failing tests; never skip tests silently.
- Prefer wrappers: `./scripts/test-backend-fast.sh`, `./scripts/test-frontend-fast.sh`, `./scripts/test-all.sh`.
- On Windows: use `python -m pytest` and `cmd /c "node_modules\.bin\vitest.cmd run"`.
- Enforce backend coverage floor from `pytest.ini` (`--cov-fail-under=59`) unless explicitly changed with added tests.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| `AGENTS.md` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\AGENTS.md` | Index — references files below |
| `SKILL.md` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\zero-radius-diagnose\SKILL.md` | Referenced by `AGENTS.md` (path not found in current workspace) |
| `SKILL.md` | `C:\Users\Alex\OneDrive\PROGRAMMING\zeroradius\.agents\skills\zero-radius-testing\SKILL.md` | Referenced by `AGENTS.md` |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
