# UI Theme Rebrand: Modern Fintech + Premium Dark

- **Date:** 2026-06-09
- **Status:** Approved (brainstorming session with Hao)
- **Scope:** Frontend only (`ui/`). No backend or API changes.

## Problem

The current UI is well-structured (ShadCN/Tailwind, consistent page patterns, data-driven
multi-theme system) but the default navy/teal look reads as generic SaaS. The goal is a
distinctive, premium brand identity — without restructuring layout, navigation, or UX.

## Decisions Made

Four design directions were mocked up and reviewed visually:

| Direction | Personality | Outcome |
|---|---|---|
| A — Modern Fintech | Warm off-white paper, near-black ink, deep green accent, mono numerals (Mercury/Ramp school) | **New default brand** — becomes the base Light + Dark themes |
| B — Soft Dark Premium | Dark-first, glassy surfaces, indigo→violet gradients with glow (Linear/Stripe school) | **Ships as "Premium Dark"** picker theme |
| C — Editorial Finance | Cream paper, serif (Fraunces) headings, forest green | Follow-up theme (cheap once tokens exist) |
| D — Bold Tech | High-contrast borders, hard offset shadows, chartreuse | Deferred — structurally most expensive, polarizing |

Further decisions:

- **Rebase, not additive:** Direction A *replaces* the values of the base `:root` (Light) and
  `.dark` (Dark) variable blocks. `system` therefore resolves to two modes of the same brand.
  Existing layered themes (terminal, amber-terminal, sepia) keep working unchanged on top.
- **Paper sidebar:** In the new Light theme the sidebar goes light/warm ("paper"), replacing
  today's dark slate gradient. Confirmed visually over the "ink sidebar" alternative.
- **Dark mode is warm ink, not blue:** `#161614`-family backgrounds, brightened green accent
  (`#3ecf8e` family). Confirmed visually.
- **Dashboard first:** The hardcoded-color sweep and QA start with the Dashboard page, then
  extend to the other key pages.

## Design

### 1. Token vocabulary (`ui/src/index.css` + `ui/tailwind.config.ts`)

The themes differ in more than color, so the CSS-variable vocabulary widens:

- **Typography tokens:** `--font-sans`, `--font-display`, `--font-mono`. Tailwind's
  `fontFamily` config reads these variables with system-stack fallbacks. Load **Inter**
  via the existing Google Fonts import; reuse the already-loaded **JetBrains Mono** for
  numerals. Tables and metric values use `tabular-nums`.
- **Chart tokens:** `--chart-1` … `--chart-5` + `--chart-grid`, defined per theme block,
  consumed by the Recharts wrapper/components so charts follow the active theme.
- **Existing tokens re-valued, not renamed:** `--radius`, shadow utilities, and the
  `--sidebar-*` set keep their names; each theme block assigns new values.

### 2. New base Light theme (`:root`)

Modern Fintech, light mode:

- Background: warm off-white paper (`#fbfbfa` family); cards white with warm-gray borders
  (`#e4e4e0` family).
- Foreground: near-black warm ink (`#1a1a18` family); muted text in warm gray (`#76766f`).
- Primary: deep green (`#0e7a4d` family). Success green, destructive `#b42318` family,
  warning amber retained.
- Sidebar tokens: **paper** — light background, ink text, subtle border; active item gets a
  slightly darker paper fill.

### 3. New base Dark theme (`.dark`)

Modern Fintech, dark mode — warm ink, deliberately not blue:

- Background `#161614` family; cards `#1e1e1b`; borders `#2e2e2a`.
- Foreground warm off-white; muted `#8f8f87`.
- Primary/accent: brightened green (`#3ecf8e` family).
- Same typography tokens as Light.

### 4. Premium Dark theme (`.theme-premium-dark`)

New registry entry, `base: 'dark'`, `className: 'theme-premium-dark'` — follows the
terminal theme's precedent for scoped flourishes:

- Cool dark surfaces (`#0e1015`–`#13151c` gradient range), indigo→violet primary
  (`#6366f1` → `#8b5cf6`).
- Glassy cards: low-alpha white fills + `backdrop-blur`.
- Soft glow shadow on primary buttons and active nav items.
- Scoped CSS lives in its own block in `index.css`, like `.theme-terminal`.

### 5. Theme registry & picker (`ui/src/components/ui/theme-provider.tsx`)

- Update `light` / `dark` entries: new preview swatch colors and descriptions matching the
  rebased look.
- Add `premium-dark` entry (label "Premium Dark") with preview swatch.
- `ThemeId` union gains `'premium-dark'`. Default theme stays `'system'`.
- `ThemePicker.tsx` needs no structural change — it renders from the registry.
- Terminal, Amber Terminal, Sepia entries untouched.

### 6. Hardcoded-color sweep

The rebrand only works where components consume tokens. Known offenders to migrate:

- `AppSidebar.tsx`: hardcoded slate-900→slate-800 gradient → `--sidebar-*` tokens.
- `professional-*` components and dashboard widgets: scattered `slate-`/`blue-` utility
  classes → semantic tokens.
- Recharts components: hardcoded color props → `--chart-*` tokens.

Sweep is scoped to what the new palette exposes — no unrelated refactoring.

### 7. Rollout phasing

1. **Phase 1 — Foundation + Dashboard:** token vocabulary, rebased `:root`/`.dark` blocks,
   `premium-dark` theme + registry entry, sidebar tokenization, and the Dashboard page
   (`ProfessionalDashboard` + its widgets and charts) swept and QA'd across all three themes.
2. **Phase 2 — Key pages:** Invoices, Clients, Settings, Login swept and QA'd.
3. **Later:** Editorial (C) and Bold Tech (D) as new registry entries; long-tail page polish.

### 8. Risks & fallbacks

- Font import failure → system-stack fallbacks in the `fontFamily` config.
- Unknown stored theme id → existing fallback-to-default behavior already handles this.
- Biggest risk is visual regressions on low-traffic pages inheriting the new base variables;
  mitigated by the QA matrix below and the phased sweep.

### 9. Testing

- Update theme-provider/picker unit tests for the new registry entry.
- Existing vitest suites must pass; `tsc` and production build must pass.
- Manual QA matrix: {Dashboard, Invoices, Clients, Settings, Login} ×
  {Light, Dark, Premium Dark}, plus spot-checks of Terminal and Sepia for inheritance leaks.

## Out of Scope

- Editorial (C) and Bold Tech (D) themes (follow-ups once the token vocabulary lands).
- Backend sync of theme preference (stays per-device localStorage).
- Per-tenant theming / white-labeling.
- Layout, navigation, or UX restructuring.
