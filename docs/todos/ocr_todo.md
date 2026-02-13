# OCR Optimization & Extensibility TODO

This document tracks the research findings and planned improvements for the OCR and LLM extraction pipeline.

## 🔍 Key Findings: Extraction Patterns

Through architectural review, we identified a fundamental difference in how different documents are processed:

- **Portfolio Imports (Investments)**: Uses a **Two-Step Pipeline**.
  - 1. Text extraction (searchable PDF text or Unstructured OCR).
  - 2. Text-only LLM call (sending just the extracted string).
  - _Status_: Working on a "Fast Path" to skip OCR for searchable PDFs.
- **Invoices & Expenses**: Uses **AI Vision**.
  - Sends actual file bytes (images/PDFs) directly to a vision-capable LLM (GPT-4o, Ollama Vision, etc.).
  - _Benefit_: Higher accuracy for complex layouts.

---

## 🛠 Active Task: High Quality Mode (Force OCR)

Implementing a user-controllable toggle to force high-fidelity OCR even when a fast extraction path is available.

- [ ] **Config Layer**
  - [ ] Add `force_ocr` to `OCRConfig`.
  - [ ] Support `BANK_OCR_FORCE_OCR` environment variable.
- [ ] **Service Layer**
  - [ ] Update `EnhancedPDFTextExtractor` to respect the flag and bypass quality checks if enabled.
  - [ ] Update `UnifiedOCRService` to route `GENERIC_DOCUMENT` through the PDF extractor by default.
- [ ] **Worker Layer**
  - [ ] propagate the flag through Kafka payloads (`holdings_import_worker.py`).
- [ ] **UI Layer**
  - [ ] Add "High Quality Mode" toggle in the Portfolio upload/reprocess modals.

---

## 🔌 Extensibility: Plugging in External Services

The system is designed to support various external providers:

1. **AI Vision (LiteLLM)**: Support for 100+ providers (Azure, Bedrock, Vertex AI) is already available via the `StructuredDataEngine`. Simply update the AI Configuration in the database or env.
2. **Unstructured API**: Can be toggled to use their hosted service for better performance/scaling.
3. **Custom Engines**: New handlers can be registered in `TextExtractionEngine` to support services like Amazon Textract or Azure Document Intelligence.

---

## 🚀 Future Roadmap

- [ ] **Fast Path for Invoices/Expenses**: Add an option to skip Vision and use text-only extraction for simple/searchable invoices to save costs.
- [ ] **Hybrid Extraction**: Implement a "best of both worlds" approach where layout-heavy parts use Vision and standard text uses fast extraction.
- [ ] **OCR Quality Scoring**: Automate the switching to "High Quality Mode" if the first pass yields a low confidence score.
