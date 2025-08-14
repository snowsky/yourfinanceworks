import os
import re
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import json as _json


@dataclass
class Transaction:
    date: str
    description: str
    amount: float
    transaction_type: str  # 'debit' | 'credit'
    balance: Optional[float] = None
    category: Optional[str] = None


class SimplePDFLoader:
    """Best-effort PDF text loader with graceful fallbacks."""

    def __init__(self) -> None:
        self._loaders: List[Any] = []
        # Try to hydrate optional loaders in a preferred order
        try:
            from langchain_community.document_loaders import PDFPlumberLoader as LC_PDFPlumberLoader  # type: ignore
            self._loaders.append(("pdfplumber", LC_PDFPlumberLoader))
        except Exception:
            pass
        try:
            from langchain_community.document_loaders import PyMuPDFLoader as LC_PyMuPDFLoader  # type: ignore
            self._loaders.append(("pymupdf", LC_PyMuPDFLoader))
        except Exception:
            pass
        try:
            from langchain_community.document_loaders import PyPDFLoader as LC_PyPDFLoader  # type: ignore
            self._loaders.append(("pypdf", LC_PyPDFLoader))
        except Exception:
            pass

    def load(self, pdf_path: str) -> List[str]:
        path = str(pdf_path)
        last_err: Optional[Exception] = None
        for name, loader_cls in self._loaders:
            try:
                loader = loader_cls(path)
                docs = loader.load()
                if docs:
                    return [d.page_content or "" for d in docs]
            except Exception as e:  # pragma: no cover - best effort
                last_err = e
                continue

        # Final fallback using PyPDF2 only for raw text
        try:
            import PyPDF2  # type: ignore

            texts: List[str] = []
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    texts.append(page.extract_text() or "")
            return texts
        except Exception as e:  # pragma: no cover
            if last_err:
                raise last_err
            raise e


def _normalize_date(value: str) -> str:
    value = value.strip()
    fmts = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%Y/%m/%d"]
    for fmt in fmts:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    # Attempt to parse dd Mon yyyy like 01 Jan 2024
    try:
        return datetime.strptime(value, "%d %b %Y").strftime("%Y-%m-%d")
    except Exception:
        return value


def build_bank_transactions_prompt(text: str) -> str:
    # Aligned to test-main.py prompt with explicit example and clarity for local models
    return (
        "You are a financial data extraction expert. Extract bank transactions from the text below.\n\n"
        "RULES:\n"
        "1. Look for dates, descriptions, and amounts\n"
        "2. Amounts with '-' or in parentheses are debits (money out)\n"
        "3. Positive amounts are credits (money in)\n"
        "4. Convert dates to YYYY-MM-DD format\n"
        "5. Extract merchant names clearly\n"
        "6. Only extract actual transactions, not headers or summaries\n\n"
        "TEXT:\n"
        f"{text}\n\n"
        "Return ONLY a JSON array like this example:\n"
        "[\n"
        "  {\"date\": \"2024-01-15\", \"description\": \"GROCERY STORE\", \"amount\": -45.67, \"transaction_type\": \"debit\", \"balance\": 1234.56},\n"
        "  {\"date\": \"2024-01-16\", \"description\": \"SALARY DEPOSIT\", \"amount\": 2500.00, \"transaction_type\": \"credit\", \"balance\": 3689.89}\n"
        "]\n\nJSON:"
    )


def _regex_extract_transactions(text: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    # Patterns aligned with test-main fallback, slightly more tolerant with $ and commas
    patterns = [
        r"(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?P<desc>[^$\d-]+?)\s+(?P<amount>[-$]?\d[\d,]*\.?\d*)",
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<desc>[^$\d-]+?)\s+(?P<amount>[-$]?\d[\d,]*\.?\d*)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.MULTILINE):
            try:
                date = _normalize_date(m.group("date"))
                desc = re.sub(r"\s+", " ", m.group("desc").strip())
                amount_raw = (m.group("amount") or "0").replace("$", "").replace(",", "")
                amount = float(amount_raw)
                tx_type = "debit" if amount < 0 else "credit"
                results.append({
                    "date": date,
                    "description": desc,
                    "amount": amount,
                    "transaction_type": tx_type,
                })
            except Exception:
                continue
    return results


class BankStatementExtractor:
    """Extractor that uses Ollama when available, with regex fallback."""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_available = self._check_ollama()
        self._pdf_loader = SimplePDFLoader()

    def _check_ollama(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            models = [m.get("name") for m in (resp.json().get("models") or [])]
            return self.model_name in models
        except Exception:
            return False

    def _ollama_chat(self, prompt: str) -> Optional[str]:
        try:
            # Use lightweight REST call to Ollama chat API
            payload = {"model": self.model_name, "messages": [{"role": "user", "content": prompt}], "stream": False, "temperature": 0.1}
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                # Newer API returns message content in choices/message; fallback to old keys if needed
                if isinstance(data, dict) and "message" in data:
                    return data["message"].get("content", "")
                if "choices" in data and data["choices"]:
                    return data["choices"][0]["message"]["content"]
                return json.dumps(data)
            return None
        except Exception:
            return None

    def _build_extraction_prompt(self, text: str) -> str:
        return build_bank_transactions_prompt(text)

    def _parse_llm_json(self, content: str) -> List[Dict[str, Any]]:
        # Strip code fences if present
        s = re.sub(r"```json\s*|```", "", (content or "").strip())
        # Find first JSON array/object
        for pat in [r"\[[\s\S]*?\]", r"\{[\s\S]*?\}"]:
            m = re.search(pat, s)
            if not m:
                continue
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return [data]
            except Exception:
                continue
        return []

    def extract_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        pages = self._pdf_loader.load(pdf_path)
        combined_raw = "\n\n".join([p or "" for p in pages])

        # Preprocess/clean text similar to test-main
        def preprocess_text(text: str) -> str:
            t = text
            t = re.sub(r"Page\s+\d+\s+of\s+\d+", " ", t)
            t = re.sub(r"Statement Period:.*?\n", " ", t)
            t = re.sub(r"Account Summary.*?\n", " ", t)
            t = re.sub(r"\s+", " ", t)
            return t.strip()

        combined = preprocess_text(combined_raw)

        # If Ollama direct chat available, try once on entire text (capped)
        if self._ollama_available:
            prompt = self._build_extraction_prompt(combined[:12000])
            resp = self._ollama_chat(prompt)
            if resp:
                items = self._parse_llm_json(resp)
                if items:
                    return items

        # Chunk and attempt extraction per chunk via regex (LiteLLM path is handled in process function)
        return _regex_extract_transactions(combined)

    def extract_from_files(self, files: List[str]) -> List[Dict[str, Any]]:
        all_items: List[Dict[str, Any]] = []
        for f in files:
            try:
                items = self.extract_from_pdf(f)
                all_items.extend(items)
            except Exception:
                continue

        # Normalize, infer transaction_type when missing, coerce fields
        normalized: List[Dict[str, Any]] = []
        for it in all_items:
            date = _normalize_date(str(it.get("date", "")).strip())
            desc = str(it.get("description", "")).strip() or "Unknown"
            try:
                amount = float(it.get("amount", 0))
            except Exception:
                # Try to clean currency formatting
                try:
                    amount = float(str(it.get("amount", 0)).replace("$", "").replace(",", ""))
                except Exception:
                    amount = 0.0
            tx_type = str(it.get("transaction_type", "")).lower() or ("debit" if amount < 0 else "credit")
            bal_val = it.get("balance", None)
            try:
                balance = float(bal_val) if bal_val is not None else None
            except Exception:
                balance = None

            normalized.append(
                {
                    "date": date,
                    "description": desc,
                    "amount": amount,
                    "transaction_type": "debit" if tx_type not in ("debit", "credit") else tx_type,
                    "balance": balance,
                    "category": it.get("category"),
                }
            )

        # De-duplicate basic duplicates
        seen = set()
        unique: List[Dict[str, Any]] = []
        for it in normalized:
            key = (it["date"], it["description"], round(float(it["amount"]), 2))
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)

        # Sort by date
        try:
            unique.sort(key=lambda x: x["date"])  # YYYY-MM-DD lexicographic works
        except Exception:
            pass

        return unique


def extract_transactions_from_pdf_paths(pdf_paths: List[str]) -> List[Dict[str, Any]]:
    extractor = BankStatementExtractor()
    return extractor.extract_from_files(pdf_paths)


def process_bank_pdf_with_llm(pdf_path: str, ai_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """LLM-based extraction with chunking and regex fallback.
    ai_config (optional): {
      provider_name: 'openai'|'ollama'|'anthropic'|..., model_name: str, provider_url?: str, api_key?: str
    }
    """
    # Load text using best-effort loader (pdfplumber/pymupdf/pypdf fallback)
    try:
        pages = SimplePDFLoader().load(pdf_path)
        raw_text = "\n\n".join([p or "" for p in pages])
        # Preprocess similar to test-main
        text = re.sub(r"Page\s+\d+\s+of\s+\d+", " ", raw_text)
        text = re.sub(r"Statement Period:.*?\n", " ", text)
        text = re.sub(r"Account Summary.*?\n", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
    except Exception:
        text = ""

    if not text.strip():
        return extract_transactions_from_pdf_paths([pdf_path])

    # Try LiteLLM
    try:
        from litellm import completion  # type: ignore
    except Exception:
        return extract_transactions_from_pdf_paths([pdf_path])

    # We'll process in chunks with small overlap as in test-main
    try:
        # Build provider/model from AI config or env
        def build_kwargs(model_name: str) -> Dict[str, Any]:
            return {
                "model": model_name,
                "max_tokens": 1500,
                "temperature": 0.1,
            }

        def sanitize_ollama_base(url: Optional[str]) -> Optional[str]:
            if not url:
                return url
            # Strip trailing /api/* paths if present
            m = re.match(r"^(https?://[^/]+)(/api.*)?$", url.strip())
            return m.group(1) if m else url.strip()

        if ai_config:
            provider = (ai_config.get("provider_name") or "").lower()
            model_name = ai_config.get("model_name") or "gpt-oss:latest"
            if provider == "ollama":
                # litellm expects "ollama/<model>"
                model = f"ollama/{model_name}"
            elif provider == "anthropic":
                model = f"anthropic/{model_name}"
            else:
                model = model_name
            base_kwargs = build_kwargs(model)
            if ai_config.get("provider_url"):
                base_kwargs["api_base"] = sanitize_ollama_base(ai_config.get("provider_url"))
            if ai_config.get("api_key"):
                base_kwargs["api_key"] = ai_config.get("api_key")
        else:
            model_name = os.getenv("LLM_MODEL_BANK_STATEMENTS", os.getenv("OLLAMA_MODEL", "gpt-oss:latest"))
            provider_url = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
            # If Ollama URL present, use ollama/<model> provider and sanitize base
            if provider_url:
                model = f"ollama/{model_name}"
                base_kwargs = build_kwargs(model)
                base_kwargs["api_base"] = sanitize_ollama_base(provider_url)
            else:
                base_kwargs = build_kwargs(model_name)
            api_key = os.getenv("LLM_API_KEY")
            if api_key:
                base_kwargs["api_key"] = api_key

        # Chunk text and run per chunk (aligned with test-main defaults)
        max_len = 3000
        overlap = 150
        chunks: List[str] = []
        i = 0
        while i < len(text):
            chunk = text[i:i + max_len]
            if not chunk.strip():
                break
            chunks.append(chunk)
            i += max_len - overlap

        aggregated: List[Dict[str, Any]] = []
        for chunk in chunks:
            prompt = build_bank_transactions_prompt(chunk)
            kwargs = {**base_kwargs, "messages": [{"role": "user", "content": prompt}]}
            resp = completion(**kwargs)
            content = None
            if resp and hasattr(resp, 'choices') and resp.choices:
                choice = resp.choices[0]
                if hasattr(choice, 'message') and getattr(choice, 'message') is not None:
                    content = choice.message.content if hasattr(choice.message, 'content') else None
            if not content:
                # Try regex fallback for this chunk if no content
                aggregated.extend(_regex_extract_transactions(chunk))
                continue

            s = re.sub(r"```json\s*|```", "", content.strip())
            data = None
            try:
                data = _json.loads(s)
            except Exception:
                m = re.search(r"\[[\s\S]*?\]", s)
                if m:
                    try:
                        data = _json.loads(m.group(0))
                    except Exception:
                        data = None
            if not isinstance(data, list):
                # Regex fallback on chunk content
                aggregated.extend(_regex_extract_transactions(chunk))
                continue

            for it in data:
                try:
                    date = _normalize_date(str(it.get("date", "")))
                    desc = str(it.get("description", "")).strip() or "Unknown"
                    try:
                        amount = float(it.get("amount", 0))
                    except Exception:
                        amount = float(str(it.get("amount", 0)).replace("$", "").replace(",", ""))
                    tx_type = str(it.get("transaction_type", "")).lower() or ("debit" if amount < 0 else "credit")
                    bal_val = it.get("balance", None)
                    try:
                        balance = float(bal_val) if bal_val is not None else None
                    except Exception:
                        balance = None
                    aggregated.append({
                        "date": date,
                        "description": desc,
                        "amount": amount,
                        "transaction_type": "debit" if tx_type not in ("debit", "credit") else tx_type,
                        "balance": balance,
                        "category": it.get("category"),
                    })
                except Exception:
                    continue

        if not aggregated:
            return extract_transactions_from_pdf_paths([pdf_path])

        # Dedup and sort aggregated
        seen = set()
        uniq: List[Dict[str, Any]] = []
        for it in aggregated:
            key = (it["date"], it["description"], round(float(it["amount"]), 2))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)
        try:
            uniq.sort(key=lambda x: x["date"])  # YYYY-MM-DD
        except Exception:
            pass
        return uniq
    except Exception:
        return extract_transactions_from_pdf_paths([pdf_path])


