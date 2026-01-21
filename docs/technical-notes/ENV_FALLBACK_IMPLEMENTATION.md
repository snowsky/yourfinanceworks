# 🔄 Environment Variable Fallback for AI Configuration

## 🎯 **Problem Solved**
When no AI configuration is found in the database (or database access fails), the system now automatically falls back to environment variables for AI/LLM configuration.

## ✅ **Implementation Details**

### **1. New Function: `_get_ai_config_from_env()`**
```python
def _get_ai_config_from_env() -> Optional[Dict[str, Any]]:
    """Get AI configuration from environment variables as fallback"""
```

**Supported Environment Variables:**
- `LLM_API_BASE` / `OLLAMA_API_BASE` - API endpoint URL
- `LLM_API_KEY` - API key for authenticated providers
- `LLM_MODEL_EXPENSES` / `OLLAMA_MODEL` - Model name to use
- `LOG_LEVEL` - Logging level (existing)

### **2. Provider Auto-Detection**
The system automatically detects the AI provider based on environment variables:

| Provider | Detection Logic | Default Model |
|----------|----------------|---------------|
| **Ollama** | `OLLAMA_*` vars or localhost:11434 | `llama3.2-vision:11b` |
| **OpenAI** | `api.openai.com` in URL or just API key | `gpt-4-vision-preview` |
| **OpenRouter** | `openrouter.ai` in URL | `openai/gpt-4-vision-preview` |
| **Anthropic** | `anthropic` in URL | `claude-3-haiku` |
| **Google** | `google` in URL | `gemini-pro-vision` |

### **3. Fallback Triggers**
Environment variable fallback is triggered when:

1. **No Database Config Found**
   ```
   No active AI config found in database → Check environment variables
   ```

2. **No OCR-Enabled Config**
   ```
   Active config exists but OCR disabled → Check environment variables
   ```

3. **Database Access Fails**
   ```
   Database error (encryption, connection, etc.) → Check environment variables
   ```

4. **AI LLM Retry Scenarios**
   ```
   Heuristic parsing fails + no DB config → Use environment config for retry
   ```

### **4. Configuration Priority**
```
1. Database AI Config (OCR-enabled) ← Highest Priority
2. Environment Variables ← Fallback
3. No AI Processing ← Last Resort
```

## 🔧 **Environment Variable Examples**

### **Ollama Setup (Local)**
```bash
export OLLAMA_API_BASE="http://localhost:11434"
export OLLAMA_MODEL="llama3.2-vision:11b"
```

### **OpenAI Setup**
```bash
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_API_KEY="sk-your-openai-key"
export LLM_MODEL_EXPENSES="gpt-4-vision-preview"
```

### **OpenRouter Setup**
```bash
export LLM_API_BASE="https://openrouter.ai/api/v1"
export LLM_API_KEY="sk-or-your-key"
export LLM_MODEL_EXPENSES="openai/gpt-4-vision-preview"
```

### **Anthropic Setup**
```bash
export LLM_API_BASE="https://api.anthropic.com"
export LLM_API_KEY="sk-ant-your-key"
export LLM_MODEL_EXPENSES="claude-3-haiku"
```

### **Minimal Setup (Ollama)**
```bash
# Just the model - system will use defaults
export OLLAMA_MODEL="llama3.2-vision:11b"
# API base defaults to http://localhost:11434
```

## 🚀 **Benefits**

### **1. Zero-Configuration OCR**
- Works out of the box with just environment variables
- No need to configure AI settings in the database first
- Perfect for development and testing

### **2. Robust Fallback**
- System continues working even if database AI config is broken
- Graceful degradation when database is unavailable
- Automatic retry with environment config

### **3. Flexible Deployment**
- Easy Docker/container deployment with env vars
- CI/CD friendly configuration
- No database setup required for basic OCR functionality

### **4. Development Friendly**
- Quick setup for local development
- Easy switching between different AI providers
- No UI configuration needed

## 🧪 **Testing the Implementation**

### **Test 1: Environment Fallback Function**
```bash
# In API container
python test_env_fallback.py
```

### **Test 2: Integration Test**
```bash
# Set environment variables
export OLLAMA_MODEL="llama3.2-vision:11b"

# Upload a receipt - should use environment config
# Check logs for: "Using AI config from environment variables"
```

### **Test 3: Database + Environment Priority**
```bash
# 1. Configure AI in database (higher priority)
# 2. Set environment variables (lower priority)  
# 3. Upload receipt - should use database config
# 4. Disable database config - should fall back to environment
```

## 📊 **Logging Output**

### **Successful Environment Fallback:**
```
INFO: No active AI config found in database, falling back to environment variables
INFO: Using AI config from environment variables: ollama/llama3.2-vision:11b
INFO: ✅ Unified OCR extraction successful: 5 fields extracted in 2.3s using ai_vision
```

### **No Configuration Available:**
```
WARNING: No AI configuration available from database or environment variables
INFO: Heuristic parsing returned no data, AI LLM extraction would be recommended
```

### **AI LLM Retry with Environment:**
```
INFO: 🔄 Retrying with AI LLM due to failed heuristic parsing...
INFO: Using environment AI config for retry: ollama/llama3.2-vision:11b
INFO: ✅ AI LLM retry successful, using AI results
```

## 🔄 **Complete Processing Flow**

```
📄 Receipt Upload
    ↓
🔍 Check Database for AI Config
    ↓
❌ No Config Found?
    ↓
🌍 Check Environment Variables
    ↓
✅ Environment Config Found?
    ↓
🤖 Use Environment Config for OCR
    ↓
📊 Process Receipt with AI LLM
    ↓
⚠️ Heuristic Parsing Fails?
    ↓
🔄 Retry with Environment Config
    ↓
✅ Store Results with Timestamp
```

## 🎯 **Real-World Scenarios**

### **Scenario 1: Fresh Installation**
- No AI config in database yet
- Environment variables set for Ollama
- **Result**: OCR works immediately using environment config

### **Scenario 2: Database Issues**
- Database encryption key changed
- AI config fetch fails
- Environment variables available
- **Result**: Automatic fallback to environment config

### **Scenario 3: Development Setup**
- Developer sets `OLLAMA_MODEL` in `.env`
- No database configuration needed
- **Result**: Instant OCR functionality for testing

### **Scenario 4: Production Deployment**
- Database has primary AI config
- Environment has backup config
- Database config fails temporarily
- **Result**: Seamless fallback to environment config

## ✅ **Summary**

The environment variable fallback ensures that:

1. **🔧 OCR always works** when properly configured
2. **🛡️ System is resilient** to database issues  
3. **⚡ Setup is simple** for development
4. **🔄 Fallback is automatic** and transparent
5. **📝 Logging is clear** about which config is used

Users now have **multiple ways to configure AI** for timestamp extraction, with intelligent fallback ensuring the system keeps working even when the primary configuration method fails! 🎉