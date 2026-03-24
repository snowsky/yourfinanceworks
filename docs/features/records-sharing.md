# Record Sharing

Allows users to generate shareable public links for financial records without requiring recipient authentication.

## Overview

Users can share read-only views of invoices, expenses, payments, clients, bank statements, and investment portfolios via tokenized links. Links expire after 1 hour and can be revoked at any time.

## Supported Record Types

| Type | Page Integration |
|------|-----------------|
| `invoice` | ViewInvoice |
| `expense` | ExpensesView |
| `payment` | Payments |
| `client` | EditClient |
| `bank_statement` | Statements |
| `portfolio` | PortfolioDetail (investments plugin) |

## API

### Authenticated Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/share-tokens/` | Create (or return existing active) share token |
| `GET` | `/api/v1/share-tokens/{record_type}/{record_id}` | Get active token for a record |
| `DELETE` | `/api/v1/share-tokens/{token}` | Revoke a token |

**Create request body:**
```json
{ "record_type": "invoice", "record_id": 42 }
```

**Response:**
```json
{
  "token": "a3f8...",
  "record_type": "invoice",
  "record_id": 42,
  "share_url": "https://app.yourfinanceworks.com/shared/a3f8...",
  "created_at": "2026-03-23T22:24:00Z",
  "expires_at": "2026-03-23T23:24:00Z",
  "is_active": true
}
```

### Public Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/shared/{token}` | Fetch sanitized record data (no auth required) |

Returns a sanitized view of the record. The response shape varies by `record_type`.

**Error responses:**
- `404` — token not found or revoked
- `410` — token expired

## Data Model

```python
class ShareToken(Base):
    __tablename__ = "share_tokens"

    id              = Column(Integer, primary_key=True)
    token           = Column(String(64), unique=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"))
    record_type     = Column(String(32))
    record_id       = Column(Integer)
    created_by_user_id = Column(Integer, ForeignKey("master_users.id", ondelete="SET NULL"))
    created_at      = Column(DateTime(timezone=True))
    expires_at      = Column(DateTime(timezone=True))
    is_active       = Column(Boolean, default=True)
```

## Frontend

### ShareButton Component

`ui/src/components/sharing/ShareButton.tsx`

Drop-in button that opens a dialog with the shareable link, copy-to-clipboard, and revoke controls.

```tsx
<ShareButton recordType="invoice" recordId={invoice.id} />
```

Props:
- `recordType` — one of the supported record types
- `recordId` — numeric record ID
- `variant` / `size` — forwarded to the underlying Button component

### Public View Page

`ui/src/pages/SharedRecord.tsx`

Mounted at `/shared/:token` outside `ProtectedRoute`. Renders a read-only view appropriate to the `record_type` returned by the API.

### API Client

`ui/src/lib/api/share-tokens.ts`

```ts
import { shareTokenApi, RecordType } from '@/lib/api/share-tokens';

// Create / get
const token = await shareTokenApi.createToken('invoice', 42);

// Read public record (no auth header sent)
const data = await shareTokenApi.getPublicRecord(token.token);

// Revoke
await shareTokenApi.revokeToken(token.token);
```

`getPublicRecord` uses a raw `fetch` call to avoid injecting the tenant auth header.

## Security Notes

- Tokens are random 32-character hex strings (`uuid4().hex`).
- Each token is scoped to a `tenant_id`; the public endpoint sets tenant context before querying so encrypted columns decrypt correctly.
- The tenant context middleware skips enforcement for `/api/v1/shared/*` paths, but tenant isolation is maintained via the stored `tenant_id`.
- Token creation is idempotent — repeated calls return the existing active non-expired token instead of creating a new one.
- Sanitized schemas (`PublicInvoiceView`, `PublicExpenseView`, etc.) expose only non-sensitive fields.

## Configuration

Token TTL defaults to **1 hour**. To change it, update the `timedelta` in `api/core/routers/share_tokens.py`:

```python
expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
```
