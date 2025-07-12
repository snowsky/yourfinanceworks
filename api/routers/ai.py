from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Any, Dict, List
from datetime import datetime, timedelta, timezone

from models.database import get_db
from routers.auth import get_current_user
from models.models import User, Invoice, Client, Payment, Tenant, AIConfig

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/analyze-patterns", summary="Analyze invoice patterns and trends")
async def analyze_patterns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyzes historical invoice data to identify patterns, trends,
    and key metrics such as total invoices, paid/unpaid status,
    revenue, and client payment behavior.
    """
    try:
        # Get all invoices for the current tenant
        invoices = db.query(Invoice).filter(Invoice.tenant_id == current_user.tenant_id).all()
        
        # Calculate basic metrics
        total_invoices = len(invoices)
        paid_invoices = len([inv for inv in invoices if inv.status == "paid"])
        unpaid_invoices = len([inv for inv in invoices if inv.status in ["pending", "draft"]])
        overdue_invoices = len([inv for inv in invoices if inv.status == "overdue"])
        
        # Calculate revenue metrics
        total_revenue = sum(inv.amount for inv in invoices if inv.status == "paid")
        outstanding_revenue = sum(inv.amount for inv in invoices if inv.status in ["pending", "draft", "overdue"])
        
        # Get client payment patterns (explicit join)
        from sqlalchemy.orm import aliased
        InvoiceAlias = aliased(Invoice)
        PaymentAlias = aliased(Payment)
        client_payments = (
            db.query(
                Client.name,
                func.avg(PaymentAlias.payment_date - InvoiceAlias.due_date).label('avg_payment_delay')
            )
            .join(InvoiceAlias, InvoiceAlias.client_id == Client.id)
            .join(PaymentAlias, PaymentAlias.invoice_id == InvoiceAlias.id)
            .filter(
                Client.tenant_id == current_user.tenant_id,
                InvoiceAlias.tenant_id == current_user.tenant_id,
                PaymentAlias.tenant_id == current_user.tenant_id
            )
            .group_by(Client.name)
            .all()
        )
        
        # Sort clients by payment speed
        fastest_paying_clients = sorted(client_payments, key=lambda x: x[1] or timedelta(days=999))[:3]
        slowest_paying_clients = sorted(client_payments, key=lambda x: x[1] or timedelta(days=0), reverse=True)[:3]
        
        # Generate recommendations
        recommendations = []
        if overdue_invoices > 0:
            recommendations.append(f"Send reminders for {overdue_invoices} overdue invoices")
        if outstanding_revenue > total_revenue * 0.3:
            recommendations.append("Consider implementing stricter payment terms")
        if slowest_paying_clients:
            recommendations.append("Review payment terms for slow-paying clients")
        if total_invoices == 0:
            recommendations.append("Start creating invoices to track your business")
        
        return {
            "success": True,
            "data": {
                "total_invoices": total_invoices,
                "paid_invoices": paid_invoices,
                "unpaid_invoices": unpaid_invoices,
                "overdue_invoices": overdue_invoices,
                "total_revenue": total_revenue,
                "outstanding_revenue": outstanding_revenue,
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
async def suggest_actions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Provides actionable recommendations and suggestions based on the
    analysis of invoice patterns, such as sending reminders for overdue
    invoices or reviewing payment terms for slow-paying clients.
    """
    try:
        # Get overdue invoices
        overdue_invoices = db.query(Invoice).filter(
            and_(
                Invoice.tenant_id == current_user.tenant_id,
                Invoice.status == "overdue"
            )
        ).all()
        
        # Get clients with outstanding balances
        clients_with_balance = db.query(Client).filter(
            and_(
                Client.tenant_id == current_user.tenant_id,
                Client.balance > 0
            )
        ).all()
        
        # Get recent invoices that might need follow-up
        recent_invoices = db.query(Invoice).filter(
            and_(
                Invoice.tenant_id == current_user.tenant_id,
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

@router.post("/chat")
def chat_with_ai(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with AI using configured provider"""
    try:
        message = request.get("message", "")
        config_id = request.get("config_id")
        
        if not message:
            return {
                "success": False,
                "error": "Message is required"
            }
        
        # Get AI configuration
        if config_id:
            ai_config = db.query(AIConfig).filter(
                AIConfig.id == config_id,
                AIConfig.tenant_id == current_user.tenant_id,
                AIConfig.is_active == True
            ).first()
        else:
            # Get default active configuration
            ai_config = db.query(AIConfig).filter(
                AIConfig.tenant_id == current_user.tenant_id,
                AIConfig.is_default == True,
                AIConfig.is_active == True
            ).first()
        
        if not ai_config:
            return {
                "success": False,
                "error": "No active AI configuration found. Please configure an AI provider in Settings."
            }
        
        # Import litellm here to avoid circular imports
        try:
            from litellm import completion
        except ImportError:
            return {
                "success": False,
                "error": "LiteLLM not installed. Please install it with: pip install litellm"
            }
        
        # Format model name based on provider for LiteLLM
        model_name = ai_config.model_name
        
        if ai_config.provider_name == "ollama":
            # For Ollama, prefix with ollama/
            model_name = f"ollama/{ai_config.model_name}"
        elif ai_config.provider_name == "openai":
            # For OpenAI, use as-is (LiteLLM recognizes OpenAI models)
            model_name = ai_config.model_name
        elif ai_config.provider_name == "anthropic":
            # For Anthropic, use as-is (LiteLLM recognizes Anthropic models)
            model_name = ai_config.model_name
        elif ai_config.provider_name == "google":
            # For Google, use as-is (LiteLLM recognizes Google models)
            model_name = ai_config.model_name
        elif ai_config.provider_name == "custom":
            # For custom providers, use the model name as-is
            model_name = ai_config.model_name
        
        # Prepare the completion call
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 500
        }
        
        # Add provider-specific configuration
        if ai_config.provider_name == "openai":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
            if ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
        elif ai_config.provider_name == "ollama":
            if ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
        elif ai_config.provider_name == "anthropic":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
        elif ai_config.provider_name == "google":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
        elif ai_config.provider_name == "custom":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
            if ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
        
        # Make the completion call
        response = completion(**kwargs)
        
        ai_response = response.choices[0].message.content if response.choices else "I'm sorry, I couldn't generate a response."
        
        return {
            "success": True,
            "data": {
                "response": ai_response,
                "provider": ai_config.provider_name,
                "model": ai_config.model_name
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get AI response: {str(e)}"
        }
