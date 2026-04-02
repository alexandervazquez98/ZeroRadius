# Skill Registry — radius-gestor

Generated: 2026-04-02

## Global Skills (`~/.config/opencode/skills/`)

| Name | Path | Trigger |
|------|------|---------|
| `sdd-init` | `C:/Users/Alex/.config/opencode/skills/sdd-init/SKILL.md` | Initialize SDD context in any project |
| `sdd-explore` | `C:/Users/Alex/.config/opencode/skills/sdd-explore/SKILL.md` | Explore/investigate ideas before committing to a change |
| `sdd-propose` | `C:/Users/Alex/.config/opencode/skills/sdd-propose/SKILL.md` | Create change proposal with intent, scope, and approach |
| `sdd-spec` | `C:/Users/Alex/.config/opencode/skills/sdd-spec/SKILL.md` | Write specifications with requirements and scenarios |
| `sdd-design` | `C:/Users/Alex/.config/opencode/skills/sdd-design/SKILL.md` | Create technical design document with architecture decisions |
| `sdd-tasks` | `C:/Users/Alex/.config/opencode/skills/sdd-tasks/SKILL.md` | Break down a change into implementation task checklist |
| `sdd-apply` | `C:/Users/Alex/.config/opencode/skills/sdd-apply/SKILL.md` | Implement tasks from a change following specs and design |
| `sdd-verify` | `C:/Users/Alex/.config/opencode/skills/sdd-verify/SKILL.md` | Validate implementation matches specs, design, and tasks |
| `sdd-archive` | `C:/Users/Alex/.config/opencode/skills/sdd-archive/SKILL.md` | Sync delta specs to main specs and archive completed change |
| `skill-creator` | `C:/Users/Alex/.config/opencode/skills/skill-creator/SKILL.md` | Create new AI agent skills |
| `go-testing` | `C:/Users/Alex/.config/opencode/skills/go-testing/SKILL.md` | Go testing patterns, Bubbletea TUI testing |

## Project Skills (`.agents/skills/`)

| Name | Path | Trigger |
|------|------|---------|
| `zero-radius-testing` | `.agents/skills/zero-radius-testing/SKILL.md` | Writing/modifying/executing tests — any layer. Auto-triggers before git commit on feat/fix/refactor |
| `openspec-explore` | `.agents/skills/openspec-explore/SKILL.md` | Explore mode — thinking partner for ideas, investigation, requirements |
| `openspec-propose` | `.agents/skills/openspec-propose/SKILL.md` | Propose new change with all artifacts in one step |
| `openspec-apply-change` | `.agents/skills/openspec-apply-change/SKILL.md` | Implement tasks from an OpenSpec change |
| `openspec-archive-change` | `.agents/skills/openspec-archive-change/SKILL.md` | Archive a completed change in the experimental workflow |
| `sdd-versioning` | `.agents/skills/sdd-versioning/SKILL.md` | Semantic versioning and changelog generation upon closing SDD feature |
| `webapp-testing` | `.agents/skills/webapp-testing/SKILL.MD` | Interact with and test local web apps using Playwright |

## Standalone Skills (`.agents/`)

| Name | Path | Trigger |
|------|------|---------|
| `zero-radius-diagnose` | `.agents/zero-radius-diagnose/SKILL.md` | Diagnóstico y operación remota de servidor de prueba ZeroRadius |

## Convention Files (Project Root)

| File | Purpose |
|------|---------|
| `AGENTS.md` | Local skill registry index — references skill files |

## Skill Lookup Quick Reference

| Context | Load |
|---------|------|
| Writing any tests (frontend/backend/E2E) | `zero-radius-testing` |
| Before any commit (feat/fix/refactor) | `zero-radius-testing` |
| Diagnosing remote test server (192.168.1.212) | `zero-radius-diagnose` |
| SDD phase: explore | `sdd-explore` |
| SDD phase: propose | `sdd-propose` |
| SDD phase: spec | `sdd-spec` |
| SDD phase: design | `sdd-design` |
| SDD phase: tasks | `sdd-tasks` |
| SDD phase: apply | `sdd-apply` |
| SDD phase: verify | `sdd-verify` |
| SDD phase: archive | `sdd-archive` |
| Version bump / CHANGELOG | `sdd-versioning` |
| Creating new skills | `skill-creator` |
| Testing web app in browser | `webapp-testing` |
