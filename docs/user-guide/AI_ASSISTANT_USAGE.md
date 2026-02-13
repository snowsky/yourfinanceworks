# AI Assistant Usage

## Overview

The AI assistant provides intelligent business insights using your actual data through the Model Context Protocol (MCP). It also answers general questions using the configured LLM provider.

## Business Analysis Queries

Try questions like:

- **"Can you analyze my invoice patterns and trends?"**
- **"What actions should I take based on my invoice data?"**
- **"Show me all my clients"**
- **"Search for clients named John"**
- **"Show me all my invoices"**
- **"Find invoices for client ABC"**
- **"Show me all payments"**
- **"Who owes me money?"**
- **"Show me overdue invoices"**
- **"How many invoices do I have?"**

## General Questions

General prompts use the LLM provider directly:

- **"What is the weather like today?"**
- **"Explain invoice terms"**
- **"How do I create a professional invoice?"**

## AI Configuration

1. **Navigate to Settings** -> **AI Configuration** tab
2. **Configure AI Provider** - Set up OpenAI, Ollama, or other providers
3. **Set as Default** - Mark your preferred provider as default
4. **Test Configuration** - Verify your AI setup works correctly

The AI assistant automatically detects the type of query and routes it to MCP (business data) or the LLM (general questions).

## Local AI with Ollama (Optional)

If you want to run AI features locally without cloud API costs:

```bash
# Start Ollama server with optimized settings
OLLAMA_CONTEXT_LENGTH=64000 OLLAMA_HOST=0.0.0.0 OLLAMA_NUM_PARALLEL=2 ollama serve &

# Pull required models
ollama pull llama3.2-vision:11b  # For OCR and expense processing
ollama pull gpt-oss:latest       # For invoice and bank statement processing
```

When using Docker Compose, Ollama should be running on your **host machine** (not in a container). The application connects via `host.docker.internal:11434`.
