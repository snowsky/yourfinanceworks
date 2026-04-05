# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Any, Dict
from datetime import datetime, timedelta, timezone
import logging
import os

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.models.models_per_tenant import Invoice, Client
from core.utils.feature_gate import require_feature
from core.constants.recommendation_codes import (
    CONSIDER_STRICTER_PAYMENT_TERMS,
    REVIEW_PAYMENT_TERMS_SLOW_CLIENTS,
    START_CREATING_INVOICES,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

router = APIRouter()


@router.get("/analyze-patterns", summary="Analyze invoice patterns and trends")
@require_feature("ai_invoice")
async def analyze_patterns(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analyzes historical invoice data to identify patterns, trends,
    and key metrics such as total invoices, paid/unpaid status,
    revenue, and client payment behavior.
    """
    try:
        # Get all invoices (no tenant_id filtering needed since we're in the tenant's database)
        invoices = db.query(Invoice).all()

        # Calculate basic metrics
        total_invoices = len(invoices)
        paid_invoices = len([inv for inv in invoices if inv.status == "paid"])
        partially_paid_invoices = len([inv for inv in invoices if inv.status == "partially_paid"])
        unpaid_invoices = len([inv for inv in invoices if inv.status in ["pending", "draft"]])
        overdue_invoices = len([inv for inv in invoices if inv.status == "overdue"])

        # Calculate revenue metrics with better error handling - grouped by currency
        total_revenue_by_currency = {}
        outstanding_revenue_by_currency = {}

        for inv in invoices:
            currency = inv.currency or "USD"

            if inv.status == "paid":
                if currency not in total_revenue_by_currency:
                    total_revenue_by_currency[currency] = 0
                total_revenue_by_currency[currency] += inv.amount
            elif inv.status == "partially_paid":
                # Calculate paid amount from payments - avoid relationship to prevent user_id column issues
                try:
                    # Use direct query to avoid Payment model relationship issues
                    from sqlalchemy import text
                    result = db.execute(text("SELECT SUM(amount) as total FROM payments WHERE invoice_id = :invoice_id"),
                                     {"invoice_id": inv.id})
                    paid_amount = result.scalar() or 0
                except Exception as e:
                    print(f"Error calculating paid amount for invoice {inv.id}: {e}")
                    paid_amount = 0

                if currency not in total_revenue_by_currency:
                    total_revenue_by_currency[currency] = 0
                total_revenue_by_currency[currency] += paid_amount

            if inv.status in ["pending", "draft", "overdue"]:
                if currency not in outstanding_revenue_by_currency:
                    outstanding_revenue_by_currency[currency] = 0
                outstanding_revenue_by_currency[currency] += inv.amount

        # Get client payment patterns (simplified to avoid Payment model issues)
        # For now, we'll skip detailed payment analysis to avoid database schema conflicts
        fastest_paying_clients = []
        slowest_paying_clients = []

        # Generate recommendations
        recommendations = []
        if overdue_invoices > 0:
            recommendations.append(f"Send reminders for {overdue_invoices} overdue invoices")

        # Calculate total outstanding and total revenue across all currencies
        total_outstanding = sum(outstanding_revenue_by_currency.values())
        total_revenue = sum(total_revenue_by_currency.values())

        if total_outstanding > total_revenue * 0.3:
            recommendations.append(CONSIDER_STRICTER_PAYMENT_TERMS)
        if slowest_paying_clients:
            recommendations.append(REVIEW_PAYMENT_TERMS_SLOW_CLIENTS)
        if total_invoices == 0:
            recommendations.append(START_CREATING_INVOICES)

        # Debug logging
        print(f"Analyze patterns debug: total_invoices={total_invoices}, paid={paid_invoices}, partially_paid={partially_paid_invoices}, total_revenue_by_currency={total_revenue_by_currency}")

        return {
            "success": True,
            "data": {
                "total_invoices": total_invoices,
                "paid_invoices": paid_invoices,
                "partially_paid_invoices": partially_paid_invoices,
                "unpaid_invoices": unpaid_invoices,
                "overdue_invoices": overdue_invoices,
                "total_revenue_by_currency": total_revenue_by_currency,
                "outstanding_revenue_by_currency": outstanding_revenue_by_currency,
                "fastest_paying_clients": fastest_paying_clients,
                "slowest_paying_clients": slowest_paying_clients,
                "recommendations": recommendations
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/suggest-actions", summary="Suggest actionable items based on invoice analysis")
@require_feature("ai_invoice")
async def suggest_actions(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analyzes invoice data and suggests actionable items
    such as follow-up on overdue invoices, adjust payment terms, etc.
    """
    # Manually set tenant context and get tenant database
    try:
        # Get overdue invoices
        # No tenant_id filtering needed since we're in the tenant's database
        overdue_invoices = db.query(Invoice).filter(Invoice.status == "overdue").all()

        # Get clients with outstanding balances
        # No tenant_id filtering needed since we're in the tenant's database
        clients_with_balance = db.query(Client).filter(Client.balance > 0).all()

        # Get recent invoices that might need follow-up
        # No tenant_id filtering needed since we're in the tenant's database
        recent_invoices = db.query(Invoice).filter(
            and_(
                Invoice.status.in_(["pending", "draft"]),
                Invoice.due_date <= datetime.now(timezone.utc) + timedelta(days=7)
            )
        ).all()

        # Generate suggested actions
        suggested_actions = []

        if overdue_invoices:
            suggested_actions.append({
                "action": "send_overdue_reminders",
                "description": f"Send payment reminders for {len(overdue_invoices)} overdue invoices",
                "priority": "high"
            })

        if clients_with_balance:
            suggested_actions.append({
                "action": "review_payment_terms",
                "description": f"Review payment terms for {len(clients_with_balance)} clients with outstanding balances",
                "priority": "medium"
            })

        if recent_invoices:
            suggested_actions.append({
                "action": "follow_up_recent_invoices",
                "description": f"Follow up on {len(recent_invoices)} invoices due within 7 days",
                "priority": "medium"
            })

        # Check for low cash flow
        total_outstanding = sum(inv.amount for inv in overdue_invoices)
        if total_outstanding > 1000:  # Arbitrary threshold
            suggested_actions.append({
                "action": "implement_stricter_terms",
                "description": "Consider implementing stricter payment terms to improve cash flow",
                "priority": "low"
            })

        # If no specific actions, suggest general improvements
        if not suggested_actions:
            suggested_actions.append({
                "action": "review_business_processes",
                "description": "Review your invoicing and payment collection processes",
                "priority": "low"
            })

        return {
            "success": True,
            "data": {
                "suggested_actions": suggested_actions,
                "overdue_count": len(overdue_invoices),
                "clients_with_balance": len(clients_with_balance),
                "recent_invoices_count": len(recent_invoices)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
