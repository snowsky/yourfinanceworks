"""Shared currency utilities used across OCR extraction and schema validation."""

# Maps common currency symbols to ISO 4217 codes.
CURRENCY_SYMBOL_MAP: dict = {
    '$': 'USD',
    '€': 'EUR',
    '£': 'GBP',
    '¥': 'JPY',
    '₹': 'INR',
    'C$': 'CAD',
    'A$': 'AUD',
    'NZ$': 'NZD',
    'HK$': 'HKD',
    'S$': 'SGD',
    'R$': 'BRL',
    'R': 'ZAR',
    '₽': 'RUB',
    '₩': 'KRW',
    '₺': 'TRY',
    'kr': 'SEK',
    'CHF': 'CHF',
}


def normalize_currency(value: str, default: str = 'USD') -> str:
    """Convert a currency symbol or code to an ISO 4217 code.

    Returns *default* when the value is unrecognised.
    """
    if not isinstance(value, str):
        return default
    stripped = value.strip()
    if stripped in CURRENCY_SYMBOL_MAP:
        return CURRENCY_SYMBOL_MAP[stripped]
    upper = stripped.upper()
    if len(upper) == 3 and upper.isalpha():
        return upper
    return default
