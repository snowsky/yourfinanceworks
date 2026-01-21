### OCR Kafka topics, creation, and reliability practices

This document summarizes how OCR messages are produced/consumed, how topics are created, and recommended configs.

### Topics

- **Input topic (tasks)**: `expenses_ocr`
  - Carries OCR tasks with payload: `{ tenant_id, expense_id, attachment_id, file_path, attempt, ts }`
  - Produced by API when a receipt is uploaded or requeued
  - Consumed by OCR worker

- **Result topic (compacted)**: `expenses_ocr_result` (env: `KAFKA_OCR_RESULT_TOPIC`)
  - Emits final status events keyed by `expense_id`
  - Recommended to enable log compaction (cleanup.policy=compact)

- **DLQ topic**: `expenses_ocr_dlq` (env: `KAFKA_OCR_DLQ_TOPIC`)
  - Receives messages that failed after `KAFKA_OCR_MAX_ATTEMPTS`
  - Used for ops inspection and replay

### Environment variables

- `KAFKA_BOOTSTRAP_SERVERS` (e.g., `kafka:9092`)
- `KAFKA_OCR_TOPIC` (default `expenses_ocr`)
- `KAFKA_OCR_RESULT_TOPIC` (default `expenses_ocr_result`)
- `KAFKA_OCR_DLQ_TOPIC` (default `expenses_ocr_dlq`)
- `KAFKA_OCR_MAX_ATTEMPTS` (default `5`)
- `KAFKA_OCR_TOPIC_PARTITIONS` (default `1`) – only used by worker auto-create for input topic
- `KAFKA_OCR_TOPIC_RF` (default `1`) – only used by worker auto-create for input topic

### Topic creation

- The broker in `docker-compose.yml` has `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true` so producing to a non-existent topic will auto-create it with defaults.
- The OCR worker explicitly ensures the input topic (`expenses_ocr`) using the Kafka AdminClient.
- The result (`expenses_ocr_result`) and DLQ (`expenses_ocr_dlq`) topics are NOT explicitly ensured by the worker today.

Recommended: Pre-create result and DLQ topics with desired policies instead of relying on auto-create defaults.

#### Create topics with the broker CLI

```bash
docker compose exec -T kafka \
  kafka-topics --bootstrap-server kafka:9092 \
  --create --topic expenses_ocr_result --partitions 1 --replication-factor 1 \
  --config cleanup.policy=compact

docker compose exec -T kafka \
  kafka-topics --bootstrap-server kafka:9092 \
  --create --topic expenses_ocr_dlq --partitions 1 --replication-factor 1

# Optional: tweak compaction aggressiveness for the result topic
docker compose exec -T kafka \
  kafka-configs --bootstrap-server kafka:9092 --alter --topic expenses_ocr_result \
  --add-config min.cleanable.dirty.ratio=0.01,segment.ms=600000
```

#### Alternatively: ensure topics in code

- The worker already ensures `expenses_ocr` on startup via the Kafka AdminClient.
- If desired, extend the same ensure logic to `KAFKA_OCR_RESULT_TOPIC` and `KAFKA_OCR_DLQ_TOPIC` (and set `cleanup.policy=compact` for the result topic).

### Processing semantics

- The worker commits the consumer offset only when processing succeeds (`analysis_status == done`).
- On failure, the worker applies exponential backoff and retries by re-publishing with an incremented `attempt` header/value.
- After `KAFKA_OCR_MAX_ATTEMPTS`, the message is sent to the DLQ and the original message is committed to avoid tight loops.

### Idempotency and side effects

- Processing is designed to be idempotent:
  - Only sets fields if they are missing or in a default state where possible
  - Checks `analysis_status` transitions before committing

### Completion signal

- When processing completes, a compacted result event is published to `KAFKA_OCR_RESULT_TOPIC`, keyed by `expense_id`.
- Consumers can use this topic to listen for final statuses without scanning the main task topic.

### Startup requeue scan

- On worker startup, the worker scans each tenant DB for expenses with `analysis_status='queued'` and re-publishes a task for the most recent attachment.
- This helps recover from missed publishes or broker restarts without manual intervention.
