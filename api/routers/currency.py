from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import logging

from models.database import get_db
from models.models import User
from routers.auth import get_current_user
from services.currency_service import CurrencyService
from schemas.currency import (
    SupportedCurrency, CurrencyListResponse, CurrencyRate,
    CurrencyRateCreate, CurrencyRateUpdate, ExchangeRateListResponse,
    CurrencyConversion
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/currency", tags=["currency"])

@router.get("/supported", response_model=CurrencyListResponse)
def get_supported_currencies(
    active_only: bool = Query(True, description="Return only active currencies"),
    db: Session = Depends(get_db)
):
    """Get list of supported currencies"""
    try:
        currency_service = CurrencyService(db)
        currencies = currency_service.get_supported_currencies(active_only=active_only)
        return CurrencyListResponse(currencies=currencies)
    except Exception as e:
        logger.error(f"Error fetching supported currencies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch supported currencies"
        )

@router.get("/rates", response_model=ExchangeRateListResponse)
def get_exchange_rates(
    base_currency: Optional[str] = Query(None, description="Filter by base currency"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current exchange rates for the tenant"""
    try:
        currency_service = CurrencyService(db)
        rates = currency_service.get_tenant_exchange_rates(
            current_user.tenant_id, 
            base_currency=base_currency
        )
        tenant_default_currency = currency_service.get_tenant_default_currency(current_user.tenant_id)
        
        return ExchangeRateListResponse(
            rates=rates,
            base_currency=tenant_default_currency
        )
    except Exception as e:
        logger.error(f"Error fetching exchange rates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch exchange rates"
        )

@router.post("/rates", response_model=CurrencyRate)
def create_or_update_exchange_rate(
    rate_data: CurrencyRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update an exchange rate"""
    try:
        currency_service = CurrencyService(db)
        
        # Validate currency codes
        if not currency_service.validate_currency_code(rate_data.from_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid from_currency: {rate_data.from_currency}"
            )
        
        if not currency_service.validate_currency_code(rate_data.to_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid to_currency: {rate_data.to_currency}"
            )
        
        if rate_data.from_currency == rate_data.to_currency:
            raise HTTPException(
                status_code=400,
                detail="From and to currencies cannot be the same"
            )
        
        if rate_data.rate <= 0:
            raise HTTPException(
                status_code=400,
                detail="Exchange rate must be positive"
            )
        
        exchange_rate = currency_service.update_exchange_rate(
            tenant_id=current_user.tenant_id,
            from_currency=rate_data.from_currency,
            to_currency=rate_data.to_currency,
            rate=rate_data.rate,
            effective_date=rate_data.effective_date.date() if rate_data.effective_date else None
        )
        
        return exchange_rate
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating/updating exchange rate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create/update exchange rate"
        )

@router.put("/rates/{rate_id}", response_model=CurrencyRate)
def update_exchange_rate(
    rate_id: int,
    rate_update: CurrencyRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a specific exchange rate"""
    try:
        from models.models import CurrencyRate as CurrencyRateModel
        
        # Get existing rate
        existing_rate = db.query(CurrencyRateModel).filter(
            CurrencyRateModel.id == rate_id,
            CurrencyRateModel.tenant_id == current_user.tenant_id
        ).first()
        
        if not existing_rate:
            raise HTTPException(
                status_code=404,
                detail="Exchange rate not found"
            )
        
        # Update fields
        if rate_update.rate is not None:
            if rate_update.rate <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Exchange rate must be positive"
                )
            existing_rate.rate = rate_update.rate
        
        if rate_update.effective_date is not None:
            existing_rate.effective_date = rate_update.effective_date
        
        from datetime import datetime
        existing_rate.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing_rate)
        
        return existing_rate
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating exchange rate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update exchange rate"
        )

@router.post("/convert", response_model=CurrencyConversion)
def convert_currency(
    amount: float = Query(..., description="Amount to convert"),
    from_currency: str = Query(..., description="Source currency code"),
    to_currency: str = Query(..., description="Target currency code"),
    conversion_date: Optional[date] = Query(None, description="Date for conversion rate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Convert amount from one currency to another"""
    try:
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Amount must be positive"
            )
        
        currency_service = CurrencyService(db)
        
        # Validate currency codes
        if not currency_service.validate_currency_code(from_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid from_currency: {from_currency}"
            )
        
        if not currency_service.validate_currency_code(to_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid to_currency: {to_currency}"
            )
        
        conversion = currency_service.convert_currency(
            tenant_id=current_user.tenant_id,
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            conversion_date=conversion_date
        )
        
        if conversion is None:
            raise HTTPException(
                status_code=404,
                detail=f"No exchange rate found for {from_currency} to {to_currency}"
            )
        
        return conversion
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting currency: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to convert currency"
        )

@router.delete("/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exchange_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an exchange rate"""
    try:
        from models.models import CurrencyRate as CurrencyRateModel
        
        existing_rate = db.query(CurrencyRateModel).filter(
            CurrencyRateModel.id == rate_id,
            CurrencyRateModel.tenant_id == current_user.tenant_id
        ).first()
        
        if not existing_rate:
            raise HTTPException(
                status_code=404,
                detail="Exchange rate not found"
            )
        
        db.delete(existing_rate)
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting exchange rate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete exchange rate"
        ) 