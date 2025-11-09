# Kafka Message Cleanup Improvement

## Problem Statement

Currently, when an invoice, expense, or statement is deleted from the database, the corresponding Kafka messages in the processing queues are **NOT** automatically removed or cancelled. This leads to several issues:

### Current Behavior

1. **Invoice Deletion** (`api/routers/invoices.py:1765`)
   - Performs soft delete (sets `is_deleted = True`)
   - Unlinks bank transactions
   - Updates invoice history
   - **Does NOT** touch Kafka messages or processing tasks

2. **Expense Deletion** (`api/routers/expenses.py:794`)
   - Performs hard delete from database
   - Deletes associated files from storage
   - Unlinks bank transactions
   - **Does NOT** remove Kafka messages

3. **Statement Deletion** (`api/routers/statements.py:606`)
   - Performs hard delete from database
   - Deletes file from storage
   - **Does NOT** remove Kafka messages

### Issues

- **Wasted Resources**: OCR consumers continue processing deleted documents
- **Error Logs**: Consumer fails when trying to update non-existent records
- **Monitoring Confusion**: Failed processing attempts clutter logs and metrics
- **Inefficient Queue Management**: Messages remain in queue until natural expiration
- **User Experience**: Processing notifications may still be sent for deleted items

## Technical Background

### Kafka Message Lifecycle

Kafka messages are **immutable** once published. They are removed by:
1. **Time-based retention** (default: 7 days)
2. **Size-based retention** (when topic reaches size limit)
3. **Consumer consumption** (marked as consumed, not immediately deleted)

Messages are **NOT** removed by application-level deletion of related database records.

### Current Processing Flow

```
1. Document uploaded → Message published to Kafka topic
   - invoice_ocr
   - expense_ocr
   - bank_statements_ocr

2. Message tracked in database:
   - BatchFileProcessing (for batch uploads)
   - InvoiceProcessingTask (for invoice processing)

3. OCR Consumer processes message:
   - Reads from Kafka topic
   - Processes document
   - Updates database record

4. If document deleted:
   - Database record removed/marked deleted
   - Kafka message REMAINS in queue
   - Consumer processes message → fails to find record
```

### Relevant Code Locations

- **Message Publishing**: `api/services/batch_processing_service.py:463-700`
- **OCR Consumer**: `api/workers/ocr_consumer.py`
- **Delete Endpoints**:
  - Invoices: `api/routers/invoices.py:1765`
  - Expenses: `api/routers/expenses.py:794`
  - Statements: `api/routers/statements.py:606`
- **Processing Tasks**: `api/models/models_per_tenant.py:814` (InvoiceProcessingTask)

## Proposed Solutions

### Option 1: Pre-Processing Validation (Recommended)

Add validation in OCR consumer to check if record still exists before processing.

**Pros:**
- Simple to implement
- No changes to Kafka infrastructure
- Gracefully handles race conditions
- Works with existing message retention

**Cons:**
- Messages still consume queue space until expiration
- Slight processing overhead for validation check

**Implementation:**
```python
# In api/workers/ocr_consumer.py

async def process_message(self, message):
    # Extract document info
    doc_id = message.get('document_id')
    doc_type = message.get('document_type')
    
    # Validate record still exists
    if not await self._validate_record_exists(doc_id, doc_type):
        logger.info(f"Skipping processing: {doc_type} {doc_id} no longer exists")
        return ProcessingResult(
            success=True,
            committed=True,
            status=ProcessingStatus.SKIPPED
        )
    
    # Continue with normal processing
    ...
```

### Option 2: Processing Task Cancellation

Mark processing tasks as "cancelled" in database when document is deleted.

**Pros:**
- Clear audit trail of cancellations
- Consumer can check cancellation status
- Supports partial processing scenarios

**Cons:**
- Requires database schema changes
- More complex deletion logic
- Still doesn't remove Kafka messages

**Implementation:**

1. Add `cancellation_status` to processing task models:
```python
# In api/models/models_per_tenant.py

class InvoiceProcessingTask(Base):
    # ... existing fields ...
    cancellation_status = Column(String, nullable=True)  # null, 'requested', 'cancelled'
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
```

2. Update delete endpoints to mark tasks as cancelled:
```python
# In api/routers/invoices.py

async def delete_invoice(invoice_id: int, ...):
    # ... existing deletion logic ...
    
    # Cancel any pending processing tasks
    processing_tasks = db.query(InvoiceProcessingTask).filter(
        InvoiceProcessingTask.invoice_id == invoice_id,
        InvoiceProcessingTask.status.in_(['queued', 'processing'])
    ).all()
    
    for task in processing_tasks:
        task.cancellation_status = 'cancelled'
        task.cancelled_at = datetime.now(timezone.utc)
        task.cancelled_by = current_user.id
    
    db.commit()
```

3. Check cancellation in consumer:
```python
# In api/workers/ocr_consumer.py

async def process_message(self, message):
    task_id = message.get('task_id')
    
    # Check if task was cancelled
    task = db.query(InvoiceProcessingTask).filter(
        InvoiceProcessingTask.task_id == task_id
    ).first()
    
    if task and task.cancellation_status == 'cancelled':
        logger.info(f"Skipping cancelled task: {task_id}")
        return ProcessingResult(success=True, status=ProcessingStatus.SKIPPED)
    
    # Continue processing
    ...
```

### Option 3: Kafka Message Headers with TTL

Use Kafka message headers to track deletion status and implement custom TTL.

**Pros:**
- Most comprehensive solution
- Reduces queue bloat
- Better resource utilization

**Cons:**
- Complex implementation
- Requires Kafka infrastructure changes
- May need custom consumer logic
- Potential for message loss if not careful

**Implementation:**
- Add deletion tracking service
- Publish deletion events to separate topic
- Consumer checks deletion topic before processing
- Implement custom message expiration logic

### Option 4: Hybrid Approach (Best Long-term Solution)

Combine Options 1 and 2 for immediate safety and future scalability.

**Phase 1 (Immediate):**
- Implement pre-processing validation (Option 1)
- Add logging for skipped messages

**Phase 2 (Short-term):**
- Add cancellation status to processing tasks (Option 2)
- Update delete endpoints to mark tasks as cancelled
- Update consumer to check cancellation status

**Phase 3 (Long-term):**
- Monitor metrics on skipped/cancelled messages
- If volume is high, consider Option 3 for queue optimization

## Recommended Implementation Plan

### Phase 1: Quick Fix (1-2 days)

1. Add validation helper in OCR consumer:
```python
async def _validate_record_exists(self, doc_id, doc_type, tenant_id, db):
    """Check if document record still exists before processing"""
    if doc_type == 'invoice':
        from models.models_per_tenant import Invoice
        record = db.query(Invoice).filter(
            Invoice.id == doc_id,
            Invoice.is_deleted == False
        ).first()
    elif doc_type == 'expense':
        from models.models_per_tenant import Expense
        record = db.query(Expense).filter(Expense.id == doc_id).first()
    elif doc_type == 'statement':
        from models.models_per_tenant import BankStatement
        record = db.query(BankStatement).filter(
            BankStatement.id == doc_id
        ).first()
    else:
        return False
    
    return record is not None
```

2. Update message processing to validate before OCR:
```python
# In each document handler (ExpenseHandler, InvoiceHandler, etc.)
if not await self._validate_record_exists(...):
    logger.info(f"Skipping deleted {doc_type}: {doc_id}")
    return ProcessingResult(success=True, status=ProcessingStatus.SKIPPED)
```

3. Add metrics for skipped messages

### Phase 2: Proper Cancellation (1 week)

1. Create migration to add cancellation fields
2. Update delete endpoints to mark tasks as cancelled
3. Update consumer to check cancellation status
4. Add cancellation audit logging

### Phase 3: Monitoring & Optimization (Ongoing)

1. Monitor skipped/cancelled message rates
2. Analyze queue performance
3. Adjust Kafka retention policies if needed
4. Consider Option 3 if queue bloat becomes an issue

## Metrics to Track

- Number of messages skipped due to deleted records
- Processing time saved by early validation
- Error rate reduction in OCR consumer
- Queue depth and message age
- Cancellation request frequency

## Testing Considerations

1. **Race Condition Testing**
   - Delete document while processing is in progress
   - Verify graceful handling

2. **Batch Processing**
   - Delete batch job with pending files
   - Verify all files are properly cancelled

3. **Performance Testing**
   - Measure validation overhead
   - Ensure no significant latency increase

4. **Error Handling**
   - Database connection failures during validation
   - Kafka consumer failures

## Related Documentation

- Batch Processing API: `api/docs/BATCH_PROCESSING_API.md`
- OCR Consumer: `api/workers/ocr_consumer.py`
- Processing Locks: `docs/PROCESSING_LOCKS_FIX.md`
- Batch Completion: `docs/BATCH_COMPLETION_IMPLEMENTATION_SUMMARY.md`

## Priority

**Medium-High**: While not causing critical failures, this improvement would:
- Reduce wasted processing resources
- Clean up error logs
- Improve monitoring clarity
- Enhance user experience
- Prevent confusion during debugging

## Estimated Effort

- **Phase 1 (Quick Fix)**: 1-2 days
- **Phase 2 (Cancellation)**: 1 week
- **Phase 3 (Monitoring)**: Ongoing

Total initial implementation: ~1.5 weeks
