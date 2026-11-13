# Project profitability browser evidence

Captured in installed Chrome using the actual `ProjectDetailInternal`, profitability components, hooks, translations, styles, and timer provider. Synthetic API responses supplied an owner, an hourly project, two time entries, and one expense; no customer data was used.

Source: `72538ad1`, including final supplier-evidence, reimbursement display, action-error and readability fixes. A temporary source-only Vite checkout excluded unrelated local plugins. Only its cache path and HMR port were overridden for local execution. This verifies browser presentation and frontend access handling, not deployed API behavior; backend authenticated HTTP and database tests are reported separately.

- [Complete](complete.png): 1,000 USD work value, 580 USD known cost, 420 USD contribution, 42% margin; invoice and cash amounts remain separate; attributed reimbursements show 100 USD with their proportional discount basis.
- [Incomplete](incomplete.png): missing costs withhold contribution/margin and show unresolved records.
- [Empty](empty.png): zero work/cost values and unavailable percentage margin render without errors.
- [Unauthorized](unauthorized.png): ordinary tenant member does not receive the profitability tab or its controls.
- [Mobile](mobile.png): 390px viewport, stacked cards/forms, wrapping header controls and bounded tab scrolling. Document width does not exceed viewport width.

All five captures completed with zero browser page errors. Desktop viewport was 1365×1000; screenshots capture the full page. No production deployment or live customer interaction occurred.
