from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from core.models.database import get_db
from core.schemas.discount_rule import DiscountRuleCreate, DiscountRuleUpdate, DiscountRuleResponse, DiscountCalculationRequest
from core.services.discount_rule_service import DiscountRuleService

router = APIRouter(prefix="/discount-rules", tags=["discount-rules"])

@router.get("/", response_model=List[DiscountRuleResponse])
async def get_discount_rules(
    db: Session = Depends(get_db)
):
    """Get all discount rules for the current tenant"""
    service = DiscountRuleService(db)
    return service.get_discount_rules()

@router.post("/", response_model=DiscountRuleResponse)
async def create_discount_rule(
    rule: DiscountRuleCreate,
    db: Session = Depends(get_db)
):
    """Create a new discount rule"""
    service = DiscountRuleService(db)
    return service.create_discount_rule(rule)

@router.get("/{discount_rule_id}", response_model=DiscountRuleResponse)
async def get_discount_rule(
    discount_rule_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific discount rule by ID"""
    service = DiscountRuleService(db)
    return service.get_discount_rule_by_id(discount_rule_id)

@router.put("/{discount_rule_id}", response_model=DiscountRuleResponse)
async def update_discount_rule(
    discount_rule_id: int,
    rule: DiscountRuleUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing discount rule"""
    service = DiscountRuleService(db)
    return service.update_discount_rule(discount_rule_id, rule)

@router.delete("/{discount_rule_id}")
async def delete_discount_rule(
    discount_rule_id: int,
    db: Session = Depends(get_db)
):
    """Delete a discount rule"""
    service = DiscountRuleService(db)
    return service.delete_discount_rule(discount_rule_id)

@router.post("/calculate")
async def calculate_discount(
    request: DiscountCalculationRequest,
    db: Session = Depends(get_db)
):
    """Calculate discount for a given subtotal"""
    service = DiscountRuleService(db)
    return service.calculate_discount(request) 