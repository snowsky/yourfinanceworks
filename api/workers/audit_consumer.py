"""
Audit Consumer for asynchronous anomaly detection and fraud prevention.
Processes forensic audit tasks from Kafka and runs the AnomalyDetectionService.
"""

import json
import logging
import os
import signal
import sys
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from commercial.anomaly_detection.service import AnomalyDetectionService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit_worker")


@dataclass
class AuditConfig:
    """Configuration for Audit processing"""

    kafka_bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    kafka_topic: str = os.getenv("KAFKA_FRAUD_AUDIT_TOPIC", "fraud_audit")
    kafka_group: str = os.getenv("KAFKA_AUDIT_GROUP", "invoice-app-audit")
    max_attempts: int = 3


class AuditConsumer:
    def __init__(self, config: AuditConfig):
        self.config = config
        self.running = True
        self.consumer = None
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def _ensure_topic_exists(self):
        """Ensure the fraud_audit topic exists"""
        try:
            from confluent_kafka.admin import AdminClient, NewTopic

            admin = AdminClient({"bootstrap.servers": self.config.kafka_bootstrap_servers})

            # Check if topic already exists
            md = admin.list_topics(timeout=5)
            if self.config.kafka_topic in md.topics and not md.topics[self.config.kafka_topic].error:
                logger.debug(f"Kafka topic '{self.config.kafka_topic}' already exists")
                return

            # Create topic
            partitions = 1
            replication_factor = 1
            new_topic = NewTopic(topic=self.config.kafka_topic, num_partitions=partitions, replication_factor=replication_factor)

            fs = admin.create_topics([new_topic])
            fut = fs.get(self.config.kafka_topic)

            try:
                fut.result(timeout=10)
                logger.info(f"Created Kafka topic '{self.config.kafka_topic}' (partitions={partitions}, rf={replication_factor})")
            except Exception as e:
                logger.warning(f"Topic creation for '{self.config.kafka_topic}' may have failed or already exists: {e}")

        except Exception as e:
            logger.warning(f"Unable to ensure Kafka topic '{self.config.kafka_topic}': {e}")

    async def start(self):
        """Initialize and start the Kafka consumer loop"""
        try:
            from confluent_kafka import Consumer, KafkaError
        except ImportError:
            logger.error("confluent-kafka not installed. Audit worker cannot start.")
            return 1

        # Ensure topic exists
        await self._ensure_topic_exists()

        conf = {
            "bootstrap.servers": self.config.kafka_bootstrap_servers,
            "group.id": self.config.kafka_group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }

        self.consumer = Consumer(conf)
        self.consumer.subscribe([self.config.kafka_topic])

        logger.info(f"Audit Worker started. Subscribed to {self.config.kafka_topic}")

        try:
            while self.running:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        break

                await self._process_message(msg)

        finally:
            self._cleanup()

        return 0

    async def _process_message(self, message):
        """Process a single audit task message"""
        try:
            payload = json.loads(message.value().decode("utf-8"))
            tenant_id = payload.get("tenant_id")
            entity_type = payload.get("entity_type")
            entity_id = payload.get("entity_id")
            reprocess_mode = payload.get("reprocess_mode", False)  # Default to False for normal audit

            if not all([tenant_id, entity_type, entity_id]):
                logger.error(f"Invalid audit message payload: {payload}")
                self.consumer.commit(message=message, asynchronous=False)
                return

            logger.info(
                f"Processing audit for {entity_type} {entity_id} in tenant {tenant_id} (reprocess_mode: {reprocess_mode})"
            )

            # Setup database session for tenant
            set_tenant_context(tenant_id)
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
            try:
                # Resolve entity from DB
                from core.models.models_per_tenant import (
                    Expense,
                    BankStatementTransaction,
                    Invoice,
                )

                entity = None
                if entity_type == "expense":
                    entity = tenant_session.query(Expense).get(entity_id)
                elif entity_type == "bank_statement_transaction":
                    entity = tenant_session.query(BankStatementTransaction).get(
                        entity_id
                    )
                elif entity_type == "invoice":
                    entity = tenant_session.query(Invoice).get(entity_id)

                if not entity:
                    logger.warning(
                        f"Entity {entity_type} {entity_id} not found in tenant {tenant_id}"
                    )
                else:
                    # Run Anomaly Detection
                    service = AnomalyDetectionService(tenant_session)
                    await service.analyze_entity(entity, entity_type, reprocess_mode=reprocess_mode)
                    logger.info(f"Completed audit for {entity_type} {entity_id}")
            finally:
                tenant_session.close()

            self.consumer.commit(message=message, asynchronous=False)

        except Exception as e:
            logger.error(f"Error processing audit message: {e}", exc_info=True)
            # In production, we might want to retry or move to DLQ

    def _cleanup(self):
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")


async def main_async():
    config = AuditConfig()
    consumer = AuditConsumer(config)
    return await consumer.start()


def main():
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logger.error(f"Audit Worker failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
