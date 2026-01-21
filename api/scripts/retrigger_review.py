#!/usr/bin/env python3
import os
import sys
import json
import argparse
from typing import Dict, Any

# Add the api directory to the path so we can import models if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from confluent_kafka import Producer
except ImportError:
    print("Error: confluent-kafka not installed. Please install it with 'pip install confluent-kafka'")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Retrigger a document review with an optional model override.")
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID")
    parser.add_argument("--type", choices=["invoice", "expense", "bank_statement"], required=True, help="Entity type")
    parser.add_argument("--id", type=int, required=True, help="Entity ID")
    parser.add_argument("--model", type=str, help="Model name override (e.g., 'gpt-4o', 'llava', 'llama3.2-vision')")
    parser.add_argument("--prompt", type=str, help="Prompt text override (or path to a file containing the prompt)")
    parser.add_argument("--bootstrap", type=str, default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"), help="Kafka bootstrap servers")
    parser.add_argument("--topic", type=str, default=os.getenv("KAFKA_REVIEW_TOPIC", "review_trigger"), help="Kafka topic for review triggers")

    args = parser.parse_args()

    # Handle prompt from file if it looks like a path
    prompt_content = args.prompt
    if prompt_content and os.path.exists(prompt_content):
        with open(prompt_content, 'r') as f:
            prompt_content = f.read()

    conf = {
        "bootstrap.servers": args.bootstrap,
        "client.id": "review-retrigger-script"
    }

    producer = Producer(conf)

    message = {
        "tenant_id": args.tenant_id,
        "entity_type": args.type,
        "entity_id": args.id,
    }

    if args.model:
        message["model_override"] = args.model
    if prompt_content:
        message["prompt_override"] = prompt_content

    def delivery_report(err, msg):
        if err is not None:
            print(f"Message delivery failed: {err}")
        else:
            print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    print(f"Publishing retrigger message to topic '{args.topic}':")
    print(json.dumps(message, indent=2))

    producer.produce(
        args.topic,
        key=str(args.id),
        value=json.dumps(message),
        callback=delivery_report
    )

    producer.flush()
    print("Done.")

if __name__ == "__main__":
    main()
