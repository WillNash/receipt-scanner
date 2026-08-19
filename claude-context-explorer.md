# Codebase Explorer Findings

## Where skills live

The active user is `devuser`. The Claude config home is `/home/devuser/.claude/`.

Will's personal plugin lives at:
```
/home/devuser/.claude/plugins/wills-plugins/
```

The new skill should be created at:
```
/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/ux-dev/SKILL.md
```

---

## Skill file format

Skills are Markdown files with YAML frontmatter. The minimum required fields are:

```yaml
---
name: ux-dev
description: <detailed activation description with positive and negative examples>
version: 1.0.0
---
```

The `description` field is the most important — it is what the model reads to decide when to activate the skill. Existing skills include long, specific descriptions with explicit trigger phrases and explicit exclusions.

---

## Pattern from existing skills (flutter-dev, python-dev, aws-sa)

All three follow this structure inside the Markdown body:

1. H1 persona title
2. Mindset section — bold-labeled bullet principles, ordered by priority
3. Domain-specific rule sections — tables, decision trees, code examples
4. Anti-Patterns — numbered table with anti-pattern name, risk, and remediation
5. How to Respond — explicit behavior rules for each request type (new feature, review, choice, explanation, user override)

The tone is first-person senior expert, prescriptive and opinionated. No hedging. Rules state trade-offs explicitly.

---

## Existing UX/design coverage

The official marketplace has a `frontend-design` skill at `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`. It covers visual aesthetic choices for web pages — palette, typography, layout, CSS, copy. It does NOT cover UX methodology, interaction design principles, information architecture, accessibility as a design discipline, design systems, or user research. There is no overlap risk.

Will's plugin has no UX or design skill at all.

---

## Files examined

- `/home/devuser/.claude/plugins/installed_plugins.json`
- `/home/devuser/.claude/plugins/wills-plugins/.claude-plugin/marketplace.json`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/.claude-plugin/plugin.json`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/flutter-dev/SKILL.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/python-dev/SKILL.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/aws-sa/SKILL.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/agent-pipeline/SKILL.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/agents/explorer.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/agents/planner.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/agents/reviewer.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/agents/researcher.md`
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/agents/glue-expert.md`
- `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`
- `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/.claude-plugin/plugin.json`
- `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/references/schemas.md`
