#!/usr/bin/env python3
"""
Test script for AI model name formatting
"""

def test_model_formatting():
    """Test model name formatting for different providers"""
    
    test_cases = [
        # (provider, input_model, expected_output)
        ("openai", "gpt-4", "gpt-4"),
        ("openai", "gpt-3.5-turbo", "gpt-3.5-turbo"),
        ("ollama", "llama2", "ollama/llama2"),
        ("ollama", "llama3.1:8b", "ollama/llama3.1:8b"),
        ("anthropic", "claude-3-sonnet", "claude-3-sonnet"),
        ("google", "gemini-pro", "gemini-pro"),
        ("custom", "my-model", "my-model"),
    ]
    
    print("🧪 Testing model name formatting...")
    
    for provider, input_model, expected in test_cases:
        # Simulate the formatting logic from the router
        model_name = input_model
        
        if provider == "ollama":
            # For Ollama, prefix with ollama/
            formatted_model = f"ollama/{model_name}"
        elif provider == "openai":
            # For OpenAI, use as-is (LiteLLM recognizes OpenAI models)
            formatted_model = model_name
        elif provider == "anthropic":
            # For Anthropic, use as-is (LiteLLM recognizes Anthropic models)
            formatted_model = model_name
        elif provider == "google":
            # For Google, use as-is (LiteLLM recognizes Google models)
            formatted_model = model_name
        elif provider == "custom":
            # For custom providers, use the model name as-is
            formatted_model = model_name
        else:
            formatted_model = model_name
        
        status = "✅" if formatted_model == expected else "❌"
        print(f"{status} {provider}: '{input_model}' -> '{formatted_model}' (expected: '{expected}')")
        
        if formatted_model != expected:
            print(f"   ⚠️  Mismatch for {provider}")

if __name__ == "__main__":
    test_model_formatting()
    print("\n🎉 Model formatting test completed!") 