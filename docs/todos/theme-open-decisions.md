# Theme rebrand — open decisions & follow-ups

Status as of 2026-06-10. The theme tokenization effort is essentially complete
(PRs #379–#392 merged: rebrand + reload fixes, auth pages, invoice flows, two
workflow batches across ~162 files, gamification/charts, sidebar tokens, test
repair, i18n keys). What remains needs a **design/product decision** or is a
**larger project** — captured here so it can be picked up cold.

Each item below has the concrete details, options, and a recommendation.

---

## 1. KPI-card consistency (charts) — DECISION

The two chart files render their metric summary cards differently because their
originals differed:

| | `PaymentCharts.tsx` | `ExpenseCharts.tsx` |
|---|---|---|
| KPI cards | **4** (blue / green / purple / orange) | **3** (trend / total / volatility) |
| Original gradient | had `dark:` variants → **adapts** to dark | light-only (`from-blue-50`, no `dark:`) → **broke** in dark |
| Batch sweep result | **kept** the gradients (they work) | **neutralized** to plain `<Card>` + muted text |

Live effect: Payments charts show colorful per-metric cards; Expenses charts show
flat neutral cards. Each sweep was locally correct; the inconsistency is the issue.

**Options**
- **(A) Recommended — make ExpenseCharts colorful + adaptive:** re-add its 3
  metric gradients *with* `dark:` variants (mirror PaymentCharts). Restores the
  per-metric color cue; PaymentCharts already proves the pattern works in dark.
- **(B) Make PaymentCharts neutral:** flatten its 4 gradient cards to plain
  `<Card>` to match ExpenseCharts. Cleaner/minimal, loses the color cue.
- **(C) Leave as-is.**

Effort: ~1 small PR either way. Files: `ui/src/components/PaymentCharts.tsx`
(lines ~80–145), `ui/src/components/expenses/ExpenseCharts.tsx` (lines ~211–260).

---

## 2. Dark destructive-button contrast — DECISION

A genuine single-token tension. Dark theme uses `--destructive: 0 72% 60%` with a
white foreground (`ui/src/index.css` line ~180).

| Use of the token | At current **L60** | At **L53** (what Premium Dark uses) |
|---|---|---|
| **Button** (white text on red bg) | **3.82:1** ✗ AA-text / ✓ 3:1 UI | 4.60:1 ✓ |
| **Error text** (red text on dark bg) | 4.80:1 ✓ | **3.99:1** ✗ |

One `--destructive` value **cannot** satisfy both at WCAG AA 4.5:1 — darkening it
fixes the button but breaks error text, and vice-versa. (Premium Dark already
made the opposite trade: its button passes, its error text is ~4.0:1.)

**Options**
- **(A) Recommended — accept it:** a destructive *button* at 3.82:1 meets WCAG
  1.4.11's 3:1 threshold for UI components; it's a bold button, not body text.
  Zero code — just a documented decision.
- **(B) Separate button token:** add a darker `--destructive-button` (e.g.
  `0 72% 50%`) + override the Button `destructive` variant to use it. Both the
  button and error text then clear 4.5:1. Cost: one token + a small variant change.
- **(C) Match Premium Dark:** darken dark-theme `--destructive` to ~L53 and
  accept error text at ~4.0:1.

Effort: (A) trivial, (B) small. File: `ui/src/index.css` (+ `button.tsx` for B).

---

## 3. Theme C — Editorial Finance — PROJECT (low effort)

From the original spec: **cream paper, serif headings (Fraunces), forest green.**
Spec note: *"Follow-up theme (cheap once tokens exist)."*

**Build:** new `THEMES` registry entry (like `premium-dark`) + a `.theme-editorial`
CSS-variable block in `index.css` + load the Fraunces serif font into
`--font-display` (the token vocabulary already supports `--font-display`).
Purely additive and opt-in; low risk.

**Effort:** ~1 focused PR. Mostly tokens + a font import + a registry entry +
preview swatch.

---

## 4. Theme D — Bold Tech — PROJECT (high effort)

From the original spec: **high-contrast borders, hard offset shadows, chartreuse
accent.** Spec note: *"Deferred — structurally most expensive, polarizing."*

**Build:** new registry entry + CSS-var block **plus scoped component CSS**
(`.theme-bold-tech { … }`) because hard offset shadows / thick borders are not
pure design tokens — they need scoped overrides on cards/buttons/inputs, similar
to the terminal theme's scoped flourishes.

**Effort:** larger, its own deliberate project. Medium risk (bold/polarizing look,
more surface to get right). Recommend scheduling separately from C.

---

## Suggested batching
- **Quick win PR:** 1A + 2A together (colorful adaptive Expense KPI cards + a
  documented "accept 3.82:1 destructive button" note). High value, low risk.
- **Theme C** as a clean standalone add.
- **Theme D** as its own project when there's appetite for a bold look.

## Other minor leaves (non-blocking, already low-priority)
- ~590 conservative color leaves from the batches (decorative multi-color
  palettes, gradients, status-on-colored-bg buttons) — case-by-case, mostly
  legitimately left.
- `AppSidebar.test` plugin-integration tests: 7 `it.skip` with TODO — need the
  plugin system mocked (`usePlugins`/`usePluginModules`) to render plugin nav.
