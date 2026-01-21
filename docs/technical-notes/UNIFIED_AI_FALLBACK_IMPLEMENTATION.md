# 🤖 Unified AI Fallback Implementation

## 🎯 **Overview**

This document describes the unified AI fallback implementation that consolidates environment variable configurations across all application components (AI chat, expense OCR, bank statement processing, and invoice processing).

## ✅ **Unified Implementation**

### **1. Centralized AI Configuration Service**

**File**: `api/services/ai_config_service.py`

The `AIConfigService` provides a centralized way to manage AI configurations with intelligent fallback from database to environment variables.

**Key Features**:
- Component-specific environment variable mappings
- Automatic provider detection
- Intelligent fallback hierarchy
- Configuration validation
- Support for multiple AI providers

### **2. Component-Specific Environment Variables**

#### **OCR/Expense Processing**
```bash
# Primary variables
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_API_KEY="sk-your-api-key"
export LLM_MODEL_EXPENSES="gpt-4-vision-preview"

# Ollama alternatives
export OLLAMA_API_BASE="http://localhost:11434"
export OLLAMA_MODEL="llama3.2-vision:11b"
```

#### **AI Chat**
```bash
export AI_PROVIDER="openai"
export AI_MODEL="gpt-4"
export AI_API_KEY="sk-your-api-key"
export AI_API_URL="https://api.openai.com/v1"
```

#### **Bank Statement Processing**
```bash
# Specific bank statement variables (highest priority)
export LLM_API_BASE_BANK="https://api.openai.com/v1"
export LLM_API_KEY_BANK="sk-your-bank-api-key"
export LLM_MODEL_BANK_STATEMENTS="gpt-4-vision-preview"

# Fallback to general variables
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_API_KEY="sk-your-api-key"
export LLM_MODEL_EXPENSES="gpt-4-vision-preview"
```

#### **Invoice Processing**
```bash
# Specific invoice variables (highest priority)
export LLM_API_BASE_INVOICE="https://api.openai.com/v1"
export LLM_API_KEY_INVOICE="sk-your-invoice-api-key"
export LLM_MODEL_INVOICES="gpt-4-vision-preview"

# Fallback to general variables
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_API_KEY="sk-your-api-key"
export LLM_MODEL_EXPENSES="gpt-4-vision-preview"
```

### **3. Provider Support Matrix**

| Provider | Environment Variables | Default Model | Default API Base |
|----------|----------------------|---------------|------------------|
| **Ollama** | `OLLAMA_API_BASE`, `OLLAMA_MODEL` | `llama3.2-vision:11b` | `http://localhost:11434` |
| **OpenAI** | `LLM_API_BASE`, `LLM_API_KEY` | `gpt-4-vision-preview` | `https://api.openai.com/v1` |
| **Anthropic** | `LLM_API_BASE`, `LLM_API_KEY` | `claude-3-haiku` | `https://api.anthropic.com` |
| **Google** | `LLM_API_BASE`, `LLM_API_KEY` | `gemini-pro-vision` | `https://generativelanguage.googleapis.com/v1beta` |
| **OpenRouter** | `LLM_API_BASE`, `LLM_API_KEY` | `openai/gpt-4-vision-preview` | `https://openrouter.ai/api/v1` |

### **4. Fallback Hierarchy**

```
1. Database AI Config (Component-specific OCR settings) ← Highest Priority
2. Database AI Config (General active configuration)
3. Component-specific Environment Variables
4. General Environment Variables ← Fallback
5. No AI Processing ← Last Resort
```

## 🔧 **Usage Examples**

### **Getting AI Configuration for Any Component**

```python
from services.ai_config_service import AIConfigService

# For OCR/Expense processing
config = AIConfigService.get_ai_config(db, component="ocr", require_ocr=True)

# For AI Chat
config = AIConfigService.get_ai_config(db, component="chat", require_ocr=False)

# For Bank Statement processing
config = AIConfigService.get_ai_config(db, component="bank_statement", require_ocr=True)

# For Invoice processing
config = AIConfigService.get_ai_config(db, component="invoice", require_ocr=True)
```

### **Component-Specific Services**

#### **Expense OCR (Updated)**
```python
from services.ocr_service import process_attachment_inline
from services.ai_config_service import AIConfigService

# Automatically uses unified configuration
ai_config = AIConfigService.get_ai_config(db, "ocr", require_ocr=True)
await process_attachment_inline(db, expense_id, attachment_id, file_path)
```

#### **AI Chat (Updated)**
```python
from routers.ai import ai_chat
from services.ai_config_service import AIConfigService

# Automatically uses unified configuration with chat-specific variables
response = await ai_chat(request, db, current_user)
```

#### **Bank Statement Processing (Enhanced)**
```python
from services.bank_statement_ocr_processor import BankStatementOCRProcessor

# Now supports AI config fallback
processor = BankStatementOCRProcessor(db_session=db)
effective_config = processor.get_effective_ai_config()
text = processor.extract_with_ocr(pdf_path)
```

#### **Invoice Processing (New)**
```python
from services.invoice_ai_service import InvoiceAIService

# New service with unified AI configuration
service = InvoiceAIService(db)
result = await service.extract_invoice_data(file_path)
```

## 🚀 **Benefits of Unified Implementation**

### **1. Consistency Across Components**
- All components use the same configuration logic
- Consistent environment variable naming patterns
- Unified provider detection and defaults

### **2. Flexible Configuration**
- Component-specific variables for fine-grained control
- Intelligent fallback to general variables
- Support for mixed provider setups

### **3. Enhanced Reliability**
- Robust error handling and fallback mechanisms
- Configuration validation
- Comprehensive logging

### **4. Simplified Deployment**
- Single configuration service to manage
- Clear environment variable hierarchy
- Easy Docker/container deployment

### **5. Better Monitoring**
- Centralized usage tracking
- Component-specific metrics
- Configuration source tracking

## 🧪 **Testing the Implementation**

### **Test 1: Component-Specific Configuration**
```bash
# Set component-specific variables
export LLM_MODEL_BANK_STATEMENTS="claude-3-haiku"
export LLM_MODEL_INVOICES="gpt-4-vision-preview"
export LLM_MODEL_EXPENSES="llama3.2-vision:11b"

# Each component should use its specific model
```

### **Test 2: Fallback Hierarchy**
```bash
# Set only general variables
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_API_KEY="sk-test-key"

# All components should fall back to general configuration
```

### **Test 3: Mixed Provider Setup**
```bash
# Different providers for different components
export AI_PROVIDER="openai"  # Chat uses OpenAI
export OLLAMA_MODEL="llama3.2-vision:11b"  # OCR uses Ollama
export LLM_API_BASE_BANK="https://api.anthropic.com"  # Bank statements use Anthropic
```

## 📊 **Configuration Validation**

The unified service includes configuration validation:

```python
from services.ai_config_service import AIConfigService

config = AIConfigService.get_ai_config(db, "ocr")
validation = AIConfigService.validate_config(config)

if not validation["valid"]:
    print("Configuration errors:", validation["errors"])
if validation["warnings"]:
    print("Configuration warnings:", validation["warnings"])
```

## 🔄 **Migration from Legacy Implementation**

### **Backward Compatibility**
- Legacy `_get_ai_config_from_env()` function maintained
- Existing environment variables continue to work
- Gradual migration path for existing deployments

### **Migration Steps**
1. Deploy unified AI configuration service
2. Update components to use new service
3. Add component-specific environment variables as needed
4. Validate configuration across all components
5. Remove legacy fallback functions (optional)

## 📝 **Environment Variable Reference**

### **Complete Environment Variable List**

```bash
# === AI Chat Configuration ===
AI_PROVIDER=openai                    # Provider name
AI_MODEL=gpt-4                       # Model name
AI_API_KEY=sk-your-key               # API key
AI_API_URL=https://api.openai.com/v1 # API URL

# === OCR/Expense Configuration ===
LLM_API_BASE=https://api.openai.com/v1  # API base URL
LLM_API_KEY=sk-your-key                 # API key
LLM_MODEL_EXPENSES=gpt-4-vision-preview # Model for expenses

# === Ollama Configuration ===
OLLAMA_API_BASE=http://localhost:11434  # Ollama API base
OLLAMA_MODEL=llama3.2-vision:11b        # Ollama model

# === Bank Statement Configuration ===
LLM_API_BASE_BANK=https://api.openai.com/v1     # Bank-specific API base
LLM_API_KEY_BANK=sk-your-bank-key               # Bank-specific API key
LLM_MODEL_BANK_STATEMENTS=gpt-4-vision-preview  # Bank-specific model

# === Invoice Configuration ===
LLM_API_BASE_INVOICE=https://api.openai.com/v1    # Invoice-specific API base
LLM_API_KEY_INVOICE=sk-your-invoice-key           # Invoice-specific API key
LLM_MODEL_INVOICES=gpt-4-vision-preview           # Invoice-specific model
```

## ✅ **Summary**

The unified AI fallback implementation provides:

1. **🔧 Centralized Configuration Management** - Single service for all AI configurations
2. **🛡️ Robust Fallback Logic** - Intelligent hierarchy from database to environment variables
3. **⚡ Component Flexibility** - Component-specific variables with general fallbacks
4. **🔄 Backward Compatibility** - Existing configurations continue to work
5. **📝 Comprehensive Logging** - Clear visibility into configuration sources and usage
6. **🎯 Enhanced Reliability** - Validation, error handling, and monitoring

All components now have consistent, reliable AI configuration with intelligent fallback to environment variables, ensuring the system continues working even when database configurations are unavailable! 🎉