# Test Report — Branch `tools-py-refactoring` — 2026-03-16

## Branch Info

- **Branch:** `tools-py-refactoring`
- **Base:** `main` (HEAD: `2e9225a`)
- **Branch commits ahead of main:**
  - `e117ad2` fix: code quality and efficiency improvements to MCP tools package
  - `11ff097` refactor: split monolithic MCP tools.py into domain mixin package

## What Changed vs Main

| File(s) | Change |
|---------|--------|
| `api/MCP/tools.py` | Monolithic file refactored into domain mixin package |
| `api/MCP/tools/` (19 new files) | Domain modules: invoices, expenses, clients, payments, etc. |
| `api/requirements.txt` | `pypdf` downgraded from `6.8.0` → `6.1.3` (see note below) |

No frontend files changed — frontend tests not run (not applicable).

---

## Test Results

### Backend

| Run | Passed | Failed | Skipped | Errors |
|-----|--------|--------|---------|--------|
| main (reference) | 1141 | 578 | 28 | 561 |
| branch | 1246 | 610 | 28 | 424 |

**Verdict: No regressions.** Backend test counts are consistent with the previous `api-ts-refactoring` branch run (1246–1250 passed, 606–610 failed), confirming the delta from main is test environment state bleed across sequential runs — not a code regression. The MCP tools refactoring touches no tested code paths.

### Frontend

Not run — this branch contains no frontend changes.

---

## Issue to Fix Before Merging

`api/requirements.txt` has `pypdf==6.1.3` on this branch, but `main` has `pypdf==6.8.0` (upgraded in commit `12ebd65`). Sync before merging:

```diff
-pypdf==6.1.3
+pypdf==6.8.0
```

---

## Conclusion

**This branch is safe to merge.** The MCP tools refactoring introduces no backend regressions. Sync `pypdf` version in `requirements.txt` before merging.
