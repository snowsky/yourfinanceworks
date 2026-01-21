# PDF Upload AI Configuration Priority System

The PDF upload feature uses a priority system to determine which AI configuration to use for processing uploaded PDF invoices. This ensures the system works out-of-the-box while allowing for flexible configuration.

## Priority Order

The system checks for AI configuration in the following order:

### 1. AI Configuration (Database) - **Highest Priority**
- **Source**: Settings → AI Configuration in the web interface
- **Requirements**: 
  - AI config must be marked as `is_active = true`
  - AI config must be marked as `tested = true` (verified working)
- **When to use**: This is the recommended approach for production systems
- **Benefits**: 
  - User-friendly web interface
  - Configuration testing and validation
  - Per-tenant configuration in multi-tenant setups

### 2. Environment Variables - **Medium Priority**
- **Source**: Environment variables in `.env` file or system environment
- **Requirements**: At least one of the following environment variables must be set:
  - `LLM_MODEL_INVOICES`, `LLM_MODEL`, or `OLLAMA_MODEL`
  - `LLM_API_BASE` or `OLLAMA_API_BASE`
  - `LLM_API_KEY` or `OPENAI_API_KEY`
- **When to use**: Good for development, testing, or containerized deployments
- **Provider Detection Logic**:
  - If `LLM_API_BASE`/`OLLAMA_API_BASE` or `OLLAMA_MODEL` is set → Uses Ollama
  - If `LLM_API_KEY`/`OPENAI_API_KEY` is set → Uses OpenAI
  - Default fallback → Ollama

### 3. Manual Fallback - **Lowest Priority**
- **Source**: Hardcoded defaults in the application
- **Configuration**:
  - Provider: `ollama`
  - URL: `http://localhost:11434`
  - Model: `gpt-oss:latest`
  - API Key: `None`
- **When to use**: Automatic fallback when no other configuration is available
- **Limitations**: May not work without proper Ollama setup

## Environment Variables Reference

```bash
# Model Configuration
LLM_MODEL_INVOICES=gpt-4o-mini    # Specific model for invoice processing
LLM_MODEL=gpt-4o-mini             # General LLM model
OLLAMA_MODEL=gpt-oss:latest       # Ollama-specific model

# API Configuration  
LLM_API_KEY=your-openai-api-key   # OpenAI API key
OPENAI_API_KEY=your-openai-key    # Alternative OpenAI API key
LLM_API_BASE=http://localhost:11434      # Ollama API base URL
OLLAMA_API_BASE=http://localhost:11434   # Alternative Ollama API base URL
```

## Configuration Examples

### Example 1: OpenAI via Environment Variables
```bash
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-openai-api-key-here
```

### Example 2: Ollama via Environment Variables
```bash
OLLAMA_MODEL=llama2:latest
OLLAMA_API_BASE=http://localhost:11434
```

### Example 3: AI Configuration via Web Interface
1. Navigate to **Settings** → **AI Configuration**
2. Click **Add New Configuration**
3. Fill in provider details (OpenAI, Ollama, etc.)
4. Click **Test Configuration** to verify
5. Set as **Default** if test passes

## Error Handling

The system provides specific error messages based on the configuration source:

- **Manual Configuration Errors**: Suggests setting up AI configuration in Settings or environment variables
- **Environment Variable Errors**: Suggests checking LLM environment configuration or using web interface
- **AI Configuration Errors**: Suggests verifying AI settings in the web interface

## Best Practices

1. **Production**: Use AI Configuration via web interface for better management and testing
2. **Development**: Use environment variables for quick setup and testing
3. **Docker/Containers**: Use environment variables or mount configuration files
4. **Testing**: The manual fallback ensures the system works even without configuration

## Troubleshooting

### Common Issues

1. **"Cannot connect to Ollama server"**
   - Ensure Ollama is running: `ollama serve`
   - Check the API URL is correct
   - Verify firewall/network settings

2. **"Authentication failed"**
   - Verify API key is correct and active
   - Check API key permissions and quotas

3. **"Model not found"**
   - Ensure the model name is correct
   - For Ollama: Pull the model first (`ollama pull model-name`)
   - For OpenAI: Verify model availability and access

### Testing Configuration

Use the test script to verify the priority system:

```bash
cd api
python scripts/test_pdf_ai_priority.py
```

This will test all three priority levels and confirm the system is working correctly.