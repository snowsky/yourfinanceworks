"""Analytics endpoints: expense summary, trends, and category breakdowns."""

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Expense
from core.routers.auth import get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analytics/summary")
async def get_expense_summary(
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    compare_with_previous: bool = True,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get expense summary statistics with period comparisons"""

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        base_query = db.query(Expense).filter(
            Expense.status != 'pending_approval',
            Expense.is_deleted == False
        )

        end_dt = datetime.now(timezone.utc)
        start_dt = None

        if start_date and end_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        else:
            if period == "day":
                start_dt = end_dt - timedelta(days=1)
            elif period == "week":
                start_dt = end_dt - timedelta(weeks=1)
            elif period == "month":
                start_dt = end_dt - timedelta(days=30)
            elif period == "quarter":
                start_dt = end_dt - timedelta(days=90)
            elif period == "year":
                start_dt = end_dt - timedelta(days=365)
            else:
                start_dt = end_dt - timedelta(days=30)

        current_expenses = base_query.filter(
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt
        ).all()

        current_total = sum(float(e.total_amount or e.amount or 0) for e in current_expenses)
        current_count = len(current_expenses)

        period_length = end_dt - start_dt
        previous_start = start_dt - period_length
        previous_end = start_dt

        previous_expenses = base_query.filter(
            Expense.expense_date >= previous_start,
            Expense.expense_date <= previous_end
        ).all()

        previous_total = sum(float(e.total_amount or e.amount or 0) for e in previous_expenses)
        previous_count = len(previous_expenses)

        total_change = None
        count_change = None
        if previous_total > 0:
            total_change = ((current_total - previous_total) / previous_total) * 100
        if previous_count > 0:
            count_change = ((current_count - previous_count) / previous_count) * 100

        category_totals = {}
        for expense in current_expenses:
            category = expense.category or "Uncategorized"
            amount = float(expense.total_amount or expense.amount or 0)
            category_totals[category] = category_totals.get(category, 0) + amount

        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

        daily_totals = defaultdict(float)
        for expense in current_expenses:
            date_key = expense.expense_date.date().isoformat()
            daily_totals[date_key] += float(expense.total_amount or expense.amount or 0)

        sorted_daily_totals = sorted(daily_totals.items())

        return {
            "period": {
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "period_type": period
            },
            "current_period": {
                "total_amount": current_total,
                "total_count": current_count,
                "average_amount": current_total / current_count if current_count > 0 else 0
            },
            "previous_period": {
                "total_amount": previous_total,
                "total_count": previous_count,
                "average_amount": previous_total / previous_count if previous_count > 0 else 0
            } if compare_with_previous else None,
            "changes": {
                "total_amount_change_percent": round(total_change, 2) if total_change is not None else None,
                "count_change_percent": round(count_change, 2) if count_change is not None else None
            } if compare_with_previous else None,
            "category_breakdown": [{"category": cat, "amount": amt, "percentage": round((amt / current_total) * 100, 1) if current_total > 0 else 0} for cat, amt in sorted_categories],
            "daily_totals": [{"date": date, "amount": amount} for date, amount in sorted_daily_totals]
        }

    except Exception as e:
        logger.error(f"Failed to get expense summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expense summary")


@router.get("/analytics/trends")
async def get_expense_trends(
    days: int = 90,
    group_by: str = "week",
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get expense trends over a time period"""

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    try:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        expenses = db.query(Expense).filter(
            Expense.status != 'pending_approval',
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
            Expense.is_deleted == False
        ).all()

        trend_data = defaultdict(float)
        trend_counts = defaultdict(int)

        for expense in expenses:
            amount = float(expense.total_amount or expense.amount or 0)

            if group_by == "day":
                key = expense.expense_date.date().isoformat()
            elif group_by == "week":
                week_start = expense.expense_date.date() - timedelta(days=expense.expense_date.weekday())
                key = week_start.isoformat()
            elif group_by == "month":
                key = f"{expense.expense_date.year}-{expense.expense_date.month:02d}"
            else:
                key = expense.expense_date.date().isoformat()

            trend_data[key] += amount
            trend_counts[key] += 1

        sorted_trends = []
        for key in sorted(trend_data.keys()):
            sorted_trends.append({
                "period": key,
                "total_amount": trend_data[key],
                "count": trend_counts[key],
                "average_amount": trend_data[key] / trend_counts[key] if trend_counts[key] > 0 else 0
            })

        if len(sorted_trends) >= 2:
            x = list(range(len(sorted_trends)))
            y = [item["total_amount"] for item in sorted_trends]

            if len(x) >= 2:
                n = len(x)
                sum_x = sum(x)
                sum_y = sum(y)
                sum_xy = sum(xi * yi for xi, yi in zip(x, y))
                sum_xx = sum(xi * xi for xi in x)

                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
                trend_direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"

                mean_y = sum_y / n
                variance = sum((yi - mean_y) ** 2 for yi in y) / n
                std_dev = math.sqrt(variance)
                volatility = (std_dev / mean_y * 100) if mean_y > 0 else 0
            else:
                trend_direction = "stable"
                volatility = 0
        else:
            trend_direction = "insufficient_data"
            volatility = 0

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
                "group_by": group_by
            },
            "trends": sorted_trends,
            "analysis": {
                "trend_direction": trend_direction,
                "volatility_percent": round(volatility, 2),
                "total_periods": len(sorted_trends),
                "total_amount": sum(trend_data.values()),
                "average_period_amount": sum(trend_data.values()) / len(trend_data) if trend_data else 0
            }
        }

    except Exception as e:
        logger.error(f"Failed to get expense trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expense trends")


@router.get("/analytics/categories")
async def get_expense_categories_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get expense analytics by category"""

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    try:
        base_query = db.query(Expense).filter(
            Expense.status != 'pending_approval',
            Expense.is_deleted == False
        )

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                base_query = base_query.filter(Expense.expense_date >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                base_query = base_query.filter(Expense.expense_date <= end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format")

        if category_filter and category_filter != "all":
            base_query = base_query.filter(Expense.category == category_filter)

        expenses = base_query.all()

        category_stats = defaultdict(lambda: {
            "total_amount": 0,
            "count": 0,
            "expenses": []
        })

        grand_total = 0
        for expense in expenses:
            category = expense.category or "Uncategorized"
            amount = float(expense.total_amount or expense.amount or 0)
            grand_total += amount

            category_stats[category]["total_amount"] += amount
            category_stats[category]["count"] += 1
            category_stats[category]["expenses"].append({
                "id": expense.id,
                "amount": amount,
                "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
                "vendor": expense.vendor,
                "notes": expense.notes
            })

        sorted_categories = sorted(
            category_stats.items(),
            key=lambda x: x[1]["total_amount"],
            reverse=True
        )

        category_analytics = []
        for category, stats in sorted_categories:
            percentage = (stats["total_amount"] / grand_total * 100) if grand_total > 0 else 0
            category_analytics.append({
                "category": category,
                "total_amount": stats["total_amount"],
                "percentage": round(percentage, 1),
                "count": stats["count"],
                "average_amount": stats["total_amount"] / stats["count"] if stats["count"] > 0 else 0,
                "expenses": stats["expenses"][:10]
            })

        return {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "grand_total": grand_total,
            "categories": category_analytics,
            "total_categories": len(category_analytics)
        }

    except Exception as e:
        logger.error(f"Failed to get expense categories analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expense categories analytics")
