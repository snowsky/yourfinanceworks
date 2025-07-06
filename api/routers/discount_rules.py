from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.models import DiscountRule
from schemas.discount_rule import DiscountRuleCreate, DiscountRuleUpdate, DiscountRuleResponse
from routers.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/discount-rules", tags=["discount-rules"])

@router.get("/", response_model=List[DiscountRuleResponse])
async def get_discount_rules(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all discount rules for the current tenant"""
    discount_rules = db.query(DiscountRule).filter(
        DiscountRule.tenant_id == current_user.tenant_id
    ).order_by(DiscountRule.priority.desc(), DiscountRule.min_amount.desc()).all()
    
    return discount_rules

@router.post("/", response_model=DiscountRuleResponse)
async def create_discount_rule(
    discount_rule: DiscountRuleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new discount rule"""
    db_discount_rule = DiscountRule(
        **discount_rule.dict(),
        tenant_id=current_user.tenant_id
    )
    db.add(db_discount_rule)
    db.commit()
    db.refresh(db_discount_rule)
    return db_discount_rule

@router.get("/{discount_rule_id}", response_model=DiscountRuleResponse)
async def get_discount_rule(
    discount_rule_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific discount rule"""
    discount_rule = db.query(DiscountRule).filter(
        DiscountRule.id == discount_rule_id,
        DiscountRule.tenant_id == current_user.tenant_id
    ).first()
    
    if not discount_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount rule not found"
        )
    
    return discount_rule

@router.put("/{discount_rule_id}", response_model=DiscountRuleResponse)
async def update_discount_rule(
    discount_rule_id: int,
    discount_rule_update: DiscountRuleUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a discount rule"""
    db_discount_rule = db.query(DiscountRule).filter(
        DiscountRule.id == discount_rule_id,
        DiscountRule.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_discount_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount rule not found"
        )
    
    update_data = discount_rule_update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(db_discount_rule, field, value)
    
    db.commit()
    db.refresh(db_discount_rule)
    return db_discount_rule

@router.delete("/{discount_rule_id}")
async def delete_discount_rule(
    discount_rule_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a discount rule"""
    db_discount_rule = db.query(DiscountRule).filter(
        DiscountRule.id == discount_rule_id,
        DiscountRule.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_discount_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount rule not found"
        )
    
    db.delete(db_discount_rule)
    db.commit()
    
    return {"message": "Discount rule deleted successfully"}

@router.post("/calculate")
async def calculate_discount(
    subtotal: float,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Calculate the applicable discount for a given subtotal"""
    # Get all active discount rules for the tenant, ordered by priority and min_amount
    discount_rules = db.query(DiscountRule).filter(
        DiscountRule.tenant_id == current_user.tenant_id,
        DiscountRule.is_active == True
    ).order_by(DiscountRule.priority.desc(), DiscountRule.min_amount.desc()).all()
    
    # Find the first applicable rule
    applicable_rule = None
    for rule in discount_rules:
        if subtotal >= rule.min_amount:
            applicable_rule = rule
            break
    
    if not applicable_rule:
        return {
            "discount_type": "none",
            "discount_value": 0,
            "discount_amount": 0,
            "applied_rule": None
        }
    
    # Calculate discount amount
    if applicable_rule.discount_type == "percentage":
        discount_amount = (subtotal * applicable_rule.discount_value) / 100
    else:  # fixed amount
        discount_amount = min(applicable_rule.discount_value, subtotal)
    
    return {
        "discount_type": applicable_rule.discount_type,
        "discount_value": applicable_rule.discount_value,
        "discount_amount": discount_amount,
        "applied_rule": {
            "id": applicable_rule.id,
            "name": applicable_rule.name,
            "min_amount": applicable_rule.min_amount
        }
    } 