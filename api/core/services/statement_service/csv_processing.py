"""CSV parsing and legacy text-processing utilities for bank statement extraction."""
import logging
import re
from typing import Any, Dict, List, Optional

from core.utils.file_validation import validate_file_path

from ._shared import _normalize_date, _normalize_column_name, _clean_and_deduplicate_transactions

logger = logging.getLogger(__name__)


def build_bank_transactions_prompt(text: str) -> str:
    """Legacy function - use BankTransactionExtractor._create_extraction_prompt instead"""
    return f"""You are a financial data extraction expert. Extract bank transactions from the text below.

RULES:
1. Look for dates, descriptions, and amounts
2. Amounts with "-" or in parentheses are debits (money out)
3. Positive amounts are credits (money in)
4. Convert dates to YYYY-MM-DD format
5. Extract merchant names clearly
6. Only extract actual transactions, not headers or summaries

TEXT:
{{text}}

Return ONLY a JSON array like this example:
[
  {{"date": "2024-01-15", "description": "GROCERY STORE", "amount": -45.67, "transaction_type": "debit", "balance": 1234.56}},
  {{"date": "2024-01-16", "description": "SALARY DEPOSIT", "amount": 2500.00, "transaction_type": "credit", "balance": 3689.89}}
]

JSON:"""


def _enhanced_regex_extraction(text: str) -> List[Dict[str, Any]]:
    """Legacy function - use BankTransactionExtractor._extract_with_regex instead"""
    transactions = []

    # Look for transaction-like patterns - exact from test-main.py
    patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
        r'(\d{4}-\d{2}-\d{2})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.MULTILINE)
        for match in matches:
            try:
                date, desc, amount = match
                amount_float = float(amount.replace('$', '').replace(',', ''))

                transactions.append({
                    'date': date,
                    'description': desc.strip(),
                    'amount': amount_float,
                    'transaction_type': 'debit' if amount_float < 0 else 'credit'
                })
            except Exception:
                continue

    return transactions


def _preprocess_bank_text(raw_text: str) -> str:
    """Legacy function - use BankTransactionExtractor.preprocess_documents instead"""
    text = raw_text

    # Clean PDF artifacts - exact from test-main.py
    text = re.sub(r'Page \d+ of \d+', '', text)
    text = re.sub(r'Statement Period:.*?\n', '', text)
    text = re.sub(r'Account Summary.*?\n', '', text)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def _parse_csv_file_basic(csv_path: str) -> List[Dict[str, Any]]:
    """Robust CSV fallback parser for bank exports with possible preambles.

    - Skips preamble lines before the real header
    - Handles common header variants: Date Posted, Transaction Amount, Transaction Type, Description
    - Converts YYYYMMDD to YYYY-MM-DD
    - Parses amounts, handling '$' and comma separators
    - Infers transaction_type from amount sign if missing
    - Skips obviously invalid/empty rows
    """
    import csv as _csv
    rows: List[Dict[str, Any]] = []
    try:
        # Validate csv_path to prevent path traversal
        try:
            safe_path = validate_file_path(csv_path)
        except ValueError as e:
            logger.error(str(e))
            return []
        # Read all lines first to locate the header row
        with open(safe_path, "r", encoding="utf-8", newline="") as f:
            lines = [ln.rstrip("\n\r") for ln in f]

        # Find header index: line with at least 3 commas and includes expected keywords
        header_idx = -1
        for i, ln in enumerate(lines):
            if not ln or ln.strip() == "":
                continue
            comma_count = ln.count(",")
            if comma_count < 2:
                continue
            probe = [c.strip().lower() for c in ln.split(",")]
            joined = ",".join(probe)
            if ("date" in joined or "posted" in joined) and ("amount" in joined or "description" in joined):
                header_idx = i
                break

        if header_idx == -1:
            return []

        data_lines = lines[header_idx:]
        reader = _csv.DictReader(data_lines)

        # Build a map from normalized header to actual keys
        norm_to_key: Dict[str, str] = {}
        for key in reader.fieldnames or []:
            norm_to_key[_normalize_column_name(key)] = key

        # Helper to get column by synonyms
        def key_for(*candidates: str) -> Optional[str]:
            for cand in candidates:
                if cand in norm_to_key:
                    return norm_to_key[cand]
            return None

        date_key = key_for("date", "dateposted", "transactiondate", "transdate")
        desc_key = key_for("description", "details", "memo", "payee", "narration")
        amt_key = key_for("amount", "transactionamount", "value", "amt")
        type_key = key_for("transactiontype", "type", "creditdebit", "debitcredit")
        bal_key = key_for("balance", "runningbalance")

        for r in reader:
            try:
                raw_date = (r.get(date_key) if date_key else "") or ""
                raw_desc = (r.get(desc_key) if desc_key else "") or ""
                raw_amt = (r.get(amt_key) if amt_key else "")
                raw_type = (r.get(type_key) if type_key else "")
                raw_bal = (r.get(bal_key) if bal_key else "")

                # Skip empty lines
                if not raw_date and not raw_desc and not raw_amt and not raw_type:
                    continue

                # Normalize date (support YYYYMMDD too)
                dt = _normalize_date(str(raw_date).strip())
                # Require strict YYYY-MM-DD to avoid counting stray lines
                if not dt or not re.match(r"^\d{4}-\d{2}-\d{2}$", dt):
                    # If date cannot be normalized, skip
                    continue

                # Parse amount (required)
                if raw_amt in (None, ""):
                    continue
                try:
                    amt_val = float(str(raw_amt).replace(",", "").replace("$", "").strip())
                except Exception:
                    logger.warning(f"Could not parse amount: {raw_amt}")
                    continue

                desc_text = str(raw_desc).strip()
                if not desc_text:
                    logger.warning(f"No description found for amount: {raw_amt}")
                    continue

                # Balance (optional)
                bal_val = None
                if raw_bal not in (None, ""):
                    try:
                        bal_val = float(str(raw_bal).replace(",", "").replace("$", "").strip())
                    except Exception:
                        logger.warning(f"Could not parse balance: {raw_bal}")
                        bal_val = None

                # Transaction type
                tx_type = str(raw_type or "").strip().lower()
                if tx_type not in ("debit", "credit"):
                    tx_type = "debit" if amt_val < 0 else "credit"

                rows.append({
                    "date": dt,
                    "description": desc_text,
                    "amount": amt_val,
                    "transaction_type": tx_type,
                    "balance": bal_val,
                })
            except Exception:
                continue

        # Deduplicate and sort
        if rows:
            rows = _clean_and_deduplicate_transactions(rows)
        return rows
    except Exception as e:
        logger.error(f"CSV basic parse failed: {e}")
        return []
