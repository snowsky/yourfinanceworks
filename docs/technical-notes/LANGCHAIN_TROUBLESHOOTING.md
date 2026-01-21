# LangChain Import Issues Troubleshooting

## Problem
OCR worker container fails with error: "LangChain is required for UniversalBankTransactionExtractor. Please install langchain package."

## Root Cause
LangChain v1.0+ has restructured its modules. The imports that worked in older versions need to be updated to use the new module structure.

## Solution

### 1. Updated Import Structure

**Old imports (LangChain < 1.0):**
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import HumanMessage, SystemMessage, AIMessage
```

**New imports (LangChain >= 1.0):**
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
```

### 2. Required Packages

Ensure these packages are installed in `requirements.txt`:
```
langchain==1.0.3
langchain-community==0.4.1
langchain-core==1.0.2
langchain-text-splitters==1.0.0
```

### 3. Testing Imports

Use the test script to verify imports work:
```bash
python scripts/test_langchain_imports.py
```

### 4. Container Rebuild

After updating requirements, rebuild the OCR worker container:
```bash
docker-compose build ocr-worker
docker-compose up -d ocr-worker
```

## Verification

1. Check that all LangChain packages are installed:
```bash
docker exec -ti invoice_app_ocr_worker pip list | grep langchain
```

2. Test the imports:
```bash
docker exec -ti invoice_app_ocr_worker python scripts/test_langchain_imports.py
```

3. Check OCR worker logs:
```bash
docker logs invoice_app_ocr_worker
```

## Fallback Behavior

The code now includes graceful fallback behavior:
- If LangChain imports fail, the system logs the error and continues
- Bank statement processing will be marked as failed with a clear error message
- The OCR worker won't crash and will continue processing other messages

## Common Issues

### Issue: "No module named 'langchain.text_splitter'"
**Solution:** Install `langchain-text-splitters` package

### Issue: "No module named 'langchain.schema'"
**Solution:** Use `langchain_core.documents` and `langchain_core.messages` instead

### Issue: "No module named 'langchain.chains'"
**Solution:** LLMChain is deprecated in LangChain v1.0+. Code has been updated to use direct LLM calls instead.

### Issue: Container has old dependencies
**Solution:** Rebuild the container with `docker-compose build ocr-worker`

## Prevention

1. Always test imports after LangChain version updates
2. Use the test script in CI/CD pipelines
3. Pin specific versions in requirements.txt
4. Monitor LangChain release notes for breaking changes