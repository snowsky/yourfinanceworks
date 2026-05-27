"""Local document discovery and classification for YFW ingestion."""

from __future__ import annotations

import csv
import mimetypes
from pathlib import Path
from typing import Iterable

from .config import Profile
from .logging_config import get_logger
from .models import ClassifiedDocument, to_decimal


logger = get_logger("classifier")

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".csv"}
DOCUMENT_TYPES = {"expense", "invoice", "statement", "portfolio"}


class DocumentClassifier:
    """Classifies local files before they are sent to YFW."""

    KEYWORDS = {
        "invoice": ("invoice", "inv-", "bill to", "amount due", "payment terms", "invoice number"),
        "expense": ("receipt", "expense", "merchant", "subtotal", "tip", "paid", "purchase"),
        "statement": ("statement", "bank", "account summary", "opening balance", "closing balance", "transactions"),
        "portfolio": ("portfolio", "holdings", "asset allocation", "ticker", "symbol", "quantity", "market value"),
    }

    def __init__(self, profile: Profile):
        self.profile = profile

    def scan(self, folder: Path, *, recursive: bool = True) -> list[Path]:
        pattern = "**/*" if recursive else "*"
        return sorted(path for path in folder.glob(pattern) if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS)

    def classify(self, path: Path) -> ClassifiedDocument:
        sample = self._extract_sample(path)
        filename_text = path.name.replace("_", " ").replace("-", " ")
        text = f"{filename_text}\n{sample}".lower()
        heuristic_type, score = self._classify_with_keywords(text)
        if score >= 2:
            return ClassifiedDocument(
                path=str(path),
                filename=path.name,
                document_type=heuristic_type,
                confidence=to_decimal(min(0.95, 0.55 + (score * 0.08))),
                reason="filename/content keyword match",
            )

        llm_type = self._classify_with_llm(path, sample)
        if llm_type:
            return ClassifiedDocument(
                path=str(path),
                filename=path.name,
                document_type=llm_type,
                confidence=to_decimal("0.80"),
                reason="LLM classification",
            )

        fallback = "portfolio" if path.suffix.lower() == ".csv" else "expense"
        return ClassifiedDocument(
            path=str(path),
            filename=path.name,
            document_type=fallback,
            confidence=to_decimal("0.35"),
            reason="fallback classification",
        )

    def _classify_with_keywords(self, text: str) -> tuple[str, int]:
        scores = {
            doc_type: sum(1 for keyword in keywords if keyword in text)
            for doc_type, keywords in self.KEYWORDS.items()
        }
        best_type = max(scores, key=scores.get)
        return best_type, scores[best_type]

    def _classify_with_llm(self, path: Path, sample: str) -> str | None:
        if not self.profile.llm_model:
            return None
        try:
            from litellm import completion
        except ImportError:
            return None

        prompt = (
            "Classify this financial document as exactly one of: "
            "expense, invoice, statement, portfolio.\n"
            "Use portfolio for brokerage/investment holdings or asset allocation files.\n"
            "Return only the single lowercase label.\n\n"
            f"Filename: {path.name}\n"
            f"MIME: {mimetypes.guess_type(path.name)[0] or 'unknown'}\n"
            f"Extracted text:\n{sample[:4000]}"
        )
        kwargs = {
            "model": self._model_name(),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8,
            "temperature": 0,
        }
        if self.profile.llm_api_key:
            kwargs["api_key"] = self.profile.llm_api_key
        if self.profile.llm_base_url:
            kwargs["api_base"] = self.profile.llm_base_url

        response = completion(**kwargs)
        content = response.choices[0].message.content.strip().lower()
        for doc_type in DOCUMENT_TYPES:
            if doc_type in content:
                return doc_type
        return None

    def _model_name(self) -> str:
        provider = (self.profile.llm_provider or "").strip().lower()
        model = str(self.profile.llm_model)
        if not provider or provider == "openai" or "/" in model:
            return model
        return f"{provider}/{model}"

    def _extract_sample(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._sample_csv(path)
        if suffix == ".pdf":
            return self._sample_pdf(path)
        return ""

    def _sample_csv(self, path: Path) -> str:
        lines: list[str] = []
        try:
            with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
                reader = csv.reader(handle)
                for index, row in enumerate(reader):
                    lines.append(",".join(row[:20]))
                    if index >= 20:
                        break
        except OSError as exc:
            logger.warning("Could not read CSV %s: %s", path, exc)
            return ""
        return "\n".join(lines)

    def _sample_pdf(self, path: Path) -> str:
        for extractor in (self._sample_pdf_with_pypdf, self._sample_pdf_with_pymupdf):
            text = extractor(path)
            if text.strip():
                return text
        return ""

    def _sample_pdf_with_pypdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        try:
            reader = PdfReader(str(path))
            return "\n".join((page.extract_text() or "") for page in reader.pages[:3])[:5000]
        except Exception as exc:
            logger.warning("pypdf failed to extract text from %s: %s", path, exc)
            return ""

    def _sample_pdf_with_pymupdf(self, path: Path) -> str:
        try:
            import fitz
        except ImportError:
            return ""
        try:
            doc = fitz.open(str(path))
            return "\n".join(doc[index].get_text() for index in range(min(3, len(doc))))[:5000]
        except Exception as exc:
            logger.warning("pymupdf failed to extract text from %s: %s", path, exc)
            return ""


def classify_paths(paths: Iterable[Path], profile: Profile) -> list[ClassifiedDocument]:
    classifier = DocumentClassifier(profile)
    return [classifier.classify(path) for path in paths]
