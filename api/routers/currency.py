from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timezone
import logging

from models.database import get_db
from models.models import User
from routers.auth import get_current_user
from services.currency_service import CurrencyService
from schemas.currency import (
    SupportedCurrency, SupportedCurrencyCreate, SupportedCurrencyUpdate, CurrencyListResponse, CurrencyRate,
    CurrencyRateCreate, CurrencyRateUpdate, ExchangeRateListResponse,
    CurrencyConversion
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/currency", tags=["currency"])

@router.get("/supported", response_model=CurrencyListResponse)
async def get_supported_currencies(
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
async def get_exchange_rates(
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
async def create_or_update_exchange_rate(
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
async def update_exchange_rate(
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
        
        existing_rate.updated_at = datetime.now(timezone.utc)
        
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
async def convert_currency(
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
async def delete_exchange_rate(
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

@router.post("/custom", response_model=SupportedCurrency)
async def create_custom_currency(
    currency_data: SupportedCurrencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a custom currency"""
    try:
        from models.models import SupportedCurrency as SupportedCurrencyModel
        
        # Check if currency code already exists
        existing_currency = db.query(SupportedCurrencyModel).filter(
            SupportedCurrencyModel.code == currency_data.code.upper()
        ).first()
        
        if existing_currency:
            raise HTTPException(
                status_code=400,
                detail=f"Currency with code {currency_data.code.upper()} already exists"
            )
        
        # Create new currency
        new_currency = SupportedCurrencyModel(
            code=currency_data.code.upper(),
            name=currency_data.name,
            symbol=currency_data.symbol,
            decimal_places=currency_data.decimal_places,
            is_active=currency_data.is_active
        )
        
        # Set updated_at if the column exists
        try:
            new_currency.updated_at = datetime.now(timezone.utc)
        except AttributeError:
            # updated_at column might not exist yet
            pass
        
        db.add(new_currency)
        db.commit()
        db.refresh(new_currency)
        
        return new_currency
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom currency: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create custom currency"
        )

@router.put("/custom/{currency_id}", response_model=SupportedCurrency)
async def update_custom_currency(
    currency_id: int,
    currency_update: SupportedCurrencyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a custom currency"""
    try:
        from models.models import SupportedCurrency as SupportedCurrencyModel
        
        # Get existing currency
        existing_currency = db.query(SupportedCurrencyModel).filter(
            SupportedCurrencyModel.id == currency_id
        ).first()
        
        if not existing_currency:
            raise HTTPException(
                status_code=404,
                detail="Currency not found"
            )
        
        # Update fields
        if currency_update.name is not None:
            existing_currency.name = currency_update.name
        
        if currency_update.symbol is not None:
            existing_currency.symbol = currency_update.symbol
        
        if currency_update.decimal_places is not None:
            existing_currency.decimal_places = currency_update.decimal_places
        
        if currency_update.is_active is not None:
            existing_currency.is_active = currency_update.is_active
        
        from datetime import datetime
        try:
            existing_currency.updated_at = datetime.now(timezone.utc)
        except AttributeError:
            # updated_at column might not exist yet
            pass
        
        db.commit()
        db.refresh(existing_currency)
        
        return existing_currency
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating custom currency: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update custom currency"
        )

@router.delete("/custom/{currency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_currency(
    currency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a custom currency"""
    try:
        from models.models import SupportedCurrency as SupportedCurrencyModel
        
        # Get existing currency
        existing_currency = db.query(SupportedCurrencyModel).filter(
            SupportedCurrencyModel.id == currency_id
        ).first()
        
        if not existing_currency:
            raise HTTPException(
                status_code=404,
                detail="Currency not found"
            )
        
        # Check if currency is being used in invoices or payments
        from models.models import Invoice
        from routers.payments import Payment
        invoice_count = db.query(Invoice).filter(Invoice.currency == existing_currency.code).count()
        payment_count = db.query(Payment).filter(Payment.currency == existing_currency.code).count()
        
        if invoice_count > 0 or payment_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete currency {existing_currency.code} as it is being used in {invoice_count} invoices and {payment_count} payments"
            )
        
        db.delete(existing_currency)
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting custom currency: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete custom currency"
        ) 