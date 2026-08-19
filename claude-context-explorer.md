# Explorer Findings: ux-dev / frontend-design Skill Boundary

## 1. File Paths

- **ux-dev skill:** `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/ux-dev/SKILL.md`
- **frontend-design skill:** `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`

Both files exist. The frontend-design skill is an official marketplace plugin. The ux-dev skill is a personal wills-plugins skill already created.

---

## 2. Every Place in ux-dev That Explicitly Mentions "frontend-design skill"

There are five explicit references. Exact quoted lines (by line number in the SKILL.md):

**Line 3 (description frontmatter):**
> "Does not replace the frontend-design skill, which owns visual aesthetics."

**Line 151 (Wireframe critique section):**
> "If asked to 'make it look better,' redirect to the frontend-design skill for aesthetic choices and stay on interaction and structure."

**Line 161 (Design system critique section):**
> "Do not evaluate palette, typeface, or brand aesthetic — direct those concerns to the frontend-design skill."

**Line 171 (Microcopy section):**
> "brand voice decisions belong to frontend-design."

**Line 175 (Deliverable generation section):**
> "Name the handoff point explicitly: 'the following spec should be passed to a frontend developer or the frontend-design skill for implementation.'"

---

## 3. Domains ux-dev Explicitly Says It Does NOT Cover (= frontend-design's remit)

From the description frontmatter (line 3):
- Color palettes
- Typography
- CSS
- HTML
- Flutter widget code
- AWS
- Python
- Brand voice
- Marketing copy
- Visual aesthetics (summary: "does not replace the frontend-design skill, which owns visual aesthetics")

From the body:
- **Wireframe critique:** "Do not comment on color, typefaces, or visual styling." (line 151)
- **Design system critique:** "Do not evaluate palette, typeface, or brand aesthetic." (line 161)
- **Microcopy:** "brand voice decisions belong to frontend-design. Do not produce surrounding HTML or CSS." (line 171)
- **Deliverable generation:** "Do not produce HTML, CSS, or implementation code." (line 175)

---

## 4. Domains ux-dev Explicitly Says It DOES Cover (must not be duplicated in frontend-design)

From the description frontmatter (line 3):
- Heuristic evaluation (Nielsen's 10)
- WCAG compliance / accessibility auditing
- Information architecture review
- User flow critique
- Wireframe critique (structure/interaction only, not color or typography)
- Design system critique (component API, token naming, a11y annotations — not palette/typeface)
- Persona creation
- Journey map creation and critique
- Usability testing, card sorting, tree testing planning and interpretation
- Form design review
- Navigation design review
- Progressive disclosure assessment
- Onboarding flow review
- VUI design review
- Touch targets, keyboard navigation, focus management
- Error states, empty states
- TV/10-foot UI, kiosk UX, cross-platform UX consistency
- UX microcopy: error messages, button labels, empty states, placeholder text (as structural elements — not brand voice)
- Platform-agnostic UX methodology
- Gestalt principles applied to layout critique

From the body, additional explicit scope:
- Severity rating of heuristic violations (0–4 scale)
- WCAG 2.2 AA conformance (specific criteria 1.3.1, 1.3.5, 1.4.1, 1.4.3, 1.4.11, 2.1.2, 2.4.3, 2.4.7, 2.4.11, 2.4.13, 2.5.7, 2.5.8, 3.3.2, 3.3.7, 3.3.8)
- Journey map emotional arc (minimum 5-point scale)
- Anti-pattern recognition (14-row table)
- IA review (four systems: organization, labeling, navigation, search)

---

## 5. ux-dev Activation Trigger (full description field, line 3)

> "Activates for UX methodology, interaction design, and design critique. Use when asked to: do a heuristic evaluation; audit for WCAG compliance or accessibility; review an information architecture or sitemap; critique a user flow, wireframe, or design system; create a persona; create or critique a journey map; run or plan usability testing, card sorting, or tree testing; assess form design, navigation design, or progressive disclosure; or apply Nielsen's heuristics or Gestalt principles. Also activates for UX questions about touch targets, keyboard navigation, focus management, error states, empty states, onboarding flows, VUI design, TV/10-foot UI, kiosk UX, or cross-platform UX consistency. Also activates for UX microcopy: error messages, button labels, empty states, placeholder text. Does NOT activate for color palettes, typography, CSS, HTML, Flutter widget code, AWS, Python, brand voice, or marketing copy. Does not replace the frontend-design skill, which owns visual aesthetics."

---

## 6. Does a frontend-design Skill File Already Exist?

Yes. It exists at:

`/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`

It is an official marketplace plugin (not a personal wills-plugins skill). Its description field is:

> "Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults."

It does NOT contain any mention of "ux-dev" anywhere in its body. Its body covers: aesthetic direction, palette (4-6 named hex values), typeface selection and pairing, layout concept, CSS authoring, motion/animation, and copy as design material (tone, brand voice, register). It explicitly treats words as a design element but from an aesthetic/brand-voice angle, not a UX methodology angle.

---

## 7. Boundary Summary for the Planner

| Domain | Owner |
|---|---|
| Color palette, hex tokens, visual identity | frontend-design |
| Typography: typeface selection, type scale, pairing | frontend-design |
| CSS authoring, HTML implementation | frontend-design |
| Layout aesthetic, visual signature, motion/animation design | frontend-design |
| Brand voice, marketing copy, stylistic copy direction | frontend-design |
| Copy as design material: tone, register, personality | frontend-design |
| UX microcopy as structural interface element (button labels, error messages, empty states, placeholder text — functional copy, not tonal direction) | ux-dev |
| Heuristic evaluation, interaction design, usability | ux-dev |
| WCAG / accessibility as design discipline | ux-dev |
| Information architecture | ux-dev |
| User flows, wireframe critique (structure only), personas, journey maps | ux-dev |
| Design system: component API, token naming, a11y annotations | ux-dev |
| Platform UX (mobile, TV, VUI, kiosk) | ux-dev |
| Usability testing, card sorting, tree testing methodology | ux-dev |

**Overlap note on copy:** frontend-design's body discusses writing as design material ("Words appear in a design for one reason: to make it easier to understand") and covers active voice, label naming, and error/empty-state tone. ux-dev's microcopy section covers the same error/empty-state territory from a structural/UX perspective. The dividing line ux-dev draws is: UX copy = structural element (ux-dev owns); brand voice / personality direction = frontend-design. Any new or revised frontend-design skill definition must not claim UX copy methodology or structural labeling — it may only claim the aesthetic/tone/brand-voice dimension of copy.

---

## Files Examined

- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/ux-dev/SKILL.md`
- `/home/devuser/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`
- `/workspace/active_repo/claude-context-plan.md` (for cross-reference with plan-time boundary decisions)
