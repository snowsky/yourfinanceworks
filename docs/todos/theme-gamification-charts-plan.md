# Theme tokenization — gamification & charts (manual pass)

These files were **deliberately excluded** from the automated workflow batches
(PRs #386/#387) because they carry intentional multi-color meaning that
collapsing to a single semantic token would destroy. They need per-file human
judgment. This doc is the treatment plan; `FinancialHealthScore.tsx` in this
branch is the worked exemplar.

## Treatment rules

### Gamification — `ui/src/components/gamification/*`
**KEEP** (deliberate identity / data-viz — the feature's visual language):
- Tier / level / streak / badge / celebration colors (purple, orange, gold-amber,
  pink, teal, multi-color gradients)
- Score / health gradients where the *color step is the signal*
  (e.g. `green→yellow→orange→red` for excellent→poor)

**TOKENIZE** (chrome around the game elements):
- Neutral surfaces / text / borders (gray, slate) → `card` / `background` /
  `foreground` / `muted-foreground` / `border` / `muted`
- Info / alert callout boxes (blue / green / red tints) → `primary` / `success` /
  `destructive` at `/10` (bg) + `/30` (border), neutral body text
- Clear binary status (trend up / down, complete / locked) → `success` /
  `destructive`
- recharts `stroke`/`fill` that is a single accent line → `hsl(var(--primary))`
  (or `hsl(var(--chart-N))`)

**Exemplar — `FinancialHealthScore.tsx` (this branch):** keeps the 4-step score
gradient (`getScoreColor`) and the purple Gamepad identity icon; tokenizes the
SVG track, body text, the blue disclaimer/tips callouts, and the recharts trend
line (`#3b82f6` → `hsl(var(--primary))`).

### Charts — `PaymentCharts.tsx`, `ExpenseCharts.tsx`, any recharts widget
Follow the **already-merged** `components/dashboard/InvoiceChart.tsx` pattern
(it uses these tokens today):
- Series colors (hardcoded hex / `color-N`) → `hsl(var(--chart-1..5))`
- Grid → `hsl(var(--chart-grid))`; axis tick/label text → `muted-foreground`
- Tooltip / legend surface → `hsl(var(--popover))` + `border`; tooltip text →
  `popover-foreground`
- Gain / loss / status text → `success` / `destructive`
- Keep a categorical palette only if it needs **>5** distinct series (the chart
  token set covers 5).

## File buckets

**Gamification (13):** AchievementGrid, AchievementRules, CelebrationModal,
ChallengeCards, **FinancialHealthScore ✅ (this branch)**, GamificationDashboard,
GamificationNotifications, GamificationToasts, GamificationToggle,
GamificationWidget, LevelProgressCard, RecentPointsHistory, StreakDisplay.

**Charts (2 primary):** PaymentCharts, ExpenseCharts (+ recharts usage inside
other widgets — grep `recharts` / `stroke="#`).

## Per-file process
1. Read; classify each color: **chrome** (tokenize) vs **identity/viz** (keep).
2. Apply edits (color classes only); confirm zero *unwanted* residual + `tsc`.
3. Visual spot-check: gamification → Settings ▸ Gamification; charts → Dashboard
   / Expenses / Payments, in a dark theme.

## Open design question (needs Hao's call)
Should the gamification identity palette (purple/gold/streak-flame) get its own
small **named token set** (e.g. `--tier-gold`, `--streak-flame`) so it adapts
subtly per theme — or stay fixed across themes? The current draft keeps it
**fixed** (simplest, preserves the established game look). A token set would make
e.g. Terminal/Sepia themes feel more cohesive but is a larger design decision.
