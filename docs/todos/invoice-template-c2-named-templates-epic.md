# Invoice Template Editor — C2: Named / Multiple Templates (Epic Stub)

**Feature:** Competitor #5 — invoice template editor.
**Status:** Deferred epic stub (not built in Slice C).

## Summary

Move from one invoice template config per tenant to N named templates, each with independent branding/layout settings, allowing tenants to create and manage multiple invoice designs with a per-invoice selector.

---

## Storage Change

Currently, invoice branding and layout config persists in a single flat `invoice_branding` Settings row per tenant. C2 replaces this with a new per-tenant storage collection:

- **Schema decision:** either a new `invoice_templates` table (per repo convention, likely created via `db_init.py` rather than Alembic — the C2 spec must decide the schema-management approach) or a keyed settings collection (e.g., `invoice_template_<id>`), each holding a full branding/layout config blob (brand colors, fonts, logo, section order, line-item columns, custom-field layout, etc.).
- **Default template:** one template per tenant marked as default, used when an invoice does not specify a template.
- **Tenant isolation:** each tenant has independent templates; no shared templates across tenants.

---

## Per-Invoice Selection

- **Invoice model:** add a `template_id` field (nullable; null → use tenant default).
- **Create/edit UI:** a selector dropdown in the invoice create/edit form to choose which template applies to this invoice.
- **Renderer:** when rendering an invoice, resolve the invoice's `template_id` to its config; if null or not found, fall back to the tenant default.

---

## CRUD UI

Template management UI (new section in invoice settings or a dedicated page):

- **List:** show all templates for the tenant (name, default flag, action menu).
- **Create:** new template dialog (starting from tenant default or a blank/sample config).
- **Rename:** edit template name.
- **Duplicate:** copy an existing template + give it a new name.
- **Delete:** remove a template (prevent deleting the default; offer reassign if any invoices reference it).
- **Set default:** mark one template as the tenant's default.
- **Edit:** reuse the existing two-pane Jinja template editor (left: controls for colors, fonts, logo, section order, columns, layout; right: live preview) for each template.

---

## Surfaces

Every invoice render path must resolve the invoice's `template_id` instead of assuming a single tenant config:

- Web invoice view: resolve template → render.
- Share link: resolve template → render.
- PDF generation (sync and async): resolve template → render.
- Email: resolve template → render.
- Bulk operations (email blast, PDF export): each invoice's template resolved independently.

---

## Next Steps

This epic is **larger and higher-risk** than Slices A/B/C and requires its own full development cycle:

1. **Brainstorm:** settle schema (table vs. settings keyed); tenant UX (how many templates do we expect; creation flows); backward compat (migrate existing `invoice_branding` → default template).
2. **Spec:** detailed design for storage, migration, per-tenant CRUD, per-invoice selector, and render path changes.
3. **Plan:** implementation tasks for backend (models, migrations, API endpoints), frontend (template list/CRUD, invoice selector), and testing.

Do not merge into C1 until C2 is fully scoped and resource-committed.
