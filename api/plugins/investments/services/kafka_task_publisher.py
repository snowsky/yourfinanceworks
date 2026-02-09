"""
Kafka Task Publisher for Holdings Import

This module provides utilities for publishing holdings import tasks to Kafka
for asynchronous processing by the holdings import worker.
"""

import json
import logging
import os
from typing import Optional

from confluent_kafka import Producer, KafkaError

logger = logging.getLogger(__name__)


class KafkaTaskPublisher:
    """Publisher for holdings import tasks to Kafka"""

    def __init__(self):
        """Initialize the Kafka producer"""
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.topic = os.getenv(
            "KAFKA_HOLDINGS_IMPORT_TOPIC", "holdings_import_tasks"
        )
        self.producer: Optional[Producer] = None

    def _get_producer(self) -> Producer:
        """Get or create Kafka producer"""
        if self.producer is None:
            producer_config = {
                'bootstrap.servers': self.bootstrap_servers,
                'client.id': 'holdings-import-publisher',
                'acks': 'all',
                'retries': 3,
            }
            self.producer = Producer(producer_config)

        return self.producer

    def publish_task(
        self,
        attachment_id: int,
        tenant_id: int,
        portfolio_id: int
    ) -> bool:
        """
        Publish a holdings import task to Kafka.

        Args:
            attachment_id: File attachment ID
            tenant_id: Tenant ID
            portfolio_id: Portfolio ID

        Returns:
            True if published successfully, False otherwise
        """
        try:
            producer = self._get_producer()

            payload = {
                "attachment_id": attachment_id,
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
            }

            message_json = json.dumps(payload)

            # Use attachment_id as the key for partitioning
            key = str(attachment_id).encode('utf-8')
            value = message_json.encode('utf-8')

            # Publish with callback
            producer.produce(
                self.topic,
                key=key,
                value=value,
                callback=self._delivery_report
            )

            # Flush to ensure message is sent
            producer.flush(timeout=10)

            logger.info(
                f"Published holdings import task: "
                f"attachment_id={attachment_id}, tenant_id={tenant_id}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to publish holdings import task: {e}",
                exc_info=True
            )
            return False

    def _delivery_report(self, err, msg):
        """Callback for message delivery"""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} "
                f"[{msg.partition()}] at offset {msg.offset()}"
            )

    def close(self):
        """Close the producer"""
        if self.producer:
            self.producer.flush()
            self.producer = None


# Global instance
_publisher: Optional[KafkaTaskPublisher] = None


def get_kafka_publisher() -> KafkaTaskPublisher:
    """Get or create the global Kafka task publisher"""
    global _publisher
    if _publisher is None:
        _publisher = KafkaTaskPublisher()
    return _publisher


def publish_holdings_import_task(
    attachment_id: int,
    tenant_id: int,
    portfolio_id: int
) -> bool:
    """
    Publish a holdings import task to Kafka.

    Args:
        attachment_id: File attachment ID
        tenant_id: Tenant ID
        portfolio_id: Portfolio ID

    Returns:
        True if published successfully, False otherwise
    """
    publisher = get_kafka_publisher()
    return publisher.publish_task(attachment_id, tenant_id, portfolio_id)
