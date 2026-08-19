# Architecture Plan

## Context Summary

Create a new personal wills-skills `frontend-design` skill that covers the visual-design layer of product UI — colour theory, typography systems, design tokens, dark mode, WCAG aesthetic criteria, design system visual critique, and brand voice — complementing (not duplicating) the existing `ux-dev` skill which owns interaction design, WCAG structural criteria, IA, and UX methodology.

---

## Impacted Files

**New file to create:**
- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/frontend-design/SKILL.md`

**No existing files need modification.** The wills-skills plugin loader discovers skills by directory presence. No registry, `plugin.json`, or manifest changes are required.

---

## Relationship to the Official Marketplace Skill

The official marketplace skill at `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md` is a **generative creative tool**: given a design brief, it produces full HTML/CSS artefacts — a compact token system, an ASCII wireframe, a layout concept, and then working code. It also enforces a quality floor while building ("responsive down to mobile, visible keyboard focus, reduced motion respected"). Its activation description is intentionally vague ("Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one") because its job is to generate, not to audit.

The new wills-skills skill is an **analytical critic and systems auditor**: it does not generate artefacts. It audits existing token architectures against their structural invariants (three-tier encapsulation, semantic-only dark-mode remapping), measures contrast ratios against named WCAG criteria, evaluates type scale ratios for mathematical coherence, and assesses brand register consistency across a design system. No code or markup is produced. The distinction is generative vs. analytical, not the presence or absence of accessibility language — the marketplace skill does mention focus and motion, but as a quality floor it enforces while building, not as a systematic audit protocol it can apply to an existing system.

The new skill's trigger description uses terms that do not appear in the marketplace skill's description ("token architecture", "OKLCH", "modular type scale", "three-tier token", "semantic token remapping", "design system visual layer critique") so disambiguation occurs at the description level. The marketplace skill will not match these trigger phrases. No undocumented precedence claim is made.

---

## Scope Boundary (the authoritative map)

| Domain | Owner |
|---|---|
| Colour palette construction (harmonies, OKLCH, hex tokens) | frontend-design (this skill) |
| Primitive → Semantic → Component token architecture | frontend-design (this skill) |
| Dark mode token remapping via semantic tokens only | frontend-design (this skill) |
| Typography: typeface selection, type scale (modular scale ratios), pairing | frontend-design (this skill) |
| WCAG 1.4.3 / 1.4.11 — SHARED: frontend-design owns visual fix (correct colour token value); ux-dev owns structural audit (flag the violation and conformance determination) | SHARED |
| WCAG 1.4.1 (Use of Colour) — SHARED: frontend-design owns visual remediation (select a second signal: icon, pattern, shape, label); ux-dev owns structural detection (flag colour as the sole differentiator) | SHARED |
| WCAG 1.4.4, 1.4.12 — resize text, text spacing | frontend-design (this skill) — visual token and unit choices only |
| Focus indicator visual appearance: colour token value, thickness, offset; providing the token value that achieves required contrast | frontend-design (this skill) |
| Focus indicator conformance determination: WCAG 2.4.7, 2.4.11, 2.4.13 structural compliance | ux-dev |
| Design system visual layer: palette tokens, type tokens, shadow, radius, motion tokens, brand expression | frontend-design (this skill) |
| Brand voice, tone, register, microcopy personality | frontend-design (this skill) |
| NNG four visual token principles: Scale, Visual Hierarchy, Balance, Contrast (as expressed through design tokens) | frontend-design (this skill) |
| Gestalt perceptual grouping critique (proximity, similarity, closure, continuity, figure/ground) | ux-dev |
| CSS custom property two-tier pattern; W3C DTCG format; Style Dictionary v4 | frontend-design (this skill) — advisory only; no code generation |
| Colour harmonies: complementary, analogous, triadic, split-complementary | frontend-design (this skill) |
| Nielsen's 10 usability heuristics, WCAG structural criteria | ux-dev |
| IA, user flows, personas, journey maps, wireframe interaction critique | ux-dev |
| Component API, keyboard model, ARIA annotations | ux-dev |
| UX microcopy as structural interface element (what to say, not how to say it) | ux-dev |
| HTML/CSS implementation | neither — this skill produces design specs and advisory output only |

**Shared-boundary resolution rules (must appear in the skill body):**
- **Focus indicators:** ux-dev owns the conformance determination under WCAG 2.4.13 (focus appearance: indicator area, contrast against adjacent colours). This skill provides the colour token value that achieves the required contrast. When asked "fix the focus ring contrast", this skill names the correct colour values and token changes; it does not write CSS and does not issue the conformance verdict.
- **WCAG 1.4.1:** ux-dev flags that colour is the sole differentiator. This skill specifies what second signal to add (icon, pattern, shape, label) and which tokens to use.
- **WCAG 1.4.3 / 1.4.11:** ux-dev flags the contrast violation. This skill names the corrected token value.
- **Microcopy:** ux-dev owns what the text must say and its functional role. This skill owns tone, brand register, personality, and whether the phrasing fits the brand voice. When asked "is this error message on-brand?", this skill answers. When asked "what should the error message say?", ux-dev answers.
- **Design system critique:** ux-dev evaluates component API, keyboard model, ARIA. This skill evaluates the visual token layer — palette naming, type token structure, shadow and radius tokens, motion token taxonomy, brand expression in component defaults.

---

## Step-by-Step Execution Plan

- **Step 0 — Measure description character count before writing.**
  Run `echo -n "<full description text>" | wc -c` with the exact proposed description. Target under 1,000 characters to leave margin against the 1,024-character hard limit. Condense the "Does NOT activate for" clause to a single redirect sentence if needed: "Does not activate for interaction design, IA, UX methodology, WCAG structural criteria, keyboard model, ARIA, or UX copy content decisions — see the ux-dev skill." Recount after every edit. Do not write the file until the count is confirmed under 1,000 characters.

- **Step 1 — Create the directory.**
  Note: `commands/` frontmatter parsing is confirmed — ux-dev lives at this same path type and its `description` auto-trigger and `tools: [Read]` restriction are observed to work correctly in practice.
  `mkdir /home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/frontend-design`

- **Step 2 — Write `SKILL.md` using the content specification below.**
  File path: `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/frontend-design/SKILL.md`

- **Step 3 — Verify frontmatter validity.**
  `name` field: `frontend-design` (lowercase, hyphens only, under 64 chars). `description` field: third person, confirmed under 1,000 characters from Step 0. `tools` field: `[Read]` only (advisory skill; no file writes needed). `version`: `1.0.0`.

- **Step 4 — Verify line count.**
  `wc -l /home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/frontend-design/SKILL.md` must be under 500. Target: 350–430 lines.

- **Step 5 — Smoke-test activation.**
  In a new Claude Code session, type trigger phrases and confirm this skill (not ux-dev or the marketplace skill) activates.

---

## Detailed Content Specification for the Implementer

### Frontmatter

```yaml
---
name: frontend-design
description: Activates for visual design systems, colour theory, typography, and brand aesthetics. Use when asked to: construct or critique a colour palette; design a token architecture (primitive, semantic, component); audit or fix WCAG contrast criteria (1.4.3, 1.4.4, 1.4.11, 1.4.12); design a type scale or typeface pairing; review the visual layer of a design system (palette tokens, type tokens, shadow, radius, motion); remap tokens for dark mode; assess brand voice, tone, or microcopy register consistency across a design system; or evaluate whether a design reads as distinctive or templated. Also activates for focus indicator appearance (colour token value, thickness, contrast — colour-token advice only; conformance determination belongs to ux-dev). Does not activate for interaction design, IA, UX methodology, WCAG structural criteria, keyboard model, ARIA, or UX copy content decisions — see the ux-dev skill.
tools:
  - Read
version: 1.0.0
---
```

**Description character count must be verified before writing — Step 0 requires a confirmed count under 1,000 characters.**

### Persona / Role Opening

Frame the skill as a senior visual designer and design systems architect. Tone: precise, opinionated, grounded in theory and production craft. Not a generative studio tool — a systematic auditor who can critique a token architecture with the same rigour as a colour palette. This skill produces design specs and remediation guidance; it does not generate HTML, CSS, or code.

Priority order: **Legibility, contrast compliance, typographic consistency, colour integrity, brand coherence, aesthetic distinctiveness.** Aesthetic risk-taking is downstream of all five.

### Mindset Section

Six to eight mindset bullets covering:
- Every visual decision is a communication act — colour, weight, and scale carry semantic load before a user reads a word.
- Token architecture is load-bearing, not cosmetic. A broken token structure means dark mode, theming, and scaling are permanently unreliable.
- Colour is a system, not a palette. Choosing four hex values is not a colour system; mapping them to semantic roles and verifying perceptual behaviour under light/dark, OKLCH uniformity, and all relevant contrast criteria is.
- Typography carries personality and hierarchy simultaneously. A type scale without a modular ratio is arbitrary; arbitrary scales accumulate as technical debt.
- Brand voice is not decoration. Register, tone, and vocabulary are design decisions that determine whether the product reads as trustworthy, playful, authoritative, or indifferent.
- WCAG aesthetic criteria are real constraints. 1.4.3, 1.4.11, 1.4.1, 1.4.4, 1.4.12 are not edge cases — they are the minimum bar for accessible visual design. For 1.4.1 and 1.4.11 as applied to focus rings, this skill provides the corrected token value; ux-dev owns the conformance determination.
- Distinctiveness is earned, not asserted. A design reads as distinctive when every token and layout decision is traceable to a brief; it reads as templated when any similar brief would produce the same result.
- Dark mode is a token problem, not a CSS problem. Only semantic tokens may change between light and dark; primitives are fixed; component tokens inherit from semantics.

### Core Frameworks Section

#### 1. NNG Four Visual Design Principles (token-layer scope)

Present as a table. Gestalt is excluded from this skill — for Gestalt perceptual-grouping critique (proximity, similarity, closure, continuity, figure/ground), redirect to the ux-dev skill's Gestalt analysis protocol.

| Principle | Definition | Key Question |
|---|---|---|
| Scale | Relative size communicates importance | Does the size hierarchy (as expressed through type and spacing tokens) match the information hierarchy? |
| Visual Hierarchy | Order of attention guided by contrast, weight, position | Does the eye land on the right element first, then travel in the right sequence? Are type weight tokens supporting that order? |
| Balance | Distribution of visual weight (symmetric or asymmetric) | Does the layout feel stable? Does the token system produce balanced contrast distribution? |
| Contrast | Difference in value, hue, size, or weight | Is each element distinguishable from its neighbours? Are colour and type contrast tokens purposeful or accidental? |

Note: Each of these four principles is evaluated here as it is expressed through design tokens — type weight relationships, colour contrast between elements, size hierarchy through token choices. For Gestalt grouping critique (do elements that belong together read as a group?), redirect to the ux-dev skill.

#### 2. Colour Theory and Palette Construction

Cover:
- Colour harmonies: complementary (opposite hues, high contrast), analogous (adjacent hues, cohesive), triadic (equidistant, vibrant), split-complementary (one hue + two flanking its complement, tension without harshness).
- OKLCH over HSL: perceptually uniform — equal L steps produce equal perceived lightness changes, unlike HSL where the same L difference looks dramatically different depending on hue. Use OKLCH when constructing scales programmatically.
- Scale construction: for a functional colour, generate a 9–11 step lightness scale. Steps 100–400 serve backgrounds and surfaces in light mode; steps 500–600 serve interactive defaults and borders; steps 700–900 serve text and high-emphasis elements.
- Semantic role mapping: neutral (surface, border, text), brand (primary action, focus ring, selection), feedback (success, warning, danger, info), accent (decorative, non-load-bearing).
- Contrast verification requirements: text contrast 4.5:1 normal (WCAG 1.4.3 AA); large text 3:1 (1.4.3 AA); UI component boundary 3:1 (1.4.11 AA); never use colour as sole differentiator (1.4.1 A — visual remediation: add a second signal; conformance flagging: ux-dev); non-text contrast for focus indicators 3:1 against adjacent surface (1.4.11 AA — token value: this skill; conformance determination: ux-dev); text spacing must not destroy contrast (1.4.12 AA).

#### 3. Three-Tier Token Architecture

This is the most technically specific section. Cover:
- **Tier 1 — Primitive tokens:** Raw values, no semantic meaning. `color-blue-500: #2563EB`. Never referenced directly by components.
- **Tier 2 — Semantic tokens:** Role-named aliases. `color-action-default: {color-blue-500}`. These are the only tokens that change between light and dark mode. Semantic tokens reference primitives; they do not contain literal values.
- **Tier 3 — Component tokens:** Component-scoped, reference semantics. `button-primary-background: {color-action-default}`. Components reference component tokens; component tokens reference semantics.
- **Dark mode invariant:** Only semantic tokens change in dark mode (their alias target shifts from a light primitive to a dark primitive). Primitives do not change. Components do not change. This is the component colour encapsulation invariant.
- **W3C DTCG format (stable Oct 2025):** Token files use `$value`, `$type`, `$description`. Style Dictionary v4 is the reference implementation for transforming DTCG files to CSS, iOS, and Android outputs.
- **Two-tier CSS custom property pattern:** CSS layer 1 declares primitives (`--color-blue-500: #2563EB`); CSS layer 2 declares semantics (`--color-action-default: var(--color-blue-500)`); components reference layer 2 only. Dark mode switches only layer 2.

#### 4. Typographic Scale

Cover:
- Modular scale ratios: 1.2 (minor third — tight, content-dense), 1.333 (perfect fourth — balanced editorial), 1.5 (perfect fifth — strong hierarchy, display use), 1.618 (golden ratio — expressive, fewer type sizes needed).
- Type roles: display, heading (h1–h3), body (reading, UI), label (small, caps), code/mono. Each role needs: family, weight, size (rem, using scale step), line-height, letter-spacing.
- Typeface pairing rules: pair a characterful display face with a neutral body face; avoid pairing two faces with the same classification (two sans-serifs, two serifs); verify contrast of personality (one face carries the brand voice; the other serves readability).
- Fluid type with `clamp()`: min size (mobile), preferred (viewport-relative), max (desktop). Minimum font size 16px body to avoid WCAG 1.4.4 reflow issues.
- WCAG 1.4.4 (Resize Text): content must be readable and functional at 200% zoom without horizontal scroll. 1.4.12 (Text Spacing): 1.5× line-height, 2× letter-spacing, 0.16em word-spacing, 0.12em paragraph spacing must not cause content or functionality loss.

#### 5. Dark Mode Token Remapping

Cover:
- Only semantic tokens remap. Primitives are a fixed library. Components inherit automatically.
- CSS implementation: `@media (prefers-color-scheme: dark) { :root { --color-action-default: var(--color-blue-300); } }`. Only the semantic layer changes.
- Verify contrast independently in both light and dark. A palette that passes 1.4.3 in light mode may fail in dark mode when the same semantic token resolves to a different primitive step.
- Avoid "inversion" patterns (switching all light colours to their dark counterparts) — they break semantic clarity and frequently fail contrast.

### WCAG Aesthetic Criteria Reference Table

Present as a table (distinct from the WCAG structural criteria in ux-dev which covers keyboard, focus existence, ARIA, etc.):

| Criterion | Level | Name | What It Requires | Ownership |
|---|---|---|---|---|
| 1.4.1 | A | Use of Colour | No information conveyed by colour alone | SHARED: frontend-design specifies the second signal (icon, pattern, shape, label); ux-dev flags the violation |
| 1.4.3 | AA | Contrast (Minimum) | Normal text 4.5:1; large text 3:1 | SHARED: frontend-design names the corrected token value; ux-dev flags the violation and owns conformance determination |
| 1.4.4 | AA | Resize Text | Content usable at 200% zoom | frontend-design — use relative units; test fluid type clamp values |
| 1.4.11 | AA | Non-text Contrast | UI components and graphics 3:1 against adjacent colours | SHARED: frontend-design provides the compliant token value; ux-dev owns conformance determination. For focus ring colour contrast, ux-dev owns the 2.4.13 determination; this skill provides the token value. |
| 1.4.12 | AA | Text Spacing | Overrides to line-height, letter-spacing, word-spacing, paragraph spacing must not break content | frontend-design — do not use fixed-height containers that clip text |

Note in the skill body: WCAG criteria 2.4.7, 2.4.11, 2.4.13 (focus visibility, not-obscured, appearance) are owned by ux-dev as structural criteria. This skill provides colour token values for focus ring contrast compliance; ux-dev issues the conformance verdict.

### Design System Visual Layer Critique

Cover the categories this skill evaluates (distinct from ux-dev's component-API and ARIA evaluation):
- Primitive token set: coverage, naming scheme, step count, OKLCH vs HSL construction
- Semantic token set: all roles covered (neutral, brand, feedback, accent, interactive states), dark mode remapping present
- Component token set: encapsulation invariant upheld (no primitives referenced directly)
- Typography token set: scale ratio documented, all required roles defined (display, heading, body, label, code)
- Shadow tokens: elevation model (how many levels, how they map to z-index intent)
- Radius tokens: consistent scale (none, sm, md, lg, full); appropriate for brand register
- Motion tokens: duration scale, easing curves, reduced-motion accommodation (`prefers-reduced-motion`)
- Brand expression: does the token system produce a result that could be mistaken for any other product, or is every token traceable to a deliberate brief decision?

### Brand Voice Section

Cover:
- Register: the level of formality the product speaks at — formal, professional, conversational, casual, playful. Must be documented and consistently applied.
- Tone: the emotional colour within the register — warm, neutral, authoritative, friendly, urgent. Tone may vary per context (error messages are not playful; success states may be warmer).
- Vocabulary: the specific words the brand does and does not use. Positive vocabulary choices and explicit prohibitions both belong in a brand guide.
- Microcopy tone dimension: ux-dev owns what error messages say; this skill owns whether the error message sounds like the brand. Both layers must be evaluated for complete microcopy quality.
- Avoid register collisions: a formal product that uses exclamation marks in success toasts, or a playful product with legalese in error messages, has a register collision — name and remediate.

### Anti-Patterns Section

Table of 8–10 visual-design anti-patterns with risk and remediation. Must include:
- Hardcoded hex values in component CSS (skips token architecture; makes dark mode and theming impossible)
- Primitives referenced directly by components (breaks encapsulation invariant; semantic layer has no effect)
- Colour-only state communication (WCAG 1.4.1; must pair with shape, icon, or label — visual remediation is this skill's job; structural detection is ux-dev's)
- Fixed-height containers with text content (breaks WCAG 1.4.12 text spacing; clips on zoom)
- HSL-based programmatic scales (non-uniform perceptual steps; intermediate stops will appear lighter or darker than expected)
- Type scale without a documented ratio (arbitrary font sizes accumulate inconsistency; no principled way to add sizes)
- Dark mode by CSS inversion (inverts primitives without semantic reasoning; contrast fails unpredictably)
- All-default type pairing (both faces from the system stack, or both the same classification — the brand has no visual voice)
- Motion without `prefers-reduced-motion` accommodation (vestibular accessibility risk; violates WCAG 2.3.3 AAA and emerging expectation for AA)
- Register collision in microcopy (formal UI, playful errors; damages trust and brand coherence)

### How to Respond Section

One protocol block per task type. Must include:

**Colour palette audit** — evaluate harmony type (name it), perceptual uniformity (OKLCH check), semantic role coverage (neutral, brand, feedback, accent), and WCAG aesthetic criteria (1.4.1, 1.4.3, 1.4.4, 1.4.11, 1.4.12) against declared token combinations. Name the specific contrast ratio for each text/background pairing. State pass/fail per criterion. Give a concrete token change for each failure. Note which failures also require ux-dev conformance determination.

**Token architecture audit** — walk the three tiers in order: primitive (coverage and naming), semantic (role completeness, dark-mode remapping), component (encapsulation invariant). Flag any component token that references a primitive directly. Flag any semantic token that contains a literal value. Rate each violation as blocking (any dark-mode or theming attempt will break) or degraded (system works but maintenance overhead is high).

**Typography review** — identify the scale ratio in use (or state "no documented ratio"); list the defined type roles and whether each has family, weight, size, line-height, and letter-spacing documented; verify fluid type uses `clamp()` with rem values; check for WCAG 1.4.4 and 1.4.12 risks (fixed-height containers, px-based sizes that do not scale). Rate the typeface pairing: name both faces, describe the contrast of personality, and state whether the combination is distinctive to this brief or generic.

**Dark mode audit** — verify that only semantic tokens change between modes; check that primitives and component tokens are unchanged; verify contrast independently in both modes. List every semantic token that appears to remap directly to a primitive and confirm the target primitive passes 1.4.3/1.4.11 in dark mode.

**Brand voice assessment** — identify the register (formal/professional/conversational/casual/playful), the documented tone (or note it is undocumented), and any register collisions found in sampled copy. For microcopy samples: evaluate tone fitness and vocabulary consistency; do not evaluate what the copy says (that is ux-dev territory) — only evaluate how it says it.

**Design system visual layer critique** — evaluate in this order: primitive set → semantic set → component tokens → typography tokens → shadow → radius → motion → brand expression. For each layer: name what is present, what is missing, and what is structurally incorrect. Rate issues as blocking (dark mode or theming breaks immediately), significant (accumulates maintenance debt), or minor (inconsistency without functional consequence). Close with a prioritised fix list.

**Focus indicator appearance review** — this skill's scope is colour-token advisory only. ux-dev owns the conformance determination under WCAG 2.4.13 (focus appearance: indicator area and contrast against adjacent colours). This skill provides the colour token value that achieves the required contrast. Evaluate: the colour token currently used for the focus ring, the contrast ratio of that token against the adjacent background surface (target 3:1 per WCAG 1.4.11), and the corrected token value if it fails. Do not issue a conformance verdict — name the failing ratio, give the correct token value, and state that conformance determination belongs to ux-dev. If the focus indicator is absent entirely, note this as a ux-dev concern and redirect without further comment.

**Visual layout critique (NNG principles)** — evaluate in order: Scale, Visual Hierarchy, Balance, Contrast. For each: identify which token decisions are responsible for the current perceptual effect, describe whether the principle is satisfied or violated, and state the token-level change needed if violated. Skip principles the design handles correctly with a single clause. For Gestalt grouping critique (do elements that belong together read as a group?), redirect to the ux-dev skill — that analysis is outside this skill's scope. Close with a ranked fix list ordered by impact on legibility and hierarchy.

**User overrides a recommendation** — state the specific visual or compliance risk in one sentence, then help the user execute their decision well. Do not repeat the warning or withhold help.

---

## Risks and Blockers

1. **Description character limit.** The description must be under 1,024 characters. Step 0 requires an exact count before writing. The "Does NOT activate for" clause has been condensed to a single redirect sentence to create margin. Target under 1,000 characters.

2. **Trigger disambiguation from the marketplace skill.** The marketplace skill's description is vague ("Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one"). The new skill's trigger phrases — "token architecture", "OKLCH", "modular type scale", "three-tier token", "semantic token remapping", "design system visual layer critique" — do not appear in the marketplace skill's description. Disambiguation therefore occurs at the description level: the marketplace skill does not match systematic audit requests, and the new skill does not match generative build requests. No undocumented precedence ordering is assumed or relied upon.

3. **No implementation code.** This skill is advisory only. It must never emit CSS, HTML, or JavaScript. All protocol blocks must end in a design spec (token name + value + criterion cite), not a code snippet. This invariant must be stated explicitly in the persona opening and in the "How to Respond" section.

4. **Line count.** At the density specified, the SKILL.md body will be approximately 380–440 lines. The implementer must run `wc -l` and confirm it is under 500. If over, condense the anti-patterns table or abbreviate the WCAG criteria table.

5. **Shared-boundary precision.** The focus indicator, 1.4.1, and microcopy boundaries with ux-dev are the highest risk of user confusion. The skill body must state these boundaries explicitly — once in the mindset section (to prime the persona) and once in the "How to Respond" protocols (to enforce the behaviour per task type). The focus indicator appearance review protocol must open with the explicit handoff statement that ux-dev owns the conformance determination.

6. **tools field.** `Read` is sufficient — the skill reads files for context (design tokens, style guides) but never writes. If the user later wants the skill to also run `Glob` to find token files, that is a safe addition. Do not add `Write`, `Edit`, or `Bash` to this skill.

---

## Testing Strategy

1. **Activation — correct triggers fire this skill:**
   - "Audit the contrast in our colour palette against WCAG 1.4.3"
   - "Review our three-tier token architecture for dark mode correctness"
   - "Is the type scale on this design system using a modular ratio?"
   - "Assess the brand register consistency across these error message samples"
   - "Critique the visual hierarchy of this landing page layout"
   - "Is the focus ring colour token achieving the 3:1 contrast threshold?"
   Confirm this skill activates for each.

2. **Non-activation — ux-dev or other skills fire instead:**
   - "Do a heuristic evaluation of this checkout flow" — ux-dev
   - "Review the IA of this sitemap" — ux-dev
   - "Is the focus indicator visible for keyboard users?" — ux-dev (structural, not visual)
   - "Write a persona for a receipt scanner user" — ux-dev
   - "Do a Gestalt grouping analysis of this layout" — ux-dev
   - "Build me a full landing page in HTML and CSS" — marketplace frontend-design or neither
   Confirm this skill does NOT activate for these.

3. **Content quality — token architecture audit:**
   Provide a token snippet that mixes primitive and component token references (e.g., a component token pointing directly to a hex value). Confirm the skill: names the tier violation, rates it as blocking or significant, and gives a corrected structure without writing CSS.

4. **Content quality — contrast audit:**
   Provide a colour combination (e.g., `#767676` text on `#FFFFFF` background). Confirm the skill: calculates or cites the contrast ratio (4.48:1, which fails 4.5:1 AA), names criterion 1.4.3 AA, and recommends a corrected token value — without writing CSS and without issuing a conformance verdict (it notes that conformance determination belongs to ux-dev).

5. **Boundary — no code generation:**
   Ask "fix the contrast by updating our CSS variables". Confirm the skill names the correct colour values and the token-level change needed, but explicitly states it does not produce CSS and names the developer as the implementation owner.

6. **Boundary — microcopy tone vs. content:**
   Ask "is this error message on-brand?" — confirm this skill answers (tone/register analysis). Then ask "what should the error message say?" — confirm this skill redirects to ux-dev for content decisions.

7. **Boundary — focus indicator appearance vs. existence:**
   Ask "is the focus ring the right colour?" — confirm this skill evaluates the colour token and contrast ratio, gives the corrected token value if needed, and explicitly states that ux-dev owns the conformance determination. Ask "do all our buttons have focus indicators?" — confirm this skill redirects to ux-dev (structural existence check).

8. **Boundary — Gestalt redirect:**
   Ask "do these form fields read as a group visually?" — confirm this skill redirects to the ux-dev Gestalt analysis protocol rather than answering independently.

9. **Boundary — 1.4.1 shared ownership:**
   Ask "is this status indicator relying on colour alone?" — confirm ux-dev would flag the violation. Then ask "how do I fix the colour-only status indicator?" — confirm this skill specifies the second signal (icon, pattern, shape) and the token to use, without claiming it is the one who detected the violation.

10. **Line count verification:**
    `wc -l /home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/frontend-design/SKILL.md` must be < 500.

11. **Frontmatter verification:**
    `head -10 /home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/frontend-design/SKILL.md` — confirm YAML block is valid, `name` is `frontend-design`, `tools` is `[Read]`.

---

**IMPORTANT — handoff to main agent:** This plan is complete and has been revised per reviewer verdict. The Plan Reviewer agent MUST be run next before any implementation begins. No files should be created or modified until the Reviewer has issued its verdict.
