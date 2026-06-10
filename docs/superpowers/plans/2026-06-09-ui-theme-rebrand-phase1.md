# UI Theme Rebrand Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebase the app's base Light/Dark themes onto the "Modern Fintech" look (warm paper, ink text, green accent, paper sidebar), add a "Premium Dark" picker theme, and sweep the Dashboard page's hardcoded colors onto semantic tokens.

**Architecture:** All theming flows through ShadCN-style CSS variables in `ui/src/index.css` consumed by `ui/tailwind.config.ts`. Themes are registry entries in `theme-provider.tsx` (`base` light/dark class + optional scoped `className`). This plan re-values the `:root` and `.dark` blocks, widens the token vocabulary (fonts, charts), adds a `.theme-premium-dark` block + registry entry, and replaces hardcoded `slate-*`/`blue-*`/hex colors in the sidebar and dashboard with token-based classes.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, ShadCN/Radix, Recharts, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-06-09-ui-theme-rebrand-design.md`

**Branch:** `feat/ui-theme-rebrand` (already created; spec committed)

**Running tests:** Canonical: `docker compose exec ui npx vitest run <path>`. If Docker isn't up, fall back to `cd ui && npx vitest run <path>` (node_modules exists locally). Same for `npx tsc --noEmit` and `npx vite build`.

**Verification baseline:** Before Task 1, capture the current state so regressions are attributable: run `cd ui && npx tsc --noEmit` and note any pre-existing errors.

---

### Task 1: Font tokens + Tailwind wiring

Inter becomes the brand font via CSS variables; Tailwind reads the variables so every `font-sans`/`font-display` usage follows the theme.

**Files:**
- Modify: `ui/src/index.css:1` (font import), `ui/src/index.css:372-390` (body + .font-display)
- Modify: `ui/tailwind.config.ts:22-28` (fontFamily)

- [ ] **Step 1: Replace the Google Fonts import** (`ui/src/index.css` line 1)

```css
@import url("https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300..800;1,14..32,400&family=JetBrains+Mono:wght@400;500;700;800&display=swap");
```

(Plus Jakarta Sans and DM Serif Display are dropped — after this plan nothing references them. JetBrains Mono stays: terminal theme + numerals.)

- [ ] **Step 2: Add font variables to `:root`** — inside the `:root` block (after `--radius`):

```css
    /* Typography tokens — themes may override */
    --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-display: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-mono: "JetBrains Mono", "Fira Code", ui-monospace, "SFMono-Regular", monospace;
```

- [ ] **Step 3: Make `body` and `.font-display` consume the variables** — replace the `font-family` declarations at `ui/src/index.css:372-390`:

```css
  body {
    @apply bg-background text-foreground;
    font-family: var(--font-sans);
    font-feature-settings: "cv02", "cv03", "cv04", "cv11";
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.011em;
  }

  /* Display font for large numbers, metric values, page titles */
  .font-display {
    font-family: var(--font-display);
    font-feature-settings: normal;
    letter-spacing: -0.02em;
  }
```

- [ ] **Step 4: Wire Tailwind `fontFamily` to the variables** (`ui/tailwind.config.ts:22-28`):

```ts
			fontFamily: {
				sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
				mono: ['var(--font-mono)', 'monospace'],
				heading: ['var(--font-sans)', 'system-ui', 'sans-serif'],
				body: ['var(--font-sans)', 'system-ui', 'sans-serif'],
				display: ['var(--font-display)', 'system-ui', 'sans-serif'],
			},
```

- [ ] **Step 5: Verify nothing else references the dropped fonts**

Run: `cd ui && grep -rn "Plus Jakarta\|DM Serif" src/ tailwind.config.ts index.html`
Expected: no matches (if `index.html` preloads fonts, update that link to the new families).

- [ ] **Step 6: Typecheck**

Run: `cd ui && npx tsc --noEmit`
Expected: no new errors vs. baseline.

- [ ] **Step 7: Commit**

```bash
git add ui/src/index.css ui/tailwind.config.ts
git commit -m "feat(theme): add font tokens, switch brand font to Inter"
```

---

### Task 2: Rebase the Light theme (`:root`)

Modern Fintech light: warm paper, ink text, deep green primary, paper sidebar, chart tokens.

**Files:**
- Modify: `ui/src/index.css:90-143` (the `:root` block)

- [ ] **Step 1: Replace the `:root` variable values** — keep the font tokens added in Task 1; replace the rest of the block body with:

```css
  :root {
    /* Modern Fintech — warm paper & ink */
    --background: 60 10% 98%;
    --foreground: 60 4% 10%;

    --card: 0 0% 100%;
    --card-foreground: 60 4% 10%;

    --popover: 0 0% 100%;
    --popover-foreground: 60 4% 10%;

    /* Deep green — the single brand accent */
    --primary: 155 79% 27%;
    --primary-foreground: 60 10% 98%;

    /* Quiet warm-gray secondary (secondary buttons, chips) */
    --secondary: 60 7% 92%;
    --secondary-foreground: 60 4% 10%;

    --muted: 60 10% 94%;
    --muted-foreground: 60 3% 40%; /* L40 (not 45): AA on --muted and --background per review */

    /* Teal-green accent — stays colored for accent-foreground contracts */
    --accent: 165 60% 30%;
    --accent-foreground: 0 0% 100%;

    /* Brick red destructive */
    --destructive: 7 76% 40%;
    --destructive-foreground: 60 10% 98%;

    --success: 155 70% 30%;
    --success-foreground: 0 0% 100%;

    /* Dark amber: legible as text-warning on light surfaces (status badges) */
    --warning: 43 96% 30%;
    --warning-foreground: 0 0% 100%;

    --border: 60 7% 89%;
    --input: 60 7% 89%;
    --ring: 155 79% 27%;

    --radius: 0.5rem;

    /* Typography tokens — themes may override */
    --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-display: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-mono: "JetBrains Mono", "Fira Code", ui-monospace, "SFMono-Regular", monospace;

    /* Chart palette */
    --chart-1: 155 79% 30%;
    --chart-2: 43 96% 50%;
    --chart-3: 60 4% 55%;
    --chart-4: 17 60% 45%;
    --chart-5: 188 60% 35%;
    --chart-grid: 60 7% 89%;

    /* Paper sidebar — light surface, ink text */
    --sidebar-background: 60 8% 95%;
    --sidebar-foreground: 60 4% 28%;
    --sidebar-primary: 155 79% 27%;
    --sidebar-primary-foreground: 0 0% 100%;
    --sidebar-accent: 60 8% 89%;
    --sidebar-accent-foreground: 60 4% 10%;
    --sidebar-border: 60 7% 88%;
    --sidebar-ring: 155 79% 27%;
  }
```

- [ ] **Step 2: Build to confirm CSS parses**

Run: `cd ui && npx vite build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add ui/src/index.css
git commit -m "feat(theme): rebase Light theme onto Modern Fintech palette"
```

---

### Task 3: Rebase the Dark theme (`.dark`)

Warm ink dark — deliberately not blue.

**Files:**
- Modify: `ui/src/index.css:145-196` (the `.dark` block)

- [ ] **Step 1: Replace the `.dark` block body with:**

```css
  .dark {
    /* Modern Fintech — warm ink dark */
    --background: 60 5% 8%;
    --foreground: 60 14% 94%;

    --card: 60 5% 11%;
    --card-foreground: 60 14% 94%;

    --popover: 60 5% 10%;
    --popover-foreground: 60 14% 94%;

    /* Brightened green for dark surfaces */
    --primary: 153 60% 53%;
    --primary-foreground: 155 50% 8%;

    --secondary: 60 4% 16%;
    --secondary-foreground: 60 14% 94%;

    --muted: 60 4% 14%;
    --muted-foreground: 60 4% 55%;

    --accent: 165 55% 45%;
    --accent-foreground: 155 50% 8%;

    --destructive: 0 72% 60%;
    --destructive-foreground: 0 0% 100%;

    --success: 153 60% 48%;
    --success-foreground: 155 50% 8%;

    --warning: 43 96% 56%;
    --warning-foreground: 60 4% 10%;

    --border: 60 5% 17%;
    --input: 60 5% 17%;
    --ring: 153 60% 53%;

    /* Chart palette — brighter on dark */
    --chart-1: 153 60% 53%;
    --chart-2: 43 96% 56%;
    --chart-3: 60 4% 50%;
    --chart-4: 17 70% 60%;
    --chart-5: 188 60% 50%;
    --chart-grid: 60 5% 17%;

    /* Warm ink sidebar */
    --sidebar-background: 60 5% 10%;
    --sidebar-foreground: 60 4% 60%;
    --sidebar-primary: 153 60% 53%;
    --sidebar-primary-foreground: 155 50% 8%;
    --sidebar-accent: 60 5% 16%;
    --sidebar-accent-foreground: 60 14% 94%;
    --sidebar-border: 60 5% 17%;
    --sidebar-ring: 153 60% 53%;
  }
```

(Note: `.dark` has no `--radius` or font overrides — it inherits Light's via `:root`.)

- [ ] **Step 2: Add chart-token fallbacks to the layered themes** so terminal/sepia charts don't render the warm-paper palette. Append to the END of the `.theme-terminal` block:

```css
    --chart-1: 142 84% 52%;
    --chart-2: 40 96% 56%;
    --chart-3: 142 24% 52%;
    --chart-4: 0 90% 62%;
    --chart-5: 180 70% 45%;
    --chart-grid: 150 36% 16%;
```

Append to the END of the `.theme-terminal-amber` block:

```css
    --chart-1: 38 96% 56%;
    --chart-2: 142 72% 50%;
    --chart-3: 36 32% 54%;
    --chart-4: 0 90% 62%;
    --chart-5: 28 58% 44%;
    --chart-grid: 34 44% 16%;
```

Append to the END of the `.theme-sepia` block:

```css
    --chart-1: 154 44% 32%;
    --chart-2: 36 72% 46%;
    --chart-3: 30 18% 42%;
    --chart-4: 8 62% 46%;
    --chart-5: 200 40% 38%;
    --chart-grid: 36 28% 78%;
```

- [ ] **Step 3: Build**

Run: `cd ui && npx vite build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add ui/src/index.css
git commit -m "feat(theme): rebase Dark theme to warm ink, add chart tokens to layered themes"
```

---

### Task 4: Premium Dark theme (TDD)

New registry entry + scoped CSS block, plus updated preview swatches/descriptions for the rebased Light/Dark entries.

**Files:**
- Test: `ui/src/components/__tests__/ThemeProvider.test.tsx` (create)
- Modify: `ui/src/components/ui/theme-provider.tsx` (ThemeId, THEMES)
- Modify: `ui/src/index.css` (new `.theme-premium-dark` blocks)

- [ ] **Step 1: Write the failing test** — create `ui/src/components/__tests__/ThemeProvider.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup, fireEvent, screen } from "@testing-library/react";
import {
  ThemeProvider,
  THEMES,
  useTheme,
} from "@/components/ui/theme-provider";

function ThemeButtons() {
  const { setTheme } = useTheme();
  return (
    <>
      <button onClick={() => setTheme("premium-dark")}>premium</button>
      <button onClick={() => setTheme("light")}>light</button>
    </>
  );
}

describe("premium-dark theme", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    document.documentElement.className = "";
  });

  it("is registered with a dark base and a scoped class", () => {
    const def = THEMES.find((t) => t.id === "premium-dark");
    expect(def).toBeDefined();
    expect(def?.base).toBe("dark");
    expect(def?.className).toBe("theme-premium-dark");
  });

  it("applies dark + theme-premium-dark classes to <html>", () => {
    render(
      <ThemeProvider defaultTheme="premium-dark" storageKey="test-theme">
        <div />
      </ThemeProvider>
    );
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(
      document.documentElement.classList.contains("theme-premium-dark")
    ).toBe(true);
  });

  it("clears the scoped class when switching back to light", () => {
    render(
      <ThemeProvider defaultTheme="premium-dark" storageKey="test-theme">
        <ThemeButtons />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByText("light"));
    expect(
      document.documentElement.classList.contains("theme-premium-dark")
    ).toBe(false);
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test — verify it FAILS**

Run: `cd ui && npx vitest run src/components/__tests__/ThemeProvider.test.tsx`
Expected: FAIL — `premium-dark` not in `THEMES` (first assertion `toBeDefined` fails).

- [ ] **Step 3: Add the theme to the registry** — in `ui/src/components/ui/theme-provider.tsx`:

Extend the union (line 16-22):

```ts
export type ThemeId =
  | 'light'
  | 'dark'
  | 'system'
  | 'premium-dark'
  | 'terminal'
  | 'amber-terminal'
  | 'sepia';
```

Update the `light` and `dark` entries (new look, new swatches) and insert `premium-dark` after `dark` in `THEMES`:

```ts
  {
    id: 'light',
    label: 'Light',
    description: 'Warm paper, ink text, and a deep green accent.',
    base: 'light',
    preview: { bg: '#fbfbfa', surface: '#ffffff', accent: '#0e7a4d', text: '#1a1a18' },
  },
  {
    id: 'dark',
    label: 'Dark',
    description: 'Warm ink surfaces with a bright green accent.',
    base: 'dark',
    preview: { bg: '#161614', surface: '#1e1e1b', accent: '#3ecf8e', text: '#f2f2ee' },
  },
  {
    id: 'premium-dark',
    label: 'Premium Dark',
    description: 'Indigo glass surfaces with a soft neon glow.',
    base: 'dark',
    className: 'theme-premium-dark',
    preview: { bg: '#0e1015', surface: '#171a23', accent: '#6366f1', text: '#e8eaf2' },
  },
```

- [ ] **Step 4: Add the variable block** — in `ui/src/index.css`, AFTER the `.dark` block (must win the equal-specificity cascade, same rule as `.theme-terminal`):

```css
  /*
   * Premium Dark — indigo glass and glow. Layered on top of `.dark`
   * (see ThemeProvider), so it must come AFTER the `.dark` block.
   */
  .theme-premium-dark {
    --background: 225 20% 7%;
    --foreground: 228 28% 93%;

    --card: 227 18% 10%;
    --card-foreground: 228 28% 93%;

    --popover: 227 18% 9%;
    --popover-foreground: 228 28% 93%;

    /* Indigo primary — L64 (not 67): white text needs >=4.5:1 per review */
    --primary: 239 84% 64%;
    --primary-foreground: 0 0% 100%;

    --secondary: 228 16% 16%;
    --secondary-foreground: 228 28% 93%;

    --muted: 228 16% 13%;
    --muted-foreground: 227 14% 60%;

    /* Violet accent — darkened for AA with white text */
    --accent: 258 84% 62%;
    --accent-foreground: 0 0% 100%;

    --destructive: 0 72% 53%;
    --destructive-foreground: 0 0% 100%;

    --success: 160 64% 52%;
    --success-foreground: 160 60% 8%;

    --warning: 43 96% 56%;
    --warning-foreground: 30 40% 8%;

    --border: 222 19% 20%;
    --input: 222 19% 18%;
    --ring: 239 84% 64%;

    --radius: 0.75rem;

    --chart-1: 239 84% 64%;
    --chart-2: 258 90% 66%;
    --chart-3: 160 64% 52%;
    --chart-4: 43 96% 56%;
    --chart-5: 199 89% 48%;
    --chart-grid: 222 19% 20%;

    --sidebar-background: 225 18% 8%;
    --sidebar-foreground: 227 14% 62%;
    --sidebar-primary: 239 84% 64%;
    --sidebar-primary-foreground: 0 0% 100%;
    --sidebar-accent: 233 30% 17%;
    --sidebar-accent-foreground: 228 28% 93%;
    --sidebar-border: 224 18% 14%;
    --sidebar-ring: 239 84% 64%;
  }
```

- [ ] **Step 5: Add the scoped flourishes** — at the END of `ui/src/index.css` (mirroring the terminal-theme section):

```css
/* ============================================================
 * Premium Dark theme — scoped glass & glow flourishes
 * Everything lives under `.theme-premium-dark`, so other themes
 * are never affected.
 * ========================================================== */

/* Subtle indigo wash behind everything */
.theme-premium-dark body {
  background:
    radial-gradient(90% 60% at 12% 0%, hsl(248 40% 14% / 0.55), transparent 60%),
    linear-gradient(160deg, hsl(228 20% 9%), hsl(225 20% 7%));
  background-attachment: fixed;
}

/* Glassy cards */
.theme-premium-dark .bg-card {
  background-color: hsl(var(--card) / 0.6);
  backdrop-filter: blur(10px);
}

/* Soft neon glow on primary-filled buttons/links. Scoped to interactive
 * elements (a bare .bg-primary match would also hit badges, progress bars,
 * calendar cells) and composed with Tailwind's ring/shadow variables so
 * keyboard-focus rings and shadow utilities still render on top. */
.theme-premium-dark button.bg-primary,
.theme-premium-dark a.bg-primary {
  box-shadow:
    var(--tw-ring-offset-shadow, 0 0 #0000),
    var(--tw-ring-shadow, 0 0 #0000),
    0 0 16px hsl(var(--primary) / 0.35),
    var(--tw-shadow, 0 0 #0000);
}

@media (prefers-reduced-motion: reduce) {
  .theme-premium-dark body {
    background-attachment: scroll;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .theme-premium-dark .bg-card {
    background-color: hsl(var(--card));
    backdrop-filter: none;
  }
}
```

- [ ] **Step 6: Run the test — verify it PASSES**

Run: `cd ui && npx vitest run src/components/__tests__/ThemeProvider.test.tsx`
Expected: 3 passed.

- [ ] **Step 7: Typecheck** (the ThemeId union change can surface exhaustiveness errors elsewhere)

Run: `cd ui && npx tsc --noEmit`
Expected: no new errors vs. baseline.

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/__tests__/ThemeProvider.test.tsx ui/src/components/ui/theme-provider.tsx ui/src/index.css
git commit -m "feat(theme): add Premium Dark theme with glass/glow flourishes"
```

---

### Task 5: Paper sidebar — sweep AppSidebar's hardcoded colors

Replace every `slate-*`/`blue-*`/`indigo-*` utility in the sidebar with `sidebar-*` token classes (Tailwind `sidebar` colors are already configured in `tailwind.config.ts:112-121`).

**Files:**
- Modify: `ui/src/components/layout/AppSidebar.tsx` (28 hardcoded-color occurrences, lines ~490-680)

- [ ] **Step 1: Apply this exact mapping** everywhere it appears in the file (several appear 3× because main/settings/plugin menus repeat the markup):

| Current | Replacement |
|---|---|
| `bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-r border-slate-700/50 shadow-2xl backdrop-blur-xl` | `bg-sidebar text-sidebar-foreground border-r border-sidebar-border` |
| `border-b border-slate-700/30` | `border-b border-sidebar-border` |
| `border-t border-slate-700/30` (footer + dividers) | `border-t border-sidebar-border` |
| `bg-gradient-to-b from-slate-900 via-slate-900/80 to-transparent` (scroll-up fade) | `bg-gradient-to-b from-sidebar via-sidebar/80 to-transparent` |
| `bg-gradient-to-t from-slate-900 via-slate-900/80 to-transparent` (scroll-down fade) | `bg-gradient-to-t from-sidebar via-sidebar/80 to-transparent` |
| `bg-blue-600/90 border-blue-400/60 text-white hover:bg-blue-500 ring-2 ring-blue-400/40` (scroll button, active) | `bg-sidebar-primary/90 border-sidebar-primary/60 text-sidebar-primary-foreground hover:bg-sidebar-primary ring-2 ring-sidebar-ring/40` |
| `bg-slate-800/80 border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700` (scroll button, idle) | `bg-sidebar-accent/80 border-sidebar-border text-sidebar-foreground/70 hover:text-sidebar-accent-foreground hover:bg-sidebar-accent` |
| `text-slate-400 uppercase tracking-wider` (section headings) | `text-sidebar-foreground/60 uppercase tracking-wider` |
| `bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20` (active nav item) | `bg-sidebar-primary text-sidebar-primary-foreground shadow-sm ring-1 ring-sidebar-ring/30` |
| `text-slate-300 hover:text-white hover:bg-slate-700/30 hover:shadow-sm` (idle nav item) | `text-sidebar-foreground/80 hover:text-sidebar-accent-foreground hover:bg-sidebar-accent hover:shadow-sm` |
| `bg-slate-700/30 group-hover:bg-slate-600/30` (icon chip) | `bg-sidebar-accent/60 group-hover:bg-sidebar-accent` |
| `ring-2 ring-slate-600/30` (avatar) | `ring-2 ring-sidebar-border` |
| `bg-gradient-to-br from-blue-500 to-indigo-600 text-white` (avatar fallback) | `bg-sidebar-primary text-sidebar-primary-foreground` |

Leave any class not in this table untouched. If a string in the table appears with minor whitespace/order differences, match on the color utilities and replace just those.

- [ ] **Step 2: Verify the file is clean**

Run: `cd ui && grep -cE "slate-|blue-[0-9]|indigo-" src/components/layout/AppSidebar.tsx`
Expected: `0`

- [ ] **Step 3: Check sibling layout files for stragglers**

Run: `cd ui && grep -nE "slate-|blue-[0-9]|indigo-" src/components/layout/*.tsx`
Expected output review: apply the same mapping to any hits in `OrganizationSwitcher.tsx` / `AppHeader.tsx` / `AppLayout.tsx` (header had 0 at planning time; the switcher renders inside the sidebar so it must use `sidebar-*` tokens too).

- [ ] **Step 4: Typecheck + existing sidebar-adjacent tests**

Run: `cd ui && npx tsc --noEmit && npx vitest run src/components/__tests__ 2>&1 | tail -5`
Expected: no new failures vs. baseline.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/layout/
git commit -m "feat(theme): tokenize sidebar — paper sidebar in light, ink in dark"
```

---

### Task 6: Theme-aware charts — InvoiceChart

Replace the hardcoded hex palette with chart tokens. SVG `fill`/`stroke` are CSS properties, so `hsl(var(--chart-1))` resolves live and charts re-color on theme switch (same pattern ShadCN charts use).

**Files:**
- Modify: `ui/src/components/dashboard/InvoiceChart.tsx:129` (grid), `:160-166` (tooltip), `:211-261` (bars)

- [ ] **Step 1: Tokenize grid and tooltip**

Line 129:

```tsx
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--chart-grid))" />
```

Lines 160-166 (`contentStyle`):

```tsx
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    color: "hsl(var(--popover-foreground))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)",
                    boxShadow: "0 2px 8px rgba(0, 0, 0, 0.15)",
                  }}
```

- [ ] **Step 2: Replace the per-currency hex map** (lines 211-261). Series colors are now semantic and theme-driven; currencies are distinguished by an opacity ladder instead of bespoke hex tables:

```tsx
                ))).map((currency, currencyIndex) => {
                  // Semantic, theme-driven series colors; currencies are
                  // distinguished by opacity so every theme stays on-palette.
                  const seriesColors = {
                    paid: "hsl(var(--chart-1))",
                    partiallyPaid: "hsl(var(--chart-2))",
                    pending: "hsl(var(--chart-3))",
                  };
                  const CURRENCY_OPACITIES = [1, 0.78, 0.6, 0.45, 0.34];
                  const fillOpacity =
                    CURRENCY_OPACITIES[currencyIndex % CURRENCY_OPACITIES.length];

                  return (
                    <React.Fragment key={currency}>
                      <Bar
                        dataKey={`paid_${currency}`}
                        name={`Paid (${currency})`}
                        fill={seriesColors.paid}
                        fillOpacity={fillOpacity}
                        radius={[4, 4, 0, 0]}
                        stackId={`stack_${currency}`}
                      />
                      <Bar
                        dataKey={`partiallyPaid_${currency}`}
                        name={`Partially Paid (${currency})`}
                        fill={seriesColors.partiallyPaid}
                        fillOpacity={fillOpacity}
                        radius={[4, 4, 0, 0]}
                        stackId={`stack_${currency}`}
                      />
                      <Bar
                        dataKey={`pending_${currency}`}
                        name={`Pending (${currency})`}
                        fill={seriesColors.pending}
                        fillOpacity={fillOpacity}
                        radius={[4, 4, 0, 0]}
                        stackId={`stack_${currency}`}
                      />
                    </React.Fragment>
                  );
                })}
```

- [ ] **Step 3: Verify no hex colors remain**

Run: `cd ui && grep -cE "#[0-9A-Fa-f]{6}" src/components/dashboard/InvoiceChart.tsx`
Expected: `0`

- [ ] **Step 4: Typecheck**

Run: `cd ui && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/dashboard/InvoiceChart.tsx
git commit -m "feat(theme): drive InvoiceChart colors from chart tokens"
```

---

### Task 7: Dashboard sweep — widgets + dashboard CSS

Replace decorative hardcoded colors in dashboard components and the dashboard CSS with semantic tokens.

**Files:**
- Modify: `ui/src/components/dashboard/RecentActivity.tsx`, `ExpectedPaymentsCard.tsx`, `ProfessionalDashboard.tsx`, `QuickActions.tsx`, `QuickActionsDemo.tsx`, `QuickActionsLoading.tsx`, `QuickActions.module.css`
- Modify: `ui/src/index.css:607-695` (`.professional-card`)
- Audit: `ui/src/styles/professional-enhancements.css`

- [ ] **Step 1: Apply this token mapping across the dashboard components** (find each with `cd ui && grep -rnE "slate-|blue-[0-9]|indigo-|purple-|violet-" src/components/dashboard/`):

| Hardcoded pattern | Replacement |
|---|---|
| `text-blue-600`, `text-blue-500`, `text-blue-400` | `text-primary` |
| `text-indigo-600`, `text-indigo-500` | `text-accent` |
| `ring-blue-500/50` | `ring-ring/50` |
| `bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400` (badges) | `bg-primary/10 text-primary` |
| `bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400` (badges) | `bg-accent/10 text-accent` |
| `bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/25` | `bg-primary/10 text-primary border-primary/25` |
| `bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200` | `bg-accent/10 border border-accent/20` |
| Other `slate-N` text/bg/border | `muted`/`muted-foreground`/`border` equivalents at the same role (e.g. `text-slate-500` → `text-muted-foreground`, `bg-slate-100` → `bg-muted`, `border-slate-200` → `border-border`) |

Status colors that are ALREADY semantic (`text-success`, `text-destructive`, `status-paid`, etc.) stay untouched. Greens/ambers/roses tied to financial meaning stay on their semantic tokens.

- [ ] **Step 2: Tokenize `.professional-card`** in `ui/src/index.css` (lines ~607-695). Replace the hardcoded white/black rgba values:

```css
.professional-card {
  background: hsl(var(--card) / 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid hsl(var(--border) / 0.6);
  border-radius: 16px;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.08),
    0 1px 3px rgba(0, 0, 0, 0.12);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
```

and the dark variant:

```css
.dark .professional-card {
  background: hsl(var(--card) / 0.75);
  border: 1px solid hsl(var(--border) / 0.5);
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.3),
    0 1px 3px rgba(0, 0, 0, 0.4);
}
```

Also replace the stat-card gradient at `ui/src/index.css:698-707`:

```css
.professional-dashboard .grid > div > div[class*="border-l-4"] {
  background: hsl(var(--card) / 0.85);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  transition: all 0.2s ease;
}
```

(Black-based shadow rgba values may stay — shadows read fine on every theme.)

- [ ] **Step 3: Audit the imported stylesheet**

Run: `cd ui && grep -nE "slate|#[0-9A-Fa-f]{6}|rgba\(2[0-9][0-9]" src/styles/professional-enhancements.css | head -30`
Apply the same principle to any hits **used by dashboard components**: surface colors → `hsl(var(--card) / α)`, text → `hsl(var(--foreground) / α)`, accents → `hsl(var(--primary) / α)`. Leave rules that only affect non-dashboard pages for Phase 2 (note them in the commit message instead).

- [ ] **Step 4: Verify dashboard is clean + tests pass**

Run: `cd ui && grep -rcE "slate-|blue-[0-9]|indigo-|purple-" src/components/dashboard/ | grep -v ":0"`
Expected: no output.
Run: `cd ui && npx vitest run src/components/dashboard 2>&1 | tail -5`
Expected: existing QuickActions tests pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/dashboard/ ui/src/index.css ui/src/styles/professional-enhancements.css
git commit -m "feat(theme): sweep dashboard hardcoded colors onto semantic tokens"
```

---

### Task 8: Full verification + QA matrix

**Files:** none modified (fix-forward if issues found).

- [ ] **Step 1: Full frontend test suite**

Run: `docker compose exec ui npx vitest run` (fallback: `cd ui && npx vitest run`)
Expected: no failures that didn't exist at the Task 1 baseline.

- [ ] **Step 2: Typecheck + production build**

Run: `cd ui && npx tsc --noEmit && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 3: Repo-wide regression greps**

Run: `cd ui && grep -rn "Plus Jakarta\|DM Serif" src/ ; grep -rnE "from-slate-900" src/components/layout/`
Expected: no matches.

- [ ] **Step 4: Manual QA matrix** (needs `docker-compose up`; if the stack can't run, hand this checklist to Hao):

For each of **Light, Dark, Premium Dark** (switch in Settings → Appearance):
1. Dashboard: stat cards, InvoiceChart (bars use theme palette; grid/tooltip themed), Recent Invoices, Quick Actions, greeting header — no navy/teal/slate remnants, text contrast OK.
2. Sidebar: paper in Light / warm ink in Dark / indigo in Premium Dark; active item legible; scroll fades match background; org switcher and avatar legible.
3. Theme picker: new swatches render; selection persists across reload (localStorage + `PUT /auth/me` fires when logged in).

Spot-check **Terminal** and **Sepia**: dashboard + sidebar still render their own palettes (no warm-paper leak); InvoiceChart uses their chart tokens.

- [ ] **Step 5: Update the spec status + commit any QA fixes**

```bash
git add -A
git commit -m "fix(theme): QA fixes from Phase 1 theme matrix"
```

(Skip the commit if QA found nothing.)

---

## Out of scope (Phase 2+)

- Invoices/Clients/Settings/Login sweeps; `financial.*` palette in `tailwind.config.ts`; non-dashboard rules in `professional-enhancements.css`.
- Editorial (C) and Bold Tech (D) themes.
- Backend changes — none needed (`theme` is a free-form `Optional[str]` in `api/core/schemas/user.py:15`; `useThemePreference` already syncs any id).
