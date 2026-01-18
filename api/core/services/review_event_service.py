import logging
import os
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ReviewEventService:
    """Service for publishing review trigger events to Kafka"""
    
    def __init__(self):
        self.topic = os.getenv("KAFKA_REVIEW_TOPIC", "review_trigger")
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self._producer = None
    
    def _get_producer(self):
        """Lazy initialization of Kafka producer"""
        if self._producer is None:
            try:
                from confluent_kafka import Producer
                
                config = {
                    'bootstrap.servers': self.bootstrap_servers,
                    'acks': '1',
                    'retries': 3,
                }
                
                self._producer = Producer(config)
                logger.info(f"Kafka producer initialized for review events (topic: {self.topic})")
            except Exception as e:
                logger.warning(f"Failed to initialize Kafka producer for review events: {e}")
                self._producer = None
        return self._producer
    
    def _delivery_report(self, err, msg):
        """Callback for Kafka message delivery"""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to topic {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

    def publish_full_review_trigger(self, tenant_id: int) -> bool:
        """
        Publish event to trigger full system review for a tenant.
        
        Args:
            tenant_id: Tenant ID to trigger review for
            
        Returns:
            True if event published successfully, False otherwise
        """
        try:
            producer = self._get_producer()
            if not producer:
                logger.warning("Kafka producer not available, review will rely on polling")
                return False
            
            event = {
                "tenant_id": tenant_id,
                "trigger_type": "full_system",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Produce message
            producer.produce(
                self.topic,
                value=json.dumps(event).encode('utf-8'),
                callback=lambda err, msg: logger.error(f"Kafka produce error: {err}") if err else None
            )
            producer.flush(timeout=5)
            
            logger.info(f"Published full review trigger event for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish full review trigger event: {e}")
            return False
    
    def publish_single_review_trigger(
        self, 
        tenant_id: int, 
        entity_type: str, 
        entity_id: int
    ) -> bool:
        """
        Publish event to trigger review for a single entity.
        
        Args:
            tenant_id: Tenant ID
            entity_type: Type of entity ('invoice', 'expense', 'statement')
            entity_id: ID of the entity to review
            
        Returns:
            True if event published successfully, False otherwise
        """
        try:
            producer = self._get_producer()
            if not producer:
                logger.warning("Kafka producer not available, review will rely on polling")
                return False
            
            event = {
                "tenant_id": tenant_id,
                "trigger_type": "single",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            producer.produce(
                self.topic,
                value=json.dumps(event).encode('utf-8'),
                callback=lambda err, msg: logger.error(f"Kafka produce error: {err}") if err else None
            )
            producer.flush(timeout=5)
            
            logger.info(f"Published single review trigger for {entity_type} {entity_id} (tenant {tenant_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish single review trigger event: {e}")
            return False
    
    def close(self):
        """Close the Kafka producer"""
        if self._producer:
            try:
                self._producer.close()
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")


# Singleton instance
_review_event_service: Optional[ReviewEventService] = None


def get_review_event_service() -> ReviewEventService:
    """Get or create the singleton ReviewEventService instance"""
    global _review_event_service
    if _review_event_service is None:
        _review_event_service = ReviewEventService()
    return _review_event_service
