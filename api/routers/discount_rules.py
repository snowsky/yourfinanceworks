from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.models_per_tenant import DiscountRule, User
from schemas.discount_rule import DiscountRuleCreate, DiscountRuleUpdate, DiscountRuleResponse, DiscountCalculationRequest
from routers.auth import get_current_user
from datetime import datetime, timezone

router = APIRouter(prefix="/discount-rules", tags=["discount-rules"])

@router.get("/", response_model=List[DiscountRuleResponse])
async def get_discount_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all discount rules for the current tenant"""
    # No tenant_id filtering needed since we're in the tenant's database
    discount_rules = db.query(DiscountRule).order_by(DiscountRule.priority.desc(), DiscountRule.min_amount.desc()).all()
    
    return discount_rules

@router.post("/", response_model=DiscountRuleResponse)
async def create_discount_rule(
    rule: DiscountRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new discount rule"""
    # No tenant_id needed since each tenant has its own database
    db_discount_rule = DiscountRule(
        name=rule.name,
        min_amount=rule.min_amount,
        discount_type=rule.discount_type,
        discount_value=rule.discount_value,
        currency=rule.currency,
        is_active=rule.is_active,
        priority=rule.priority,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.add(db_discount_rule)
    db.commit()
    db.refresh(db_discount_rule)
    
    return db_discount_rule

@router.get("/{discount_rule_id}", response_model=DiscountRuleResponse)
async def get_discount_rule(
    discount_rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific discount rule by ID"""
    # No tenant_id filtering needed since we're in the tenant's database
    discount_rule = db.query(DiscountRule).filter(
        DiscountRule.id == discount_rule_id
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
    rule: DiscountRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing discount rule"""
    # No tenant_id filtering needed since we're in the tenant's database
    discount_rule = db.query(DiscountRule).filter(
        DiscountRule.id == discount_rule_id
    ).first()
    
    if not discount_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount rule not found"
        )
    
    # Update fields
    for field, value in rule.dict(exclude_unset=True).items():
        setattr(discount_rule, field, value)
    
    discount_rule.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(discount_rule)
    
    return discount_rule

@router.delete("/{discount_rule_id}")
async def delete_discount_rule(
    discount_rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a discount rule"""
    # No tenant_id filtering needed since we're in the tenant's database
    discount_rule = db.query(DiscountRule).filter(
        DiscountRule.id == discount_rule_id
    ).first()
    
    if not discount_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount rule not found"
        )
    
    db.delete(discount_rule)
    db.commit()
    
    return {"message": "Discount rule deleted successfully"}

@router.post("/calculate")
async def calculate_discount(
    request: DiscountCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate discount for a given subtotal"""
    # No tenant_id filtering needed since we're in the tenant's database
    discount_rules = db.query(DiscountRule).filter(
        DiscountRule.is_active == True,
        DiscountRule.min_amount <= request.subtotal
    ).order_by(DiscountRule.priority.desc(), DiscountRule.min_amount.desc()).all()
    
    if not discount_rules:
        return {
            "discount_amount": 0.0,
            "discount_type": "percentage",
            "discount_value": 0.0,
            "rule_name": None
        }
    
    # Apply the first (highest priority) rule
    rule = discount_rules[0]
    
    if rule.discount_type == "percentage":
        discount_amount = request.subtotal * (rule.discount_value / 100)
    else:  # fixed
        discount_amount = rule.discount_value
    
    return {
        "discount_amount": discount_amount,
        "discount_type": rule.discount_type,
        "discount_value": rule.discount_value,
        "rule_name": rule.name
    } 