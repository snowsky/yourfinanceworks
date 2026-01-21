# Invoice Approval Database Schema

## New Table: `invoice_approvals`

The `invoice_approvals` table mirrors the structure of `expense_approvals` to support multi-level approval workflows for invoices.

### Schema Definition

```sql
CREATE TABLE invoice_approvals (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    approver_id INTEGER NOT NULL REFERENCES users(id),
    approval_rule_id INTEGER REFERENCES approval_rules(id),
    status VARCHAR NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    rejection_reason TEXT,
    notes TEXT,
    submitted_at TIMESTAMP WITH TIMEZONE NOT NULL,
    decided_at TIMESTAMP WITH TIMEZONE,
    approval_level INTEGER NOT NULL DEFAULT 1,
    is_current_level BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIMEZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIMEZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Column Descriptions

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | NO | Primary key, auto-increment |
| `invoice_id` | INTEGER | NO | Foreign key to invoices table |
| `approver_id` | INTEGER | NO | Foreign key to users table (the approver) |
| `approval_rule_id` | INTEGER | YES | Foreign key to approval_rules table (optional) |
| `status` | VARCHAR | NO | Approval status: 'pending', 'approved', or 'rejected' |
| `rejection_reason` | TEXT | YES | Reason for rejection (only populated if rejected) |
| `notes` | TEXT | YES | Additional notes from approver |
| `submitted_at` | TIMESTAMP | NO | When the invoice was submitted for approval |
| `decided_at` | TIMESTAMP | YES | When the approval decision was made |
| `approval_level` | INTEGER | NO | Approval level (1, 2, 3, etc. for multi-level workflows) |
| `is_current_level` | BOOLEAN | NO | Whether this is the current approval level |
| `created_at` | TIMESTAMP | NO | Record creation timestamp |
| `updated_at` | TIMESTAMP | NO | Record last update timestamp |

### Relationships

- **invoice_id** → `invoices.id`: One-to-many relationship (one invoice can have multiple approvals)
- **approver_id** → `users.id`: Many-to-one relationship (one user can approve multiple invoices)
- **approval_rule_id** → `approval_rules.id`: Optional many-to-one relationship (approval may be based on a rule)

### Indexes

Recommended indexes for performance:

```sql
CREATE INDEX idx_invoice_approvals_invoice_id ON invoice_approvals(invoice_id);
CREATE INDEX idx_invoice_approvals_approver_id ON invoice_approvals(approver_id);
CREATE INDEX idx_invoice_approvals_status ON invoice_approvals(status);
CREATE INDEX idx_invoice_approvals_approval_level ON invoice_approvals(approval_level);
CREATE INDEX idx_invoice_approvals_is_current_level ON invoice_approvals(is_current_level);
CREATE INDEX idx_invoice_approvals_submitted_at ON invoice_approvals(submitted_at);
```

## Modified Table: `invoices`

Added relationship to support approvals:

```python
approvals = relationship("InvoiceApproval", back_populates="invoice", cascade="all, delete-orphan")
```

This allows:
- Accessing all approvals for an invoice: `invoice.approvals`
- Cascading deletion of approvals when invoice is deleted

## Workflow States

### Invoice Status Transitions

```
draft → pending_approval → approved → paid
                        ↓
                      rejected
```

### Approval Status Values

- **pending**: Approval is awaiting decision
- **approved**: Approval has been granted
- **rejected**: Approval has been denied

### Multi-Level Approval Example

For an invoice requiring 2-level approval:

1. **Level 1 Approval**
   - `approval_level = 1`
   - `is_current_level = True`
   - Status: pending → approved
   - Once approved, moves to Level 2

2. **Level 2 Approval**
   - `approval_level = 2`
   - `is_current_level = True` (after Level 1 is approved)
   - Status: pending → approved
   - Once approved, invoice is fully approved

## Data Integrity

### Cascade Delete
- When an invoice is deleted, all associated approvals are automatically deleted
- This maintains referential integrity

### Unique Constraints
- No unique constraints on invoice_approvals (multiple approvals per invoice are expected)
- Approval level and current level status are managed by application logic

### Audit Trail
- All approval decisions are permanently recorded
- `decided_at` timestamp captures when decision was made
- `rejection_reason` provides context for rejections
- `notes` field allows approvers to add comments

## Query Examples

### Get Pending Approvals for a User
```sql
SELECT * FROM invoice_approvals
WHERE approver_id = ? 
  AND status = 'pending'
  AND is_current_level = TRUE
ORDER BY submitted_at ASC;
```

### Get Approval History for an Invoice
```sql
SELECT * FROM invoice_approvals
WHERE invoice_id = ?
ORDER BY approval_level ASC, submitted_at ASC;
```

### Get Approved Invoices
```sql
SELECT DISTINCT i.* FROM invoices i
JOIN invoice_approvals ia ON i.id = ia.invoice_id
WHERE ia.status = 'approved'
  AND ia.approval_level = (
    SELECT MAX(approval_level) FROM invoice_approvals 
    WHERE invoice_id = i.id
  );
```

### Get Rejected Invoices
```sql
SELECT DISTINCT i.* FROM invoices i
JOIN invoice_approvals ia ON i.id = ia.invoice_id
WHERE ia.status = 'rejected'
ORDER BY ia.decided_at DESC;
```

## Performance Considerations

1. **Indexing**: The recommended indexes above should be created for optimal query performance
2. **Pagination**: Use `LIMIT` and `OFFSET` for large result sets
3. **Soft Deletes**: Consider implementing soft deletes for audit compliance
4. **Archive**: Old approval records can be archived to maintain performance

## Migration Path

### From Existing System
If migrating from a system without invoice approvals:

1. Create the `invoice_approvals` table
2. No data migration needed (new table is empty)
3. Existing expense approvals remain unchanged
4. Invoice approval feature is available immediately after migration

### Alembic Migration Example
```python
def upgrade():
    op.create_table(
        'invoice_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), nullable=False),
        sa.Column('approval_rule_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_current_level', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approval_rule_id'], ['approval_rules.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_invoice_approvals_invoice_id', 'invoice_approvals', ['invoice_id'])
    op.create_index('idx_invoice_approvals_approver_id', 'invoice_approvals', ['approver_id'])
    op.create_index('idx_invoice_approvals_status', 'invoice_approvals', ['status'])
    op.create_index('idx_invoice_approvals_approval_level', 'invoice_approvals', ['approval_level'])
    op.create_index('idx_invoice_approvals_is_current_level', 'invoice_approvals', ['is_current_level'])
    op.create_index('idx_invoice_approvals_submitted_at', 'invoice_approvals', ['submitted_at'])

def downgrade():
    op.drop_index('idx_invoice_approvals_submitted_at', table_name='invoice_approvals')
    op.drop_index('idx_invoice_approvals_is_current_level', table_name='invoice_approvals')
    op.drop_index('idx_invoice_approvals_approval_level', table_name='invoice_approvals')
    op.drop_index('idx_invoice_approvals_status', table_name='invoice_approvals')
    op.drop_index('idx_invoice_approvals_approver_id', table_name='invoice_approvals')
    op.drop_index('idx_invoice_approvals_invoice_id', table_name='invoice_approvals')
    op.drop_table('invoice_approvals')
```
