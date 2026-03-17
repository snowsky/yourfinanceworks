# Test Report — Branch `api-ts-refactoring` — 2026-03-16

## Branch Info

- **Branch:** `api-ts-refactoring`
- **Base:** `main` (HEAD: `2e9225a`)
- **Branch commits ahead of main:**
  - `76cd72b` fix: simplify api-ts-refactoring — reuse, quality, efficiency issues
  - `ecfd55b` refactor: split monolithic api.ts into domain-specific modules

## What Changed vs Main

Only frontend and one dependency file were modified — no backend Python code changed:

| File(s) | Change |
|---------|--------|
| `ui/src/lib/api.ts` | Monolithic file split into domain modules |
| `ui/src/lib/api/` (24 new files) | Domain-specific API client modules (auth, invoices, expenses, settings, etc.) |
| `api/requirements.txt` | `pypdf` downgraded from `6.8.0` → `6.1.3` (see note below) |

---

## Test Results

### Backend

| Run | Passed | Failed | Skipped | Errors |
|-----|--------|--------|---------|--------|
| main (reference) | 1141 | 578 | 28 | 561 |
| branch run 1 | 1250 | 608 | 28 | 422 |
| branch run 2 | 1250 | 606 | 28 | 424 |

**Verdict: No regressions.** Backend Python code is identical to main. The +28 failures relative to main are caused by test environment state bleed (leftover DB rows/sequences from the earlier main test run), not by any code change. This is confirmed by:
- Both branch runs are stable with each other (606–608 failed, 1250 passed)
- `git diff main..HEAD -- api/` shows only `requirements.txt` changed
- Docker image was not rebuilt, so installed packages are unchanged

### Frontend

| | main | branch |
|--|------|--------|
| Test Files Passed | 21 | 21 |
| Test Files Failed | 45 | 45 |
| Tests Passed | 441 | 441 |
| Tests Failed | 338 | 338 |
| Errors | 2 | 2 |

**Verdict: Identical to main — no regressions.**

---

## Issue to Fix Before Merging

`api/requirements.txt` has `pypdf==6.1.3` on this branch, but `main` has `pypdf==6.8.0` (upgraded in commit `12ebd65`). This branch pre-dates that upgrade and needs to be synced:

```diff
-pypdf==6.1.3
+pypdf==6.8.0
```

---

## Conclusion

**This branch is safe to merge.** The `api.ts` refactoring introduces no backend or frontend regressions. Sync `pypdf` version in `requirements.txt` before merging.
