from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DiscountRuleBase(BaseModel):
    name: str = Field(..., description="Name of the discount rule")
    min_amount: float = Field(..., description="Minimum amount to trigger the rule")
    discount_type: str = Field(default="percentage", description="Type of discount: percentage or fixed")
    discount_value: float = Field(..., description="Discount value (percentage or fixed amount)")
    is_active: bool = Field(default=True, description="Whether the rule is active")
    priority: int = Field(default=0, description="Priority of the rule (higher = applied first)")

class DiscountRuleCreate(DiscountRuleBase):
    pass

class DiscountRuleUpdate(BaseModel):
    name: Optional[str] = None
    min_amount: Optional[float] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None

class DiscountRule(DiscountRuleBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DiscountRuleResponse(BaseModel):
    id: int
    name: str
    min_amount: float
    discount_type: str
    discount_value: float
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 