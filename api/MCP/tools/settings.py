"""
Settings-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GetSettingsArgs(BaseModel):
    pass  # No arguments needed for getting settings


class ListDiscountRulesArgs(BaseModel):
    pass  # No arguments needed for listing discount rules


class CreateDiscountRuleArgs(BaseModel):
    name: str = Field(description="Name of the discount rule")
    discount_type: str = Field(description="Type of discount (percentage, fixed)")
    discount_value: float = Field(description="Discount value")
    min_amount: Optional[float] = Field(default=None, description="Minimum amount for discount to apply")
    max_discount: Optional[float] = Field(default=None, description="Maximum discount amount")
    priority: int = Field(default=1, description="Priority of the rule (higher number = higher priority)")
    is_active: bool = Field(default=True, description="Whether the rule is active")
    currency: Optional[str] = Field(default=None, description="Currency code for the rule")


class GetNotificationSettingsArgs(BaseModel):
    pass  # No arguments needed


class UpdateNotificationSettingsArgs(BaseModel):
    invoice_created: bool = Field(default=True, description="Notify when invoices are created")
    invoice_paid: bool = Field(default=True, description="Notify when invoices are paid")
    payment_received: bool = Field(default=True, description="Notify when payments are received")
    client_created: bool = Field(default=False, description="Notify when clients are created")
    overdue_invoice: bool = Field(default=True, description="Notify about overdue invoices")
    email_enabled: bool = Field(default=True, description="Enable email notifications")


class SettingsToolsMixin:
    # Settings
    async def get_settings(self) -> Dict[str, Any]:
        """Get tenant settings"""
        try:
            settings = await self.api_client.get_settings()

            return {
                "success": True,
                "data": settings
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get settings: {e}"}

    # Discount Rules
    async def list_discount_rules(self) -> Dict[str, Any]:
        """List all discount rules"""
        try:
            response = await self.api_client.list_discount_rules()

            # Extract items from paginated response
            discount_rules = self._extract_items_from_response(response, ["items", "data", "rules"])

            return {
                "success": True,
                "data": discount_rules,
                "count": len(discount_rules)
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to list discount rules: {e}"}

    async def create_discount_rule(self, name: str, discount_type: str, discount_value: float, min_amount: Optional[float] = None, max_discount: Optional[float] = None, priority: int = 1, is_active: bool = True, currency: Optional[str] = None) -> Dict[str, Any]:
        """Create a new discount rule"""
        try:
            rule_data = {
                "name": name,
                "discount_type": discount_type,
                "discount_value": discount_value,
                "priority": priority,
                "is_active": is_active
            }
            if min_amount is not None:
                rule_data["min_amount"] = min_amount
            if max_discount is not None:
                rule_data["max_discount"] = max_discount
            if currency:
                rule_data["currency"] = currency

            discount_rule = await self.api_client.create_discount_rule(rule_data)

            return {
                "success": True,
                "data": discount_rule,
                "message": "Discount rule created successfully"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create discount rule: {e}"}

    # Notification Tools
    async def get_notification_settings(self) -> Dict[str, Any]:
        """Get current user's notification settings"""
        try:
            settings = await self.api_client.get_notification_settings()
            return {
                "success": True,
                "data": settings,
                "message": "Notification settings retrieved"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get notification settings: {e}"}

    async def update_notification_settings(
        self,
        invoice_created: bool = True,
        invoice_paid: bool = True,
        payment_received: bool = True,
        client_created: bool = False,
        overdue_invoice: bool = True,
        email_enabled: bool = True
    ) -> Dict[str, Any]:
        """Update current user's notification settings"""
        try:
            settings_data = {
                "invoice_created": invoice_created,
                "invoice_paid": invoice_paid,
                "payment_received": payment_received,
                "client_created": client_created,
                "overdue_invoice": overdue_invoice,
                "email_enabled": email_enabled
            }

            settings = await self.api_client.update_notification_settings(settings_data)
            return {
                "success": True,
                "data": settings,
                "message": "Notification settings updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update notification settings: {e}"}
