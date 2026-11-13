# Implementation decisions

These decisions were made during the approved implementation. Potential costs are included so they can be reviewed before integration.

1. Use isolated dependency/test fixtures because the shared conftest drops its configured database. Cost: extra harness setup and narrower application-stack coverage.
2. Use disposable PostgreSQL and isolated API containers, never the service database. Cost: production configuration and migration execution remain unverified.
3. Request permission for managed-worktree writes outside writable roots. Cost: approval interruptions.
4. Preserve historical rates and nullable source references rather than cascading their deletion. Cost: retained internal history needs normal retention controls.
5. A supplier entry linked to an excluded/rejected expense remains unresolved. Cost: estimates remain incomplete until an administrator reconciles the links.
6. Unsupported refunds/credits remain unallocated. Cost: collections reporting is incomplete for those invoices.
7. After worktree-write approval was aborted, move only scoped candidates to the writable checkout on a feature branch, preserving the managed worktree. Cost: an extra recovery worktree remains.
8. Repair migration025's parent identifier to the actual024 revision. Cost: historical migration graph change requires deployment review.
9. Add private revision table029 for cost-method replacement history. Cost: another tenant migration and retained sensitive audit storage.
10. Add durable invoice links and fingerprints in030. Cost: additional storage and conservative unresolved states after invoice edits.
11. Implement separately attributed reimbursements required by the approved spec but omitted from the plan; allocate supported discounts proportionally and label the basis. Cost: that operational allocation may differ from a customer's accounting allocation.

12. Preserve supplier expense IDs after expense deletion via migration031, with live links validated on explicit replacement. Cost: historical IDs intentionally outlive their expense rows; administrators must reconcile missing expenses.

No production migration, release, push, or deployment was performed. See VALIDATION.md for evidence and limitations.
