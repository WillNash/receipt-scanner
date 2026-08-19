# Research Findings

## Sources

- Nielsen Norman Group - 10 Usability Heuristics
- Nielsen Norman Group - Information Architecture Study Guide
- WCAG 2 Overview - W3C WAI
- Web Content Accessibility Guidelines (WCAG) 2.2
- Gestalt Principles of Design - UXcam
- The 10 UX Deliverables Top Designers Use - Toptal
- Cross-Platform UX - UXPin
- Designing for Voice User Interfaces - Smashing Magazine
- Agent Skills Overview - Anthropic Platform Docs
- Skill Authoring Best Practices - Anthropic Platform Docs
- Extend Claude with Skills - Claude Code Docs
- Create Custom Sub-Agents - Claude Code Docs
- How to Conduct a Heuristic Evaluation - Maze

---

## Core Concepts

### 1. Nielsen's 10 Usability Heuristics

The canonical framework for expert UX review (heuristic evaluation). Each is a general principle, not a rigid rule. Use the 0-4 severity scale: 0 = not a problem, 4 = usability catastrophe.

1. **Visibility of System Status** — Keep users informed via timely, appropriate feedback.
2. **Match Between System and the Real World** — Use the user's language; follow real-world conventions.
3. **User Control and Freedom** — Provide clear "emergency exits" (undo, back, cancel) without extended processes.
4. **Consistency and Standards** — Follow platform and industry conventions; different words should not mean the same thing.
5. **Error Prevention** — Design to prevent problems before they occur; prefer good defaults and confirmation dialogs over error recovery.
6. **Recognition Rather Than Recall** — Make options and actions visible; users should not have to remember info from one screen to use another.
7. **Flexibility and Efficiency of Use** — Offer accelerators (shortcuts, saved settings, gestures) for expert users while keeping the novice path clear.
8. **Aesthetic and Minimalist Design** — Every extra unit of information competes with relevant content; remove the irrelevant.
9. **Help Users Recognize, Diagnose, and Recover from Errors** — Error messages must be plain-language, precise about the problem, and constructively suggest a solution.
10. **Help and Documentation** — If help is needed, it must be easy to find, task-focused, and concise.

---

### 2. Gestalt Principles

Describe how humans perceive and group visual information. Applied to create clear visual hierarchy and grouping.

- **Proximity** — Elements close together are perceived as a group. Use whitespace deliberately to create logical clusters.
- **Similarity** — Elements sharing color, shape, or size appear related. Use consistently to signal category membership.
- **Continuity** — The eye follows the smoothest path; alignment and flow guide attention.
- **Closure** — The mind completes incomplete shapes; enables clean minimal icons.
- **Figure/Ground** — Elements are perceived as foreground or background; contrast and layering create depth and focus.
- **Symmetry** — Symmetrical elements read as a unit; implies stability.
- **Praegnanz (Simplicity)** — The mind simplifies complex shapes to the simplest possible interpretation; prefer the simplest solution that communicates correctly.
- **Common Fate** — Elements moving together are perceived as related; critical for animation and transition design.

---

### 3. Accessibility: WCAG 2.2

Current standard. Organized under 4 principles (POUR):

1. **Perceivable** — Content available to at least one sense. Key requirements: text alternatives for non-text content, captions for audio/video, color contrast 4.5:1 for normal text and 3:1 for large text (AA level), never use color alone to convey information.
2. **Operable** — All functionality reachable by keyboard. No timing traps. No content flashing more than 3 times/sec. Meaningful page titles and logical focus order.
3. **Understandable** — Language identified in markup. Consistent navigation and labeling. Error identification and suggested corrections.
4. **Robust** — Valid markup. Name, role, and value exposed to assistive technologies.

Conformance levels: A (minimum), AA (standard legal/enterprise target), AAA (aspirational).

Key WCAG 2.2 additions:
- **2.4.11 Focus Not Obscured (AA)** — Focused component not fully hidden by sticky headers.
- **2.5.7 Dragging Movements (AA)** — Every drag operation must have a single-pointer alternative.
- **2.5.8 Target Size (AA)** — Minimum 24x24 CSS pixels for interactive targets.
- **3.3.7 Redundant Entry (A)** — Do not ask users to re-enter information already provided in the session.
- **3.3.8 Accessible Authentication (AA)** — No cognitive function test for login unless an alternative or assistance is provided.

---

### 4. Information Architecture Fundamentals

IA is the structural design of shared information environments. The Morville and Rosenfeld framework frames it as the intersection of Users, Content, and Context.

Four core systems:
- **Organization** — How content is categorized: hierarchical, sequential, matrix, or faceted.
- **Labeling** — How items and categories are named; must match users' mental models, not internal system terminology.
- **Navigation** — How users move through the structure: global nav, local nav, contextual links, breadcrumbs.
- **Search** — How users search; indexing, filtering, faceted search design.

Key concepts:
- **Mental models** — Users' expectations of how content is organized, revealed through card sorting. IA must align with these.
- **Findability** — Can a user locate a known item? Tested via tree testing.
- **Discoverability** — Can a user encounter unknown but relevant items while browsing?
- **Information scent** — Degree to which link text and labels signal the user is on the right path. Vague labels ("Learn More", "Click here") eliminate scent entirely.
- **Wayfinding** — Design cues (breadcrumbs, active nav states, progress indicators) that tell users where they are and how to navigate back.

Research methods: open card sort (reveals mental models), closed card sort (validates existing structure), tree testing (validates proposed hierarchy without visual design).

---

### 5. User-Centered Design Process

An iterative cycle. Phases are not strictly sequential; teams loop back as new information emerges.

| Phase | Goal | Key Activities |
|---|---|---|
| Discovery / Research | Understand users, context, and the actual problem | Stakeholder interviews, user interviews, surveys, contextual inquiry, analytics review, competitive analysis |
| Define | Frame the right problem | Affinity mapping, HMW statements, personas, jobs-to-be-done, problem statements |
| Ideation | Generate diverse solution concepts | Sketching, Crazy 8s, design studio, service blueprints, IA drafts |
| Prototype | Make ideas tangible enough to test | Paper sketches to lo-fi wireframes to interactive hi-fi prototypes |
| Test | Validate with real users on real tasks | Moderated usability testing, unmoderated remote testing, A/B tests, heuristic evaluation, accessibility audit |
| Implement and Measure | Ship and track outcomes | Developer handoff, annotated specs, design QA, post-launch research |

5 users per group surfaces approximately 85% of usability issues (Nielsen). Different tasks and different user segments require separate rounds.

---

### 6. Common UX Deliverables

| Deliverable | Purpose |
|---|---|
| Research report | Documents user research findings; grounds decisions in evidence |
| Personas | Archetypal user profiles: goals, behaviors, frustrations, context of use. Must be research-derived. |
| Sitemap / IA diagram | Hierarchical map of all content and sections |
| User flow | Step-by-step path a user takes to complete a specific task, including decision branches |
| Journey map | End-to-end visualization across touchpoints over time, including emotional states |
| Service blueprint | Extends journey map to backstage processes and organizational actors |
| Wireframe | Grayscale blueprint of layout, content hierarchy, and interaction; no color or final typography |
| Interactive prototype | Clickable simulation for user testing |
| Heuristic evaluation report | Expert review against heuristics; severity-rated issue list with recommendations |
| Usability test report | Findings from observed user sessions; issues ranked by frequency and severity |
| Accessibility audit | WCAG conformance checklist; flagged violations with remediation guidance |
| Design system / style guide | Canonical component library, design tokens, usage rules |

---

### 7. Platform-Agnostic UX Principles

These apply regardless of medium — web, native mobile, desktop, voice, TV, kiosk.

- **Clarity over cleverness** — The interface should immediately communicate what it is and what the user can do.
- **Match the user's mental model** — Organize and label content the way users think about it, not the way the system is built.
- **Progressive disclosure** — Show only what is needed for the current task; reveal complexity on demand.
- **Feedback and status** — Every action must produce a perceivable response matched to the modality (visual, haptic, audio, spoken).
- **Reversibility** — Users make mistakes on every platform. Undo, cancel, go-back, and confirmation dialogs are universally required.
- **Affordances match input modality** — Touch targets sized for fingers. Voice needs spoken confirmation. Desktop may use hover states. Keyboard must reach everything.
- **Consistent navigation and labeling** — Predictability reduces learning overhead on any platform.
- **Accessible by default** — Contrast, text scaling, keyboard access, and semantic markup are baseline quality requirements, not optional.
- **Content first** — Content and user goals drive layout; navigation chrome serves content, not the reverse.
- **Context of use** — Design accounts for where and how the user is interacting: ambient noise, sunlight, one-handed use, no persistent screen.

Platform-specific distinctions:

| Platform | Key UX Distinctions |
|---|---|
| Web | URLs are canonical and shareable; responsive layout; hover states available; back button behavior must be handled correctly |
| Native mobile | Touch-first, thumb-zone layout; OS gesture conventions must be respected; app lifecycle (backgrounding, interruption) |
| Desktop (native) | Keyboard shortcuts critical; dense information displays acceptable; multi-window workflows; drag-and-drop; right-click context menus |
| Voice / VUI | No persistent visual state; navigation is time-based and sequential, not spatial; short prompts; explicit spoken confirmation of destructive actions; no re-reading; system must manage short-term memory for the user |
| TV / 10-foot UI | D-pad/remote navigation only; very large type; high contrast; minimal text input; lean-back context; unmistakable focus states |
| Kiosk / embedded | Hostile environment; fail-safe defaults; no persistent login; very large touch targets; auto-reset sessions |

---

### 8. Claude Code Skill File Format

#### File locations

| Path | Scope |
|---|---|
| `~/.claude/skills/<skill-name>/SKILL.md` | Personal; available in all projects |
| `.claude/skills/<skill-name>/SKILL.md` | Project-level; can be checked into repo |
| `.claude/commands/<skill-name>.md` | Legacy command format; still works but lacks frontmatter features |

The directory name becomes the `/skill-name` slash command.

#### Three-level progressive disclosure

- **Level 1: Metadata** (always pre-loaded, ~100 tokens per skill) — `name` + `description` from frontmatter. Claude reads these for all installed skills at startup to decide whether to trigger.
- **Level 2: Instructions** (loaded when triggered) — The full SKILL.md body. Keep under 500 lines.
- **Level 3: Resources** (loaded as needed) — Bundled files referenced from SKILL.md. Zero token cost until accessed.

Keep all file references **one level deep** from SKILL.md to prevent partial reads.

#### Required frontmatter fields

| Field | Constraints |
|---|---|
| `name` | Max 64 chars; lowercase letters, numbers, hyphens only; no XML tags; cannot contain "anthropic" or "claude" |
| `description` | Max 1,024 chars; non-empty; no XML tags; must state both WHAT it does AND WHEN to use it; always third person |

#### Optional frontmatter fields (Claude Code)

| Field | Type | Description |
|---|---|---|
| `model` | string | `sonnet`, `opus`, `haiku`, `fable`, full model ID, or `inherit` (default) |
| `tools` | array | Allowlist of tools the skill may use; omitting inherits all available tools |
| `disallowedTools` | array | Denylist; removes tools from the inherited set |
| `disable-model-invocation` | boolean | `true` = only user can invoke via `/skill-name`; Claude will not auto-trigger |
| `context` | string | `fork` (inherits main conversation context) or `subagent:<name>` |
| `permissionMode` | string | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan`, or `manual` |
| `maxTurns` | number | Maximum agentic turns before stopping |

#### Available tool names for the `tools` field

```
Read, Write, Edit, Glob, Grep, Bash, PowerShell,
WebFetch, WebSearch, Agent, Skill, Task,
TodoRead, TodoWrite, NotebookEdit, Monitor,
mcp__<server>, mcp__<server>__<tool>, mcp__<server>__*
```

---

## Gotchas & Warnings

### Skill file format

- The `description` field is the sole auto-trigger mechanism. A vague description like "helps with design" will cause the skill to never fire or to fire on unrelated requests. Include explicit trigger phrases.
- Always write `description` in **third person**. The description is injected verbatim into the system prompt; first or second person causes discovery failures.
- `name` must be lowercase with hyphens only. No underscores, spaces, or uppercase. Max 64 characters.
- `disable-model-invocation: true` is required for skills with side effects.
- Keep SKILL.md body under **500 lines**. Move large reference content to linked files.
- File references should be **one level deep** from SKILL.md.
- The `tools` field is an **allowlist**. Omitting it grants the skill access to all tools.
- Legacy `.claude/commands/` files still work but lack frontmatter features.

### UX practice

- Nielsen's severity ratings must be assigned **independently** by each evaluator before consolidation. Discussing ratings first introduces anchoring bias.
- WCAG 2.2 supersedes WCAG 2.1 and 2.0. Target 2.2 AA as the baseline for new work.
- WCAG AA contrast (4.5:1) applies to text under 18pt regular or 14pt bold. Large text requires 3:1. UI component boundaries require 3:1 against adjacent colors.
- Personas without supporting research data are fictional characters. Label them explicitly as "proto-personas" or "assumption personas" to prevent stakeholders from treating them as evidence.
- Journey maps should represent **one persona's path through one scenario**. A map covering all users loses specificity.
- Wireframes should omit color, final typography, and imagery to keep feedback focused on structure and interaction, not aesthetics.
- "5 users find 85% of issues" applies to **one task flow and one homogeneous user group**. Different tasks and different segments require separate rounds.
- VUI design is temporal, not spatial. Users navigate through time and sound rather than space and sight. The system must proactively manage short-term memory on the user's behalf; users cannot re-read a spoken response.
