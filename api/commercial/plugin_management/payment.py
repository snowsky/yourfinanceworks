from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
import stripe
import logging

from core.models.database import get_db, get_master_db
from core.models.models import Tenant, PluginUser, TenantPluginSettings, Settings
from core.routers.auth import get_current_user
from config import config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["plugin_payment"])

def get_tenant_payment_settings(db: Session, tenant_id: int):
    setting = db.query(Settings).filter(Settings.tenant_id == tenant_id, Settings.key == "payment_settings").first()
    if not setting or not setting.value:
        return None
    
    settings_val = setting.value
    stripe_cfg = settings_val.get("stripe", {})
    if not stripe_cfg.get("enabled"):
        return None
        
    return stripe_cfg

class CheckoutRequest(BaseModel):
    tenant_id: int
    plugin_user_id: int

@router.post("/{plugin_id}/public-paywall/checkout")
async def plugin_paywall_checkout(
    plugin_id: str,
    payload: CheckoutRequest,
    db: Session = Depends(get_master_db)
):
    plugin_user = db.query(PluginUser).filter(
        PluginUser.id == payload.plugin_user_id,
        PluginUser.tenant_id == payload.tenant_id,
        PluginUser.plugin_id == plugin_id
    ).first()
    
    if not plugin_user:
        raise HTTPException(status_code=404, detail="Plugin user not found")

    # Get Stripe credentials for the tenant
    stripe_cfg = get_tenant_payment_settings(db, payload.tenant_id)
    if not stripe_cfg or not stripe_cfg.get("secretKey"):
        raise HTTPException(status_code=400, detail="Payments are not configured by the organization")

    # Get the price_id from the plugin config
    plugin_settings = db.query(TenantPluginSettings).filter(TenantPluginSettings.tenant_id == payload.tenant_id).first()
    if not plugin_settings or plugin_id not in plugin_settings.enabled_plugins:
        raise HTTPException(status_code=403, detail="Plugin not available")
        
    cfg = plugin_settings.plugin_config or {}
    p_cfg = cfg.get(plugin_id, {})
    pa = p_cfg.get("public_access", {})
    
    if not pa.get("enabled"):
        raise HTTPException(status_code=403, detail="Plugin not public")
        
    stripe_price_id = pa.get("stripe_price_id")
    if not stripe_price_id:
        raise HTTPException(status_code=400, detail="A price has not been set for this plugin")

    stripe.api_key = stripe_cfg.get("secretKey")

    # Create or retrieve customer
    customer_id = plugin_user.stripe_customer_id
    if not customer_id:
        try:
            customer = stripe.Customer.create(
                email=plugin_user.email,
                metadata={"tenant_id": payload.tenant_id, "plugin_id": plugin_id, "plugin_user_id": plugin_user.id}
            )
            customer_id = customer.id
            plugin_user.stripe_customer_id = customer_id
            db.commit()
        except stripe.StripeError as e:
            logger.error(f"Stripe error creating customer: {e}")
            raise HTTPException(status_code=500, detail="Error communicating with Stripe")

    ui_base = config.UI_BASE_URL
    success_url = f"{ui_base}/p/{plugin_id}?payment=success"
    cancel_url = f"{ui_base}/p/{plugin_id}/paywall"

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription', # Assuming subscription for plugins based on common practices
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {"checkout_url": session.url}
    except stripe.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with Stripe")

@router.post("/{plugin_id}/public-paywall/status")
async def plugin_paywall_status(
    plugin_id: str,
    payload: CheckoutRequest,
    db: Session = Depends(get_master_db)
):
    plugin_user = db.query(PluginUser).filter(
        PluginUser.id == payload.plugin_user_id,
        PluginUser.tenant_id == payload.tenant_id,
        PluginUser.plugin_id == plugin_id
    ).first()

    if not plugin_user:
        raise HTTPException(status_code=404, detail="Plugin user not found")

    is_paid = False

    # Get Stripe credentials for the tenant
    stripe_cfg = get_tenant_payment_settings(db, payload.tenant_id)
    if stripe_cfg and stripe_cfg.get("secretKey") and plugin_user.stripe_customer_id:
        stripe.api_key = stripe_cfg["secretKey"]
        try:
            # Check for active subscriptions
            subs = stripe.Subscription.list(customer=plugin_user.stripe_customer_id, status='active')
            if subs and len(subs.data) > 0:
                is_paid = True
            else:
                # Also check for successful one-time payments if they use a one-time price
                # just in case the price was a one-time charge instead of subscription
                charges = stripe.Charge.list(customer=plugin_user.stripe_customer_id, limit=1)
                if charges and len(charges.data) > 0 and charges.data[0].paid:
                    is_paid = True
        except stripe.StripeError as e:
            logger.error(f"Stripe error checking customer status: {e}")
            
    return {"is_paid": is_paid}
