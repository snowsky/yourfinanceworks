
import sys
import os
import logging
from unittest.mock import MagicMock

# Add API directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commercial.prompt_management.services.prompt_service import PromptService
from commercial.prompt_management.models.prompt_templates import PromptTemplate
from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fallback_mechanism():
    """Test that PromptService falls back to default constants when DB template is missing."""
    
    # Create a mock session that returns None for queries
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    service = PromptService(mock_session)
    
    # Test case: Request a known default template (that is missing from DB)
    template_name = "invoice_processing"
    logger.info(f"Testing fallback for '{template_name}'...")
    
    # We expect this to SUCCEED by finding the default definition, 
    # instead of failing or using the fallback string
    try:
        # Pass a fallback string to verify it is NOT used when default exists
        prompt = service.get_prompt(
            name=template_name,
            variables={"invoice_text": "Sample Invoice"},
            fallback_prompt="This is the fallback string fallback."
        )
        
        # Verify result content matches the default template, not the fallback string
        default_def = next(t for t in DEFAULT_PROMPT_TEMPLATES if t["name"] == template_name)
        
        # Simple check - the prompt should contain parts of the default template content
        if "You are an AI assistant specialized in extracting structured data" in prompt:
            logger.info("✅ SUCCESS: Service used default template definition as fallback")
            return True
        elif "This is the fallback string fallback" in prompt:
            logger.error("❌ FAILURE: Service used the provided fallback string instead of default definition")
            return False
        else:
            logger.error(f"❌ FAILURE: Unrecognized output. Prompt content:\n{prompt}")
            return False

    except ValueError as e:
        logger.error(f"❌ FAILURE: Service raised ValueError: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ FAILURE: Unexpected error: {e}")
        return False

def test_unknown_template():
    """Test behavior for unknown template with no default."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    service = PromptService(mock_session)
    
    unknown_name = "non_existent_template_xyz"
    logger.info(f"Testing fallback for unknown '{unknown_name}'...")
    
    try:
        fallback = "Fallback string used"
        prompt = service.get_prompt(name=unknown_name, fallback_prompt=fallback)
        
        if prompt == fallback:
            logger.info("✅ SUCCESS: Service correctly used fallback string for unknown template")
            return True
            # Continue with the next test within this function
        else:
            logger.error(f"❌ FAILURE: Expected fallback string, got: {prompt}")
            return False
            
    except Exception as e:
        logger.error(f"❌ FAILURE: Unexpected error: {e}")
        return False

    logger.info("\n✅ Validated unknown prompt fallbacks")

    # 4. Test list_default_prompts
    logger.info("\nTesting list_default_prompts...")
    defaults = service.list_default_prompts()
    
    if not defaults:
        logger.error("❌ list_default_prompts returned empty list")
        return False
        
    logger.info(f"Found {len(defaults)} default prompts")
    
    # Check if invoice_processing is in the list
    invoice_prompt = next((p for p in defaults if p.name == "invoice_processing"), None)
    if not invoice_prompt:
        logger.error("❌ 'invoice_processing' not found in default prompts")
        return False
        
    if invoice_prompt.id >= 0:
         logger.error(f"❌ Expected negative ID for virtual default prompt, got {invoice_prompt.id}")
         return False

    logger.info("✅ Validated list_default_prompts returns constants with negative IDs")
    return True # All tests within this function passed

if __name__ == "__main__":
    if test_fallback_mechanism() and test_unknown_template():
        logger.info("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error("\n💥 Some tests failed.")
        sys.exit(1)
