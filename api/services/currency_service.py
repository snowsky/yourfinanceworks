from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, date
import logging

from models.models import SupportedCurrency, CurrencyRate, Tenant, Client
from schemas.currency import CurrencyConversion

logger = logging.getLogger(__name__)

class CurrencyService:
    """Service class for handling currency operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_supported_currencies(self, active_only: bool = True) -> List[SupportedCurrency]:
        """Get list of supported currencies"""
        query = self.db.query(SupportedCurrency)
        if active_only:
            query = query.filter(SupportedCurrency.is_active == True)
        return query.order_by(SupportedCurrency.code).all()
    
    def get_currency_by_code(self, code: str) -> Optional[SupportedCurrency]:
        """Get a specific currency by its code"""
        return self.db.query(SupportedCurrency).filter(
            SupportedCurrency.code == code,
            SupportedCurrency.is_active == True
        ).first()
    
    def get_tenant_default_currency(self, tenant_id: int) -> str:
        """Get the default currency for a tenant"""
        try:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            return tenant.default_currency if tenant else "USD"
        except Exception as e:
            logger.warning(f"Error getting tenant default currency: {e}")
            # Fallback to USD if there's any database error
            return "USD"
    
    def get_client_preferred_currency(self, client_id: int, tenant_id: int) -> str:
        """Get the preferred currency for a client, fallback to tenant default"""
        try:
            client = self.db.query(Client).filter(
                Client.id == client_id,
                Client.tenant_id == tenant_id
            ).first()
            
            if client and client.preferred_currency:
                return client.preferred_currency
            
            return self.get_tenant_default_currency(tenant_id)
        except Exception as e:
            logger.warning(f"Error getting client preferred currency: {e}")
            # Fallback to USD if there's any database error
            return "USD"
    
    def get_exchange_rate(self, tenant_id: int, from_currency: str, to_currency: str, 
                         effective_date: Optional[date] = None) -> Optional[float]:
        """Get exchange rate between two currencies"""
        if from_currency == to_currency:
            return 1.0
        
        if effective_date is None:
            effective_date = date.today()
        
        # Get the most recent rate for the given date
        rate = self.db.query(CurrencyRate).filter(
            CurrencyRate.tenant_id == tenant_id,
            CurrencyRate.from_currency == from_currency,
            CurrencyRate.to_currency == to_currency,
            CurrencyRate.effective_date <= effective_date
        ).order_by(desc(CurrencyRate.effective_date)).first()
        
        return rate.rate if rate else None
    
    def convert_currency(self, tenant_id: int, amount: float, from_currency: str, 
                        to_currency: str, conversion_date: Optional[date] = None) -> Optional[CurrencyConversion]:
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return CurrencyConversion(
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                converted_amount=amount,
                exchange_rate=1.0,
                conversion_date=datetime.now()
            )
        
        exchange_rate = self.get_exchange_rate(tenant_id, from_currency, to_currency, conversion_date)
        
        if exchange_rate is None:
            logger.warning(f"No exchange rate found for {from_currency} to {to_currency}")
            return None
        
        converted_amount = amount * exchange_rate
        
        return CurrencyConversion(
            from_currency=from_currency,
            to_currency=to_currency,
            amount=amount,
            converted_amount=converted_amount,
            exchange_rate=exchange_rate,
            conversion_date=datetime.now()
        )
    
    def update_exchange_rate(self, tenant_id: int, from_currency: str, to_currency: str, 
                           rate: float, effective_date: Optional[date] = None) -> CurrencyRate:
        """Update or create an exchange rate"""
        if effective_date is None:
            effective_date = date.today()
        
        # Check if rate already exists for this date
        existing_rate = self.db.query(CurrencyRate).filter(
            CurrencyRate.tenant_id == tenant_id,
            CurrencyRate.from_currency == from_currency,
            CurrencyRate.to_currency == to_currency,
            CurrencyRate.effective_date == effective_date
        ).first()
        
        if existing_rate:
            existing_rate.rate = rate
            existing_rate.updated_at = datetime.utcnow()
            currency_rate = existing_rate
        else:
            currency_rate = CurrencyRate(
                tenant_id=tenant_id,
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                effective_date=effective_date
            )
            self.db.add(currency_rate)
        
        self.db.commit()
        self.db.refresh(currency_rate)
        return currency_rate
    
    def get_tenant_exchange_rates(self, tenant_id: int, base_currency: Optional[str] = None) -> List[CurrencyRate]:
        """Get all current exchange rates for a tenant"""
        query = self.db.query(CurrencyRate).filter(
            CurrencyRate.tenant_id == tenant_id
        )
        
        if base_currency:
            query = query.filter(CurrencyRate.from_currency == base_currency)
        
        # Get the most recent rate for each currency pair
        subquery = self.db.query(
            CurrencyRate.from_currency,
            CurrencyRate.to_currency,
            desc(CurrencyRate.effective_date).label('max_date')
        ).filter(
            CurrencyRate.tenant_id == tenant_id
        ).group_by(
            CurrencyRate.from_currency,
            CurrencyRate.to_currency
        ).subquery()
        
        rates = self.db.query(CurrencyRate).join(
            subquery,
            (CurrencyRate.from_currency == subquery.c.from_currency) &
            (CurrencyRate.to_currency == subquery.c.to_currency) &
            (CurrencyRate.effective_date == subquery.c.max_date)
        ).filter(
            CurrencyRate.tenant_id == tenant_id
        ).all()
        
        return rates
    
    def format_currency(self, amount: float, currency_code: str) -> str:
        """Format amount with currency symbol"""
        currency = self.get_currency_by_code(currency_code)
        if not currency:
            return f"{amount:.2f} {currency_code}"
        
        decimal_places = currency.decimal_places
        symbol = currency.symbol
        
        formatted_amount = f"{amount:.{decimal_places}f}"
        return f"{symbol}{formatted_amount}"
    
    def validate_currency_code(self, currency_code: str) -> bool:
        """Validate if currency code is supported and active"""
        try:
            currency = self.get_currency_by_code(currency_code)
            if currency is not None:
                return True
            
            # Fallback: if supported_currencies table doesn't exist or is empty,
            # allow common currency codes
            fallback_currencies = {
                'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'CNY', 'INR', 'BRL'
            }
            return currency_code.upper() in fallback_currencies
            
        except Exception as e:
            logger.warning(f"Error validating currency {currency_code}: {e}")
            # Fallback: allow common currency codes if there's any database error
            fallback_currencies = {
                'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'CNY', 'INR', 'BRL'
            }
            return currency_code.upper() in fallback_currencies 