# Invoice PDF AI Configuration Priority System

## Overview

The Invoice PDF upload feature uses an intelligent priority system to automatically select the best available AI configuration for processing uploaded PDF invoices. This ensures the system works out-of-the-box while providing flexibility for advanced configuration.

## Priority System

The system checks for AI configuration in the following order:

### 1. **AI Configuration (Database)** - Highest Priority
- **Source**: Settings → AI Configuration in web interface
- **Requirements**: Must be marked as `active` and `tested`
- **Best for**: Production environments with multiple users
- **UI Indicator**: Green alert with checkmark

### 2. **Environment Variables** - Medium Priority  
- **Source**: Docker environment variables or system environment
- **Requirements**: At least one LLM environment variable must be set
- **Best for**: Docker deployments and development
- **UI Indicator**: Blue alert with checkmark

### 3. **Manual Fallback** - Lowest Priority
- **Source**: Hardcoded defaults (Ollama localhost:11434)
- **Requirements**: None (automatic fallback)
- **Best for**: Local development with Ollama running
- **UI Indicator**: Yellow alert with setup note

## Environment Variables

```bash
# Model Configuration
LLM_MODEL_INVOICES=gpt-oss:latest    # Primary model for invoice processing
LLM_MODEL=gpt-4o-mini                # General LLM model
OLLAMA_MODEL=llama2:latest           # Ollama-specific model

# API Configuration
LLM_API_BASE=http://host.docker.internal:11434      # Primary API endpoint
OLLAMA_API_BASE=http://localhost:11434              # Ollama-specific endpoint
LLM_API_KEY=sk-your-openai-key                      # OpenAI API key
OPENAI_API_KEY=sk-your-openai-key                   # Alternative OpenAI key
```

## How It Works

### PDF Upload Process

1. **User uploads PDF** via web interface
2. **System checks priority order**:
   - Database AI config → Environment variables → Manual fallback
3. **UI shows status** with appropriate color-coded alert
4. **PDF is processed** using selected configuration
5. **Results returned** with extracted invoice data

### Configuration Detection

```python
# Priority logic (simplified)
if ai_config_in_database and ai_config.tested:
    use_database_config()
elif environment_variables_set:
    use_environment_config()
else:
    use_manual_fallback()
```

## User Experience

### Status Indicators

| Config Source | Alert Color | Message | Action Required |
|---------------|-------------|---------|-----------------|
| Database | 🟢 Green | "AI configuration from database ✓" | None |
| Environment | 🔵 Blue | "AI configuration from environment variables ✓" | None |
| Manual | 🟡 Yellow | "Manual fallback (Requires Ollama setup)" | Install Ollama |

### Processing Messages

- **Database**: "Using database AI configuration for PDF processing..."
- **Environment**: "Using environment AI configuration for PDF processing..."
- **Manual**: "Using fallback AI configuration for PDF processing..."

## Docker Configuration

The system is pre-configured with environment variables in `docker-compose.yml`:

```yaml
environment:
  - LLM_API_BASE=http://host.docker.internal:11434
  - OLLAMA_API_BASE=http://host.docker.internal:11434
  - LLM_MODEL_INVOICES=gpt-oss:latest
  - LLM_MODEL_BANK_STATEMENTS=gpt-oss:latest
  - LLM_MODEL_EXPENSES=llama3.2-vision:11b
```

## Benefits

### For Users
- **Works out-of-the-box** with Docker setup
- **No configuration required** for basic usage
- **Clear status indicators** show which config is active
- **Flexible upgrade path** from environment to database config

### For Developers
- **Graceful degradation** ensures system always works
- **Environment-specific configs** for dev/staging/prod
- **Easy testing** with multiple configuration sources
- **Comprehensive error handling** with helpful messages

## Testing

Verify the priority system:

```bash
# Test in Docker container
docker-compose exec api python scripts/test_pdf_priority_in_container.py

# Expected output: "Config Source: env_vars" (with Docker setup)
```

## Troubleshooting

### Common Issues

1. **"Manual fallback" when environment variables are set**
   - Check environment variables are properly set in container
   - Restart Docker services: `docker-compose restart api`

2. **"Cannot connect to Ollama server"**
   - Ensure Ollama is running on host machine
   - Check `host.docker.internal` is accessible from container

3. **"Model not found"**
   - Pull the model: `ollama pull gpt-oss:latest`
   - Verify model name matches environment variable

## API Endpoint

Check current AI status:

```bash
GET /api/v1/invoices/ai-status

Response:
{
  "configured": true,
  "config_source": "env_vars",
  "message": "AI configuration from environment variables"
}
```

This priority system ensures reliable PDF processing while providing flexibility for different deployment scenarios.