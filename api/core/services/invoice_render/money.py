# api/core/services/invoice_render/money.py
"""Single currency formatter for invoice rendering."""

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
            "CAD": "$", "AUD": "$", "INR": "₹"}
_ZERO_DECIMAL = {"JPY"}


def format_money(amount: float, currency: str) -> str:
    currency = (currency or "USD").upper()
    symbol = _SYMBOLS.get(currency, "")
    if currency in _ZERO_DECIMAL:
        body = f"{amount:,.0f}"
    else:
        body = f"{amount:,.2f}"
    return f"{symbol}{body}" if symbol else f"{body} {currency}"
