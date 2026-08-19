# Plan Review

## Verdict
**NEEDS REVISION** — six of the seven previously flagged flaws have been resolved correctly. One flaw (Flaw 7, the `commands/` path frontmatter parsing verification) remains unaddressed in the revised plan: the recommended verification step was dropped when Step 0 was repurposed for character counting. No new hard flaws have been introduced. One minor observation is also noted below.

---

## Flaws Found

**Flaw 7 (persisting) — `commands/` path frontmatter verification step is still absent.**

The previous review required inserting a step to confirm the wills-skills plugin loader parses YAML frontmatter from the `commands/` path before any file is written. The revised plan's Step 0 was repurposed for the character-count measurement (correct), but the frontmatter-parsing verification step was not inserted anywhere else in the sequence. Steps 0–5 now read: measure character count → create directory → write file → verify frontmatter fields → verify line count → smoke-test activation. None of these steps confirm that the loader honours frontmatter at this path before the file is written.

This matters because the entire skill depends on frontmatter: the `description` field is the auto-trigger mechanism, and the `tools: [Read]` allowlist is the only constraint preventing the skill from inheriting all available tools. The researcher explicitly states: "Legacy `.claude/commands/` files still work but lack frontmatter features." If the wills-skills loader treats the `commands/` directory as legacy-format, both the auto-trigger and the tool restriction will be silently ignored. The ux-dev skill existing at the same path type is circumstantial evidence that the loader does parse frontmatter here, but it is not a confirmed fact — it has not been verified by reading the ux-dev skill's frontmatter and observing it enforced at runtime.

Consequence if left unfixed: the implementer creates the file, the character count and line count pass, the smoke test appears to activate the skill (because the skill content loads), but the `tools: [Read]` restriction is not enforced and the description-based auto-trigger may not function — the skill may only fire when explicitly invoked via slash command, not when Claude selects it automatically.

---

## Verification of the Six Resolved Flaws

**Flaw 1 — False claim about marketplace skill:** Resolved. The revised plan now explicitly acknowledges the marketplace skill "enforces a quality floor while building ('responsive down to mobile, visible keyboard focus, reduced motion respected')" and frames the distinction as "generative vs. analytical, not the presence or absence of accessibility language." The false characterisation ("no WCAG aesthetic criteria") has been corrected.

**Flaw 2 — Focus indicator contrast ownership conflict:** Resolved. The scope boundary table now cleanly separates "Focus indicator visual appearance: colour token value, thickness, offset; providing the token value that achieves required contrast" (frontend-design) from "Focus indicator conformance determination: WCAG 2.4.7, 2.4.11, 2.4.13 structural compliance" (ux-dev). The shared-boundary resolution rules state this explicitly, and the "How to Respond" protocol for focus indicator appearance review opens with the explicit handoff. This no longer conflicts with ux-dev's existing 2.4.13 ownership.

**Flaw 3 — WCAG 1.4.1 sole attribution:** Resolved. The scope boundary table now applies the shared model consistently: "WCAG 1.4.1 (Use of Colour) — SHARED: frontend-design owns visual remediation (select a second signal: icon, pattern, shape, label); ux-dev owns structural detection (flag colour as the sole differentiator)." This matches ux-dev's existing ownership of 1.4.1 in its anti-patterns table and WCAG POUR coverage.

**Flaw 4 — Undocumented precedence claim:** Resolved. The revised plan explicitly states "No undocumented precedence claim is made." The plan now relies solely on description-level disambiguation through trigger phrases that do not appear in the marketplace skill's description. The phrase "the wills-skills skill takes precedence due to being in the personal plugin path" has been removed.

**Flaw 5 — Description character count underestimated:** Resolved. Step 0 now mandates an exact `echo -n "<full description text>" | wc -c` measurement before writing, targets under 1,000 characters (not ~950), and provides the condensed negative clause as a fallback. The description as written in the frontmatter block uses the condensed form ("Does not activate for interaction design, IA, UX methodology, WCAG structural criteria, keyboard model, ARIA, or UX copy content decisions — see the ux-dev skill"), which is the abbreviated version recommended in the previous review.

**Flaw 6 — Gestalt duplication with ux-dev:** Resolved. Gestalt has been removed from the NNG table, which is now explicitly titled "NNG Four Visual Design Principles" covering only Scale, Visual Hierarchy, Balance, and Contrast. The scope boundary table explicitly assigns Gestalt to ux-dev. The "Visual layout critique" response protocol redirects Gestalt grouping critique to the ux-dev skill. The note in the NNG section states: "For Gestalt grouping critique (do elements that belong together read as a group?), redirect to the ux-dev skill."

---

## Suggested Improvements

**Improvement 1:** Insert a pre-write verification step for frontmatter support at the `commands/` path. Place it as the first action inside Step 0 or as a new Step 0a:

> "Step 0a — Confirm frontmatter is parsed at the `commands/` path for this loader. Open `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/ux-dev/SKILL.md` and verify its `tools: [Read]` and `description` fields are present in the file header. Then confirm in a live session that ux-dev auto-triggers on a description-matched request (not only via slash command). If both are true, the loader parses frontmatter at this path and Step 1 may proceed. If uncertain, use the path `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/skills/frontend-design/SKILL.md` (the researcher-documented canonical personal skill path) to guarantee frontmatter support."

**Improvement 2 (minor, non-blocking):** The frontmatter block includes `version: 1.0.0`. The researcher's documentation of optional frontmatter fields does not list `version` as a recognised field (`model`, `tools`, `disallowedTools`, `disable-model-invocation`, `context`, `permissionMode`, and `maxTurns` are listed; `version` is not). An unrecognised YAML field is silently ignored and will not cause a failure, but the field has no documented effect. If ux-dev uses the same convention it is consistent with the local plugin pattern, which is acceptable. No action required, but worth noting.

---

## Revised Steps (if applicable)

Insert the following as a new step before Step 1. Step 0 (character count) remains as written. The new step is Step 0a:

**Step 0a — Confirm `commands/` path supports frontmatter parsing.**
Open `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/ux-dev/SKILL.md`. Verify that a `description:` and `tools:` field appear in the YAML frontmatter block at the top of the file. In a live Claude Code session, issue a request that should match ux-dev's description trigger (e.g., "do a heuristic evaluation of this flow") and confirm ux-dev auto-activates without being explicitly invoked as `/ux-dev`. If auto-trigger is confirmed, the loader parses frontmatter at the `commands/` path; proceed to Step 1. If auto-trigger cannot be confirmed, create the new skill at `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/skills/frontend-design/SKILL.md` instead (the canonical path documented in the researcher's findings under "File locations"), which guarantees frontmatter support.

---

## Summary

The plan is substantively stronger after revision: the six structural conflicts, false characterisations, and undocumented assumptions from the first review have all been correctly resolved. The single remaining issue is the missing verification that the `commands/` path actually parses YAML frontmatter for this specific plugin loader — without that confirmation, the auto-trigger mechanism and the `tools: [Read]` restriction may silently fail. Adding Step 0a above is a one-action fix that resolves the last outstanding risk, after which implementation can safely proceed.
