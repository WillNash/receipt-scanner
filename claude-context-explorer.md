# Explorer Findings — Flutter Dev Skill

## Skill Location

All skills live under:
`/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/`

The new skill must be created at:
**`/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/flutter-dev/SKILL.md`**

The `commands/flutter-dev/` directory does not yet exist. No changes to `plugin.json` or `marketplace.json` are needed — the plugin auto-discovers commands by directory structure.

## Skill File Format

Every skill is a Markdown file with YAML frontmatter. Required fields:

```yaml
---
name: flutter-dev
description: <activation description — most critical field>
version: 1.0.0
---
```

The `description` field is Claude's activation gate. Must include:
- Explicit trigger phrases: "write Flutter", "review this widget", "build a screen"
- Implicit topic triggers: `.dart` files, widget tree, state management, pubspec.yaml, BLoC, Riverpod, go_router
- Optionally: what NOT to activate for

## Skill Body Structure (from existing skills)

Both `python-dev` and `aws-sa` follow:

1. H1 title (role name)
2. Role statement (2–3 sentences on values and decision-making priority)
3. Mindset section (5–8 bold-lead bullet points)
4. Technical content sections (style rules, patterns to use with examples, patterns to avoid, tooling)
5. "How to Respond" section — explicit per-scenario response rules (writing, reviewing, explaining, comparisons, pushback)

## Quality Benchmark

Gold standard: `aws-sa/SKILL.md` (v1.1.0, ~376 lines):
- Service decision flowcharts
- Pipe tables for routing decisions
- Anti-patterns with named remediation actions
- Deprecated services table
- Key production gotchas

`python-dev/SKILL.md` — shorter, more concise, inline code examples.

Target for Flutter skill: closer to `aws-sa` depth — state management routing table, widget lifecycle gotchas, anti-patterns with remediation, response rules.

## No Flutter Code in Active Repo

The active repo is a Python/Terraform AWS backend. All Flutter skill content is authored from knowledge + researcher findings.
