"""
Minimal Report API Router

Basic API endpoints for report generation with minimal dependencies.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from models.database import get_db
from models.models import MasterUser
from routers.auth import get_current_user
from schemas.report import ReportTypesResponse, ReportType

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/types", response_model=ReportTypesResponse)
async def get_report_types(
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get available report types and their configuration options.
    
    Returns information about all supported report types including
    available filters, columns, and export formats.
    """
    try:
        report_types = [
            {
                "type": ReportType.CLIENT,
                "name": "Client Reports",
                "description": "Comprehensive client analysis with financial history",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "client_ids", "type": "list[int]", "required": False},
                    {"name": "include_inactive", "type": "boolean", "required": False},
                    {"name": "balance_min", "type": "float", "required": False},
                    {"name": "balance_max", "type": "float", "required": False}
                ],
                "columns": [
                    "client_name", "email", "phone", "total_invoiced", "total_paid",
                    "outstanding_balance", "last_invoice_date", "payment_terms"
                ]
            },
            {
                "type": ReportType.INVOICE,
                "name": "Invoice Reports", 
                "description": "Detailed invoice analysis with payment tracking",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "client_ids", "type": "list[int]", "required": False},
                    {"name": "status", "type": "list[str]", "required": False},
                    {"name": "amount_min", "type": "float", "required": False},
                    {"name": "amount_max", "type": "float", "required": False},
                    {"name": "include_items", "type": "boolean", "required": False}
                ],
                "columns": [
                    "invoice_number", "client_name", "date", "due_date", "amount",
                    "status", "paid_amount", "outstanding_amount", "currency"
                ]
            }
        ]
        
        return ReportTypesResponse(report_types=report_types)
        
    except Exception as e:
        logger.error(f"Failed to get report types: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report types"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for reports module"""
    return {"status": "ok", "module": "reports"}