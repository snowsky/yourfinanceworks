from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

ALLOWED_RECORD_TYPES = {"invoice", "expense", "payment", "client", "bank_statement", "portfolio"}


class ShareTokenCreate(BaseModel):
    record_type: str
    record_id: int


class ShareTokenResponse(BaseModel):
    token: str
    record_type: str
    record_id: int
    share_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True


# --- Public view schemas (safe fields only) ---

class PublicInvoiceItem(BaseModel):
    description: str
    quantity: float
    price: float
    amount: float
    unit_of_measure: Optional[str] = None


class PublicInvoiceView(BaseModel):
    record_type: str = "invoice"
    id: int
    number: str
    amount: float
    currency: str
    status: str
    due_date: Optional[datetime] = None
    created_at: datetime
    description: Optional[str] = None
    subtotal: float
    discount_type: str
    discount_value: float
    payer: str
    client_name: Optional[str] = None
    client_company: Optional[str] = None
    items: List[PublicInvoiceItem] = []


class PublicExpenseView(BaseModel):
    record_type: str = "expense"
    id: int
    amount: Optional[float] = None
    currency: str
    expense_date: datetime
    category: str
    vendor: Optional[str] = None
    total_amount: Optional[float] = None
    payment_method: Optional[str] = None
    status: str
    created_at: datetime


class PublicPaymentView(BaseModel):
    record_type: str = "payment"
    id: int
    amount: float
    currency: str
    payment_date: datetime
    payment_method: str
    invoice_number: Optional[str] = None
    created_at: datetime


class PublicClientView(BaseModel):
    record_type: str = "client"
    id: int
    name: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime


class PublicBankStatementTransaction(BaseModel):
    date: date
    description: str
    amount: float
    transaction_type: str
    category: Optional[str] = None


class PublicBankStatementView(BaseModel):
    record_type: str = "bank_statement"
    id: int
    original_filename: str
    card_type: str
    status: str
    extracted_count: int
    created_at: datetime
    transactions: List[PublicBankStatementTransaction] = []


class PublicPortfolioHolding(BaseModel):
    security_symbol: str
    security_name: Optional[str] = None
    security_type: str
    asset_class: str
    quantity: float
    currency: str


class PublicPortfolioView(BaseModel):
    record_type: str = "portfolio"
    id: int
    name: str
    portfolio_type: str
    currency: str
    created_at: datetime
    holdings: List[PublicPortfolioHolding] = []
