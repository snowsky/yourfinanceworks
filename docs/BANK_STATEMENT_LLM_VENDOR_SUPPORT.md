# Bank Statement Service - LLM Vendor Support Roadmap

## Current State

The `BankTransactionExtractor` class in `api/services/bank_statement_service.py` has been refactored to follow `test-main.py` patterns but is currently **Ollama-only**. The service is production-ready for Ollama deployments but lacks support for other LLM vendors.

## TODO: Multi-Vendor LLM Support

### Problem Statement
The bank statement service is currently tightly coupled to Ollama, limiting deployment flexibility and vendor choice. Enterprise customers may require different LLM providers based on:
- Cost considerations
- Latency requirements  
- Compliance needs
- Regional availability
- Existing vendor relationships

### Required LLM Vendors

#### High Priority
- **OpenAI** (GPT-3.5, GPT-4, GPT-4 Turbo)
- **Anthropic** (Claude 3, Claude 3.5)
- **Azure OpenAI** (Enterprise GPT models)

#### Medium Priority
- **Google PaLM/Gemini** (Vertex AI)
- **AWS Bedrock** (Claude, Titan, Llama via Bedrock)
- **Cohere** (Command models)

#### Low Priority
- **Hugging Face** (Hosted inference)
- **Together AI** (Open source models)
- **Replicate** (Various models)

### Proposed Architecture

#### 1. LLM Provider Abstraction Layer

```python
class LLMProvider(ABC):
    @abstractmethod
    def extract_transactions(self, text: str) -> List[Dict]:
        pass
    
    @abstractmethod
    def categorize_transactions(self, descriptions: List[str]) -> List[str]:
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        pass
```

#### 2. Provider Implementations

```python
class OllamaProvider(LLMProvider):
    # Current implementation
    
class OpenAIProvider(LLMProvider):
    # GPT-based implementation
    
class AnthropicProvider(LLMProvider):
    # Claude-based implementation
    
class AzureOpenAIProvider(LLMProvider):
    # Azure OpenAI implementation
```

#### 3. Provider Factory

```python
class LLMProviderFactory:
    @staticmethod
    def create_provider(provider_config: Dict) -> LLMProvider:
        provider_type = provider_config.get("type")
        if provider_type == "ollama":
            return OllamaProvider(provider_config)
        elif provider_type == "openai":
            return OpenAIProvider(provider_config)
        # ... etc
```

#### 4. Unified Configuration

```python
llm_config = {
    "type": "openai",  # or "ollama", "anthropic", etc.
    "model": "gpt-4",
    "api_key": "...",
    "base_url": "...",  # optional
    "temperature": 0.1,
    "max_tokens": 1500,
    "timeout": 120
}
```

### Implementation Considerations

#### Authentication & Security
- **API Keys**: Secure storage and rotation
- **OAuth**: For enterprise providers
- **Role-based access**: Different models for different users
- **Rate limiting**: Provider-specific limits

#### Cost Management
- **Token counting**: Accurate billing across providers
- **Cost optimization**: Automatic model selection based on budget
- **Usage monitoring**: Track costs per provider/model

#### Performance Optimization
- **Caching**: Provider-agnostic response caching
- **Batch processing**: Optimize for provider-specific batch APIs
- **Fallback chains**: Primary → Secondary → Tertiary providers
- **Load balancing**: Distribute requests across providers

#### Error Handling
- **Provider failures**: Graceful degradation
- **Rate limiting**: Backoff and retry strategies
- **Model unavailability**: Automatic fallback to alternative models
- **Partial failures**: Handle batch processing errors

### Migration Strategy

#### Phase 1: Abstraction Layer
1. Create base `LLMProvider` interface
2. Refactor `BankTransactionExtractor` to use provider abstraction
3. Implement `OllamaProvider` (existing functionality)
4. Add provider configuration system

#### Phase 2: Core Providers
1. Implement `OpenAIProvider`
2. Implement `AnthropicProvider`
3. Implement `AzureOpenAIProvider`
4. Add comprehensive testing for each provider

#### Phase 3: Advanced Features
1. Add fallback provider chains
2. Implement cost tracking and optimization
3. Add performance monitoring and analytics
4. Implement smart model selection

#### Phase 4: Enterprise Features
1. Add role-based provider access
2. Implement advanced caching strategies
3. Add batch processing optimizations
4. Enterprise security compliance

### Testing Requirements

#### Unit Tests
- Provider interface compliance
- Authentication mechanisms
- Error handling scenarios
- Configuration validation

#### Integration Tests
- End-to-end extraction with each provider
- Fallback chain functionality
- Performance benchmarking
- Cost tracking accuracy

#### Load Tests
- Provider rate limit handling
- Concurrent request processing
- Failover scenarios
- Performance under load

### Configuration Examples

#### Environment Variables
```bash
# Primary provider
LLM_PROVIDER_TYPE=openai
LLM_PROVIDER_MODEL=gpt-4
LLM_PROVIDER_API_KEY=sk-...

# Fallback provider
LLM_FALLBACK_PROVIDER_TYPE=ollama
LLM_FALLBACK_PROVIDER_MODEL=llama2:7b
LLM_FALLBACK_PROVIDER_BASE_URL=http://localhost:11434
```

#### Configuration File
```yaml
llm_providers:
  primary:
    type: openai
    model: gpt-4
    api_key: ${OPENAI_API_KEY}
    temperature: 0.1
    max_tokens: 1500
  
  fallback:
    type: ollama
    model: llama2:7b
    base_url: http://localhost:11434
    temperature: 0.1
    max_tokens: 1500
  
  cost_limits:
    daily_budget: 100.00
    per_request_max: 0.50
```

### Success Metrics

#### Functionality
- ✅ Support for 5+ LLM providers
- ✅ Seamless fallback between providers
- ✅ Configuration-driven provider selection

#### Performance
- ✅ <5% performance overhead from abstraction
- ✅ 99.9% uptime with fallback providers
- ✅ Cost reduction through smart provider selection

#### Developer Experience
- ✅ Simple provider configuration
- ✅ Comprehensive documentation
- ✅ Easy testing and debugging

### Timeline Estimate

- **Phase 1**: 2-3 weeks (Abstraction layer)
- **Phase 2**: 3-4 weeks (Core providers)
- **Phase 3**: 2-3 weeks (Advanced features)
- **Phase 4**: 3-4 weeks (Enterprise features)

**Total**: 10-14 weeks for complete implementation

### Related Files

- `api/services/bank_statement_service.py` - Current implementation
- `test-main.py` - Reference patterns
- `api/routers/settings.py` - Configuration management
- `docs/` - Additional documentation

---

**Status**: TODO - Not yet implemented
**Priority**: High
**Complexity**: Medium-High
**Dependencies**: LangChain provider support, configuration system
