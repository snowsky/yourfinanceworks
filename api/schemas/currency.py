from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SupportedCurrencyBase(BaseModel):
    code: str = Field(..., description="ISO 4217 currency code")
    name: str = Field(..., description="Currency name")
    symbol: str = Field(..., description="Currency symbol")
    decimal_places: int = Field(2, description="Number of decimal places")
    is_active: bool = Field(True, description="Whether the currency is active")

class SupportedCurrency(SupportedCurrencyBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CurrencyRateBase(BaseModel):
    from_currency: str = Field(..., description="Source currency code")
    to_currency: str = Field(..., description="Target currency code")
    rate: float = Field(..., description="Exchange rate")
    effective_date: datetime = Field(..., description="Date when the rate becomes effective")

class CurrencyRateCreate(CurrencyRateBase):
    pass

class CurrencyRateUpdate(BaseModel):
    rate: Optional[float] = Field(None, description="Exchange rate")
    effective_date: Optional[datetime] = Field(None, description="Date when the rate becomes effective")

class CurrencyRate(CurrencyRateBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CurrencyConversion(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    converted_amount: float
    exchange_rate: float
    conversion_date: datetime

class CurrencyListResponse(BaseModel):
    currencies: List[SupportedCurrency] = Field(..., description="List of supported currencies")

class ExchangeRateListResponse(BaseModel):
    rates: List[CurrencyRate] = Field(..., description="List of exchange rates")
    base_currency: str = Field(..., description="Base currency for the tenant") 