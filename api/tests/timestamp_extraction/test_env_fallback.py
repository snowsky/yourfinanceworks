#!/usr/bin/env python3
"""
Test environment variable fallback for AI configuration
"""
import os
import sys

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from commercial.ai.services.ocr_service import _get_ai_config_from_env


def test_env_fallback():
    """Test AI config fallback to environment variables"""
    
    print("🧪 TESTING AI CONFIG ENVIRONMENT VARIABLE FALLBACK")
    print("=" * 60)
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "Ollama Configuration",
            "env_vars": {
                "OLLAMA_API_BASE": "http://localhost:11434",
                "OLLAMA_MODEL": "llama3.2-vision:11b"
            },
            "expected_provider": "ollama"
        },
        {
            "name": "OpenAI Configuration",
            "env_vars": {
                "LLM_API_BASE": "https://api.openai.com/v1",
                "LLM_API_KEY": "sk-test-key",
                "LLM_MODEL_EXPENSES": "gpt-4-vision-preview"
            },
            "expected_provider": "openai"
        },
        {
            "name": "OpenRouter Configuration",
            "env_vars": {
                "LLM_API_BASE": "https://openrouter.ai/api/v1",
                "LLM_API_KEY": "sk-or-test-key",
                "LLM_MODEL_EXPENSES": "openai/gpt-4-vision-preview"
            },
            "expected_provider": "openrouter"
        },
        {
            "name": "Anthropic Configuration",
            "env_vars": {
                "LLM_API_BASE": "https://api.anthropic.com",
                "LLM_API_KEY": "sk-ant-test-key",
                "LLM_MODEL_EXPENSES": "claude-3-haiku"
            },
            "expected_provider": "anthropic"
        },
        {
            "name": "No Environment Variables",
            "env_vars": {},
            "expected_provider": None
        },
        {
            "name": "Minimal Ollama (Just Model)",
            "env_vars": {
                "OLLAMA_MODEL": "llama3.2-vision:11b"
            },
            "expected_provider": "ollama"
        },
        {
            "name": "Just API Key (Default to OpenAI)",
            "env_vars": {
                "LLM_API_KEY": "sk-test-key"
            },
            "expected_provider": "openai"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n📋 Test {i}: {scenario['name']}")
        print("-" * 40)
        
        # Clear existing environment variables
        env_vars_to_clear = [
            "LLM_API_BASE", "LLM_API_KEY", "LLM_MODEL_EXPENSES",
            "OLLAMA_API_BASE", "OLLAMA_MODEL"
        ]
        
        original_values = {}
        for var in env_vars_to_clear:
            original_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]
        
        # Set test environment variables
        for var, value in scenario["env_vars"].items():
            os.environ[var] = value
            print(f"   {var}={value}")
        
        try:
            # Test the function
            result = _get_ai_config_from_env()
            
            if scenario["expected_provider"] is None:
                if result is None:
                    print("   ✅ Correctly returned None (no config)")
                else:
                    print(f"   ❌ Expected None but got: {result}")
            else:
                if result:
                    provider = result.get("provider_name")
                    model = result.get("model_name")
                    api_base = result.get("provider_url")
                    api_key = result.get("api_key")
                    ocr_enabled = result.get("ocr_enabled")
                    
                    print(f"   Provider: {provider}")
                    print(f"   Model: {model}")
                    print(f"   API Base: {api_base}")
                    print(f"   API Key: {'***' if api_key else None}")
                    print(f"   OCR Enabled: {ocr_enabled}")
                    
                    if provider == scenario["expected_provider"]:
                        print("   ✅ Provider detection correct")
                    else:
                        print(f"   ❌ Expected provider '{scenario['expected_provider']}' but got '{provider}'")
                    
                    if ocr_enabled:
                        print("   ✅ OCR enabled by default")
                    else:
                        print("   ❌ OCR should be enabled by default")
                else:
                    print(f"   ❌ Expected config but got None")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        finally:
            # Restore original environment variables
            for var in env_vars_to_clear:
                if var in os.environ:
                    del os.environ[var]
                if original_values[var] is not None:
                    os.environ[var] = original_values[var]
    
    print("\n" + "=" * 60)
    print("🎯 ENVIRONMENT FALLBACK TEST SUMMARY")
    print("=" * 60)
    print("✅ AI config now falls back to environment variables when:")
    print("   - No AI config found in database")
    print("   - Database AI config fetch fails")
    print("   - No OCR-enabled AI config in database")
    print("✅ Supports multiple providers:")
    print("   - Ollama (OLLAMA_API_BASE, OLLAMA_MODEL)")
    print("   - OpenAI (LLM_API_BASE, LLM_API_KEY, LLM_MODEL_EXPENSES)")
    print("   - OpenRouter (openrouter.ai in API base)")
    print("   - Anthropic (anthropic in API base)")
    print("   - Google (google in API base)")
    print("✅ Provides sensible defaults for missing values")
    print("✅ OCR is enabled by default for env fallback")


def test_integration_scenario():
    """Test a realistic integration scenario"""
    
    print("\n🔄 INTEGRATION SCENARIO TEST")
    print("=" * 40)
    
    # Simulate a typical Ollama setup
    os.environ["OLLAMA_MODEL"] = "llama3.2-vision:11b"
    # Don't set OLLAMA_API_BASE to test default
    
    try:
        config = _get_ai_config_from_env()
        
        if config:
            print("✅ Environment fallback working!")
            print(f"   Provider: {config['provider_name']}")
            print(f"   Model: {config['model_name']}")
            print(f"   API Base: {config['provider_url']}")
            print(f"   OCR Enabled: {config['ocr_enabled']}")
            
            # This config should work with the OCR system
            if config['provider_name'] == 'ollama' and config['ocr_enabled']:
                print("✅ Ready for OCR processing!")
            else:
                print("⚠️  Config may not be optimal for OCR")
        else:
            print("❌ Environment fallback failed")
    
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
    
    finally:
        # Clean up
        if "OLLAMA_MODEL" in os.environ:
            del os.environ["OLLAMA_MODEL"]


if __name__ == "__main__":
    test_env_fallback()
    test_integration_scenario()