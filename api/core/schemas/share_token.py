from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime, date

ALLOWED_RECORD_TYPES = {"invoice", "expense", "payment", "client", "bank_statement", "portfolio"}


class ShareTokenCreate(BaseModel):
    record_type: str
    record_id: int
    access_type: str = Field("public", pattern="^(public|password|question)$")
    expires_in_hours: Optional[int] = Field(1, ge=0, le=8760)
    one_time: bool = False
    password: Optional[str] = None
    security_question: Optional[str] = None
    security_answer: Optional[str] = None

    @model_validator(mode="after")
    def validate_access_controls(self):
        if self.access_type == "password" and not self.password:
            raise ValueError("Password is required for password-protected shares")
        if self.access_type == "question":
            if not self.security_question or not self.security_answer:
                raise ValueError("Question and answer are required for question-protected shares")
        return self


class ShareTokenAccessRequest(BaseModel):
    password: Optional[str] = None
    security_answer: Optional[str] = None


class ShareTokenResponse(BaseModel):
    token: str
    record_type: str
    record_id: int
    share_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    access_type: str = "public"
    security_question: Optional[str] = None
    one_time: bool = False
    access_count: int = 0
    max_access_count: Optional[int] = None

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
    balance: Optional[float] = None
    category: Optional[str] = None


class PublicBankStatementView(BaseModel):
    record_type: str = "bank_statement"
    id: int
    original_filename: str
    bank_name: Optional[str] = None
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
