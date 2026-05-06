import asyncio
import sys
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[2] / "api"
sys.path.insert(0, str(API_DIR))

from MCP.tools import InvoiceTools


class PaginatedPaymentsClient:
    async def list_payments(self, skip=0, limit=100):
        return {
            "items": [
                {
                    "id": 1,
                    "amount": 125.5,
                    "payment_date": "2026-05-01T12:00:00",
                    "payment_method": "bank_transfer",
                },
                {
                    "id": 2,
                    "amount": 74.5,
                    "payment_date": "2026-05-02T12:00:00",
                    "payment_method": "cash",
                },
            ],
            "total": 2,
        }


def test_query_payments_accepts_paginated_response_envelope():
    tools = InvoiceTools(PaginatedPaymentsClient())

    result = asyncio.run(tools.query_payments("how much did I get paid?"))

    assert result["success"] is True
    assert result["count"] == 2
    assert sum(payment["amount"] for payment in result["data"]) == 200.0
