#!/bin/bash

# Scale OCR workers and Kafka partitions
# Usage: ./scale-kafka-partitions.sh <worker_count>

if [ $# -eq 0 ]; then
    echo "Usage: $0 <worker_count>"
    echo "Example: $0 4"
    exit 1
fi

WORKERS=$1
KAFKA_CONTAINER="invoice_app_kafka"

echo "Scaling OCR workers to $WORKERS instances..."

# Scale OCR workers using docker-compose
docker-compose up --scale ocr-worker=$WORKERS -d

echo "Scaling OCR topics to $WORKERS partitions..."

# Scale expenses_ocr topic
docker exec $KAFKA_CONTAINER kafka-topics --bootstrap-server localhost:9092 --alter --topic expenses_ocr --partitions $WORKERS

# Scale bank_statements_ocr topic  
docker exec $KAFKA_CONTAINER kafka-topics --bootstrap-server localhost:9092 --alter --topic bank_statements_ocr --partitions $WORKERS

# Scale invoices_ocr topic
docker exec $KAFKA_CONTAINER kafka-topics --bootstrap-server localhost:9092 --alter --topic invoices_ocr --partitions $WORKERS

echo "Scaling complete!"
echo "Workers: $WORKERS"
echo "Partitions: $WORKERS"
echo ""
echo "Verify workers:"
echo "docker ps --filter 'name=ocr-worker'"
echo ""
echo "Verify partitions:"
echo "docker exec $KAFKA_CONTAINER kafka-topics --bootstrap-server localhost:9092 --describe --topic expenses_ocr"
echo ""
echo "Check consumer group distribution:"
echo "docker exec $KAFKA_CONTAINER kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group invoice-app-ocr-shared"