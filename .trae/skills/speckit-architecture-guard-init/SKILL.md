---
name: speckit-architecture-guard-init
description: 'Initialize or update the Project Constitution for Architecture Guard. Creates the governance and architecture constitutions used by the architecture-guard extension for review.'
compatibility: Requires spec-kit project structure with .specify/ directory and architecture-guard extension v1.8.9+
metadata:
  author: DyanGalih
  source: architecture-guard:commands/init.md
---

# speckit.architecture-guard.init

Initialize the Project Constitution for Architecture Guard. This command bootstraps the governance and architecture constitutions used as the source-of-truth for downstream review, planning, and refactor-generation commands.

## Usage

```
/speckit.architecture-guard.init
```

## Process

1. **Detect Project Type**: Identify the project's primary language/framework (Python/FastAPI, Node/Express, etc.) and select the appropriate preset from `presets/`.
2. **Generate Governance Constitution**: Create `.specify/memory/governance_constitution.md` from the chosen preset, covering:
   - Project identity and scope
   - Coding standards
   - Testing policy
   - Documentation requirements
3. **Generate Architecture Constitution**: Create `.specify/memory/architecture_constitution.md` covering:
   - Module layering (e.g., `infra ← biz ← api`)
   - Boundary rules (which modules may import which)
   - Dependency direction
   - Contract layer requirements
4. **Review with User**: Present both constitutions to the user for confirmation before writing.

## Templates

The extension provides:
- [architecture_constitution.md](file:///e:/DEMO/AI/ontology-graphiti/.specify/extensions/architecture-guard/templates/architecture_constitution.md) — Architecture-specific template
- [constitution.md](file:///e:/DEMO/AI/ontology-graphiti/.specify/extensions/architecture-guard/templates/constitution.md) — Generic governance template

## Presets

Available framework presets at `presets/`:
- `springboot.md` — Spring Boot (Java)
- `nestjs.md` — NestJS (TypeScript)
- `nextjs.md` — Next.js (TypeScript)
- `django.md` — Django (Python)
- `laravel.md` — Laravel (PHP)
- `expressjs.md` — Express.js
- `react.md`, `vue.md`, `nuxtjs.md` — Frontend frameworks

## Example Output

```text
.specify/memory/
├── constitution.md              # Existing project constitution
├── governance_constitution.md   # NEW: architecture-guard governance rules
└── architecture_constitution.md # NEW: architecture-guard boundary rules
```

## Notes

- This command is **non-destructive** — it does not overwrite existing constitutions without explicit user confirmation
- Re-running this command is safe; it merges new preset content with existing customizations
- The generated constitutions are read by `architecture-review`, `violation-detection`, and `refactor-generator` commands
