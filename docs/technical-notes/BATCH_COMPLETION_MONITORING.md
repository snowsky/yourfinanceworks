# Batch Completion Monitoring

This document describes the batch completion monitoring system that automatically detects when batch processing jobs are complete and triggers export operations.

## Overview

The batch completion monitoring system consists of two main components:

1. **BatchCompletionMonitor**: A background service that polls for completed jobs every 30 seconds
2. **WebhookNotificationService**: Sends HTTP POST notifications to configured webhook URLs when jobs complete

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         BatchCompletionMonitor Service                   │
│  (Polls every 30 seconds)                               │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Query: processed_files >= total_files                   │
│         AND status = "processing"                        │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│           Export Service                                 │
│  - Generate CSV from processed files                    │
│  - Upload to configured destination                     │
│  - Update job status                                    │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│      WebhookNotificationService                          │
│  - Send POST to webhook_url                             │
│  - Retry up to 3 times on failure                       │
│  - 30-second timeout per request                        │
└─────────────────────────────────────────────────────────┘
```

## Components

### BatchCompletionMonitor

The `BatchCompletionMonitor` is a background service that:

- Polls the database every 30 seconds for completed jobs
- Identifies jobs where `processed_files >= total_files` and `status = "processing"`
- Triggers the export process for each completed job
- Sends webhook notifications after export completes

**Key Features:**
- Automatic job completion detection
- Graceful error handling (continues processing other jobs if one fails)
- Configurable poll interval (default: 30 seconds)
- Singleton pattern to prevent multiple instances

**Usage:**

```python
from services.batch_completion_monitor import get_batch_completion_monitor

# Create database session factory
def create_session():
    return SessionLocal()

# Get monitor instance
monitor = get_batch_completion_monitor(create_session)

# Start monitoring (runs indefinitely)
await monitor.start()

# Stop monitoring (graceful shutdown)
await monitor.stop()
```

### WebhookNotificationService

The `WebhookNotificationService` handles sending HTTP POST notifications to configured webhook URLs.

**Key Features:**
- Automatic retry with exponential backoff (3 attempts: 2s, 4s, 8s delays)
- 30-second timeout per request
- Detailed logging of delivery status
- Test webhook functionality

**Webhook Payload:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "total_files": 25,
  "successful_files": 24,
  "failed_files": 1,
  "processed_files": 25,
  "progress_percentage": 100.0,
  "export_file_url": "https://s3.amazonaws.com/bucket/export.csv",
  "export_completed_at": "2025-11-08T10:45:00Z",
  "created_at": "2025-11-08T10:30:00Z",
  "completed_at": "2025-11-08T10:45:00Z",
  "tenant_id": 1,
  "document_types": ["invoice", "expense"],
  "export_destination_type": "s3",
  "webhook_sent_at": "2025-11-08T10:45:01Z"
}
```

**Usage:**

```python
from services.webhook_notification_service import WebhookNotificationService

webhook_service = WebhookNotificationService()

# Send notification for a completed job
result = await webhook_service.send_job_completion_notification(batch_job)

# Test a webhook URL
test_result = await webhook_service.test_webhook_url("https://example.com/webhook")
```

## Running the Monitor

### As a Standalone Worker

Use the provided worker script to run the monitor as a separate process:

```bash
python api/workers/batch_completion_worker.py
```

The worker handles:
- Graceful shutdown on SIGTERM/SIGINT
- Database connection management
- Error recovery

### As Part of Main Application

You can also integrate the monitor into your main application:

```python
import asyncio
from services.batch_completion_monitor import get_batch_completion_monitor

async def start_background_services():
    """Start background services."""
    monitor = get_batch_completion_monitor(db_session_factory)
    
    # Start monitor in background task
    asyncio.create_task(monitor.start())
```

### Using Docker/Kubernetes

For containerized deployments, run the worker as a separate container:

**Dockerfile:**
```dockerfile
FROM python:3.11

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "workers/batch_completion_worker.py"]
```

**docker-compose.yml:**
```yaml
services:
  batch-completion-worker:
    build: .
    command: python workers/batch_completion_worker.py
    environment:
      - DATABASE_URL=${DATABASE_URL}
    restart: unless-stopped
```

## Configuration

### Environment Variables

- `DATABASE_URL`: Database connection string
- `BATCH_COMPLETION_POLL_INTERVAL`: Poll interval in seconds (default: 30)

### Monitor Settings

The monitor can be configured by modifying the `BatchCompletionMonitor` class:

```python
class BatchCompletionMonitor:
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.poll_interval = 30  # Change this to adjust poll frequency
```

### Webhook Settings

Webhook retry behavior can be configured in `WebhookNotificationService`:

```python
class WebhookNotificationService:
    MAX_RETRIES = 3  # Number of retry attempts
    TIMEOUT_SECONDS = 30  # Request timeout
    RETRY_DELAYS = [2, 4, 8]  # Exponential backoff delays
```

## Monitoring and Logging

### Log Levels

The services use Python's logging module with the following levels:

- **INFO**: Normal operations (job completion, webhook delivery)
- **WARNING**: Retry attempts, non-critical errors
- **ERROR**: Failed operations, exceptions

### Example Logs

```
2025-11-08 10:45:00 - BatchCompletionMonitor - INFO - Found 3 completed jobs to export
2025-11-08 10:45:01 - ExportService - INFO - Export completed for job abc-123: status=completed
2025-11-08 10:45:02 - WebhookNotificationService - INFO - Webhook notification sent successfully for job abc-123 (attempt 1)
```

### Metrics to Monitor

- Number of jobs processed per minute
- Export success/failure rate
- Webhook delivery success rate
- Average time from job completion to export
- Number of retry attempts

## Error Handling

### Job Export Failures

If export fails:
1. Job status is set to "failed"
2. Error is logged with full stack trace
3. Webhook notification is still sent (with failed status)
4. Monitor continues processing other jobs

### Webhook Delivery Failures

If webhook delivery fails after all retries:
1. Failure is logged with error details
2. Job status remains "completed" (export succeeded)
3. Webhook delivery status is tracked separately

### Database Connection Issues

If database connection fails:
1. Error is logged
2. Monitor waits for next poll interval
3. Connection is retried on next poll

## Testing

### Test the Monitor

```bash
python api/scripts/test_batch_completion_monitor.py
```

This script tests:
- Webhook notification service
- Webhook payload building
- Monitor initialization
- Retry logic

### Test Webhook URL

```python
from services.webhook_notification_service import WebhookNotificationService

webhook_service = WebhookNotificationService()
result = await webhook_service.test_webhook_url("https://your-webhook-url.com")

print(f"Test result: {result['status']}")
```

## Security Considerations

### Webhook Security

1. **HTTPS Only**: Always use HTTPS webhook URLs in production
2. **Authentication**: Consider adding authentication headers to webhook requests
3. **Signature Verification**: Implement webhook signature verification on the receiving end
4. **Rate Limiting**: Implement rate limiting on webhook endpoints

### Database Access

1. **Connection Pooling**: Use connection pooling for production deployments
2. **Read-Only Access**: Monitor only needs read access to job tables
3. **Tenant Isolation**: All queries are filtered by tenant_id

## Troubleshooting

### Monitor Not Detecting Completed Jobs

**Symptoms:** Jobs remain in "processing" status even though all files are processed

**Solutions:**
1. Check that `processed_files` equals `total_files`
2. Verify job status is "processing" (not "pending" or "completed")
3. Check monitor logs for errors
4. Verify database connection

### Webhook Notifications Not Delivered

**Symptoms:** Jobs complete but webhook is not called

**Solutions:**
1. Verify `webhook_url` is set on the job
2. Check webhook service logs for errors
3. Test webhook URL manually
4. Verify network connectivity
5. Check for SSL certificate issues

### High CPU Usage

**Symptoms:** Monitor process consuming excessive CPU

**Solutions:**
1. Increase poll interval (reduce frequency)
2. Add database indexes on `status` and `processed_files` columns
3. Limit number of jobs processed per poll
4. Use database connection pooling

## Best Practices

1. **Run as Separate Process**: Run the monitor as a dedicated worker process
2. **Monitor Health**: Implement health checks for the monitor service
3. **Log Aggregation**: Use centralized logging (e.g., ELK stack)
4. **Alerting**: Set up alerts for high failure rates
5. **Graceful Shutdown**: Always use signal handlers for clean shutdown
6. **Database Indexes**: Ensure proper indexes on query columns
7. **Connection Pooling**: Use connection pooling for production
8. **Webhook Validation**: Validate webhook URLs before saving

## Future Enhancements

Potential improvements for the monitoring system:

1. **Configurable Poll Interval**: Make poll interval configurable per tenant
2. **Priority Queue**: Process high-priority jobs first
3. **Webhook Signatures**: Add HMAC signatures to webhook payloads
4. **Retry Strategies**: Support different retry strategies (linear, exponential, custom)
5. **Webhook Templates**: Allow custom webhook payload templates
6. **Metrics Dashboard**: Real-time dashboard for monitoring job processing
7. **Dead Letter Queue**: Move permanently failed jobs to DLQ
8. **Batch Notifications**: Group multiple job completions into single webhook

## Related Documentation

- [Batch Processing Service](./BATCH_PROCESSING_SERVICE.md)
- [Export Service Implementation](./EXPORT_SERVICE_IMPLEMENTATION.md)
- [Export Destinations API](./EXPORT_DESTINATIONS_API.md)
