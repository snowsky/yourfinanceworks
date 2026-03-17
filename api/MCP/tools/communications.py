"""
Communications-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TestEmailArgs(BaseModel):
    test_email: str = Field(description="Email address to send test email to")


class CommunicationsToolsMixin:
    async def test_email_configuration(self, test_email: str) -> Dict[str, Any]:
        """Test email configuration"""
        try:
            result = await self.api_client.test_email_configuration(test_email)

            return {
                "success": True,
                "data": result,
                "message": "Email test completed"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to test email configuration: {e}"}
