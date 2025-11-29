from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timezone
import logging

from core.models.models_per_tenant import DiscountRule
from core.schemas.discount_rule import DiscountRuleCreate, DiscountRuleUpdate, DiscountCalculationRequest

logger = logging.getLogger(__name__)

class DiscountRuleService:
    """Service class for handling discount rule operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_discount_rules(self) -> List[DiscountRule]:
        """Get all discount rules ordered by priority and minimum amount"""
        try:
            return self.db.query(DiscountRule).order_by(
                DiscountRule.priority.desc(),
                DiscountRule.min_amount.desc()
            ).all()
        except Exception as e:
            logger.error(f"Error fetching discount rules: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch discount rules: {str(e)}"
            )

    def get_discount_rule_by_id(self, discount_rule_id: int) -> DiscountRule:
        """Get a specific discount rule by ID"""
        try:
            discount_rule = self.db.query(DiscountRule).filter(
                DiscountRule.id == discount_rule_id
            ).first()

            if not discount_rule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Discount rule not found"
                )

            return discount_rule
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching discount rule {discount_rule_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch discount rule: {str(e)}"
            )

    def create_discount_rule(self, rule: DiscountRuleCreate) -> DiscountRule:
        """Create a new discount rule"""
        try:
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

            self.db.add(db_discount_rule)
            self.db.commit()
            self.db.refresh(db_discount_rule)

            return db_discount_rule
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating discount rule: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create discount rule: {str(e)}"
            )

    def update_discount_rule(self, discount_rule_id: int, rule: DiscountRuleUpdate) -> DiscountRule:
        """Update an existing discount rule"""
        try:
            discount_rule = self.get_discount_rule_by_id(discount_rule_id)

            # Update fields
            for field, value in rule.model_dump(exclude_unset=True).items():
                setattr(discount_rule, field, value)

            discount_rule.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(discount_rule)

            return discount_rule
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating discount rule {discount_rule_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update discount rule: {str(e)}"
            )

    def delete_discount_rule(self, discount_rule_id: int) -> dict:
        """Delete a discount rule"""
        try:
            discount_rule = self.get_discount_rule_by_id(discount_rule_id)

            self.db.delete(discount_rule)
            self.db.commit()

            return {"message": "Discount rule deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting discount rule {discount_rule_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete discount rule: {str(e)}"
            )

    def calculate_discount(self, request: DiscountCalculationRequest) -> dict:
        """Calculate discount for a given subtotal"""
        try:
            discount_rules = self.db.query(DiscountRule).filter(
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
        except Exception as e:
            logger.error(f"Error calculating discount: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to calculate discount: {str(e)}"
            )
