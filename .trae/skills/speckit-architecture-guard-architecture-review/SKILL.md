---
name: speckit-architecture-guard-architecture-review
description: 'Perform a framework-agnostic architecture review validating implementation against spec.md, plan.md, tasks.md, and the governance and architecture constitutions.'
compatibility: Requires spec-kit project structure with .specify/ directory and architecture-guard extension v1.8.9+
metadata:
  author: DyanGalih
  source: architecture-guard:commands/architecture-review.md
---

# speckit.architecture-guard.architecture-review

Run a post-implementation architecture review validating code against spec, plan, tasks, and the project constitutions.

## Usage

```
/speckit.architecture-guard.architecture-review [scope]
```

**Scope**: Optional — `specs/NNN-feature-name/`, file path, or "all changes". Defaults to the latest feature.

## Operating Constraints

- **STRICTLY READ-ONLY**: This command is analytical. Do **not** modify any files.
- **Progressive Disclosure**: Load context incrementally. Start with manifests and design artifacts before deep-diving into implementation code.
- **Evidence-Based**: Every violation must cite specific "Implementation Evidence" (file paths, line numbers, or code patterns) or its absence.

## Process

1. **Read Artifacts** in this order:
   - `specs/NNN-feature/spec.md` — User requirements and acceptance scenarios
   - `specs/NNN-feature/plan.md` — Technical design
   - `specs/NNN-feature/tasks.md` — Task breakdown
   - `.specify/memory/constitution.md` — Project constitution
   - `.specify/memory/architecture_constitution.md` — Architecture rules (if exists)
   - `.specify/memory/governance_constitution.md` — Governance rules (if exists)

2. **Framework-Agnostic Review** (always applied):
   - Universal boundary concepts: Entry, App, Domain, Data, External
   - Module layering: `infra ← biz ← api`
   - Dependency direction enforcement
   - Cross-cutting concerns placement

3. **Framework-Aware Review** (preset-driven):
   - Apply framework-specific rules from the active preset
   - Validate framework conventions (e.g., controllers in ExpressJS, services in Spring Boot)

4. **Generate Architecture Review Report** with:
   - ✅ Compliant items
   - ⚠️ Drift candidates (low confidence, no clear violation)
   - ❌ Violations with file/line evidence
   - 📊 Drift score (0-100)

5. **Output Refactor Tasks** (non-blocking):
   - Convert each violation into a structured refactor task
   - Tasks go to `specs/NNN-feature/checklist-review.md`

## Sub-Agent Delegation

When codebase is large (≥50 files OR ≥10,000 lines), consider delegating to a sub-agent for parallel analysis. Otherwise run inline.

## Output Format

```text
# Architecture Review: [feature-name]

## Summary
- Files reviewed: N
- Spec compliance: X/Y scenarios
- Boundary violations: N
- Drift score: 85/100

## Findings
### Critical (block release)
- [file:line] Description — Evidence — Recommended fix

### Important (block merge)
- ...

### Suggestions
- ...
```

## Notes

- This command runs automatically as a post-implementation hook (configured in extension.yml)
- Output is **non-blocking** — review results do not fail CI/CD
- Use `/speckit.architecture-guard.architecture-verify` for a stricter verification gate
