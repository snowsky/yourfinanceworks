import asyncio
import aiohttp
import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

class ExternalAnalyticsService:
    def __init__(self):
        self.google_analytics_id = os.getenv("GOOGLE_ANALYTICS_ID")
        self.mixpanel_token = os.getenv("MIXPANEL_TOKEN")
        self.custom_webhook_url = os.getenv("ANALYTICS_WEBHOOK_URL")
        self.custom_api_key = os.getenv("ANALYTICS_API_KEY")
        self.posthog_api_key = os.getenv("POSTHOG_API_KEY")
        self.posthog_host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
        self.amplitude_api_key = os.getenv("AMPLITUDE_API_KEY")
    
    async def send_event(self, event_data: Dict[str, Any]):
        """Send event to all configured analytics services"""
        tasks = []
        
        if self.google_analytics_id:
            tasks.append(self._send_to_google_analytics(event_data))
        
        if self.mixpanel_token:
            tasks.append(self._send_to_mixpanel(event_data))
        
        if self.custom_webhook_url:
            tasks.append(self._send_to_custom_webhook(event_data))
        
        if self.posthog_api_key:
            tasks.append(self._send_to_posthog(event_data))
        
        if self.amplitude_api_key:
            tasks.append(self._send_to_amplitude(event_data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_google_analytics(self, event_data: Dict[str, Any]):
        """Send event to Google Analytics 4"""
        try:
            url = f"https://www.google-analytics.com/mp/collect?measurement_id={self.google_analytics_id}&api_secret={os.getenv('GA_API_SECRET')}"
            
            payload = {
                "client_id": str(hash(event_data.get("user_email", "anonymous"))),
                "events": [{
                    "name": "page_view",
                    "params": {
                        "page_location": event_data.get("path"),
                        "page_title": event_data.get("path"),
                        "user_id": event_data.get("user_email"),
                        "tenant_id": str(event_data.get("tenant_id")),
                        "response_time": event_data.get("response_time_ms")
                    }
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 204:
                        logger.debug("Successfully sent to Google Analytics")
                    else:
                        logger.warning(f"GA response: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send to Google Analytics: {e}")
    
    async def _send_to_mixpanel(self, event_data: Dict[str, Any]):
        """Send event to Mixpanel"""
        try:
            url = "https://api.mixpanel.com/track"
            
            payload = {
                "event": "Page View",
                "properties": {
                    "token": self.mixpanel_token,
                    "distinct_id": event_data.get("user_email"),
                    "path": event_data.get("path"),
                    "method": event_data.get("method"),
                    "tenant_id": event_data.get("tenant_id"),
                    "response_time_ms": event_data.get("response_time_ms"),
                    "status_code": event_data.get("status_code"),
                    "time": int(datetime.utcnow().timestamp())
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Successfully sent to Mixpanel")
                    else:
                        logger.warning(f"Mixpanel response: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send to Mixpanel: {e}")
    
    async def _send_to_custom_webhook(self, event_data: Dict[str, Any]):
        """Send event to custom webhook/API"""
        try:
            headers = {"Content-Type": "application/json"}
            if self.custom_api_key:
                headers["Authorization"] = f"Bearer {self.custom_api_key}"
            
            payload = {
                "event_type": "page_view",
                "timestamp": datetime.utcnow().isoformat(),
                "data": event_data
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.custom_webhook_url, json=payload, headers=headers) as response:
                    if response.status in [200, 201, 204]:
                        logger.debug("Successfully sent to custom webhook")
                    else:
                        logger.warning(f"Custom webhook response: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send to custom webhook: {e}")
    
    async def _send_to_posthog(self, event_data: Dict[str, Any]):
        """Send event to PostHog"""
        try:
            url = f"{self.posthog_host}/capture/"
            
            payload = {
                "api_key": self.posthog_api_key,
                "event": "page_view",
                "distinct_id": event_data.get("user_email"),
                "properties": {
                    "path": event_data.get("path"),
                    "method": event_data.get("method"),
                    "tenant_id": event_data.get("tenant_id"),
                    "response_time_ms": event_data.get("response_time_ms"),
                    "status_code": event_data.get("status_code")
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Successfully sent to PostHog")
                    else:
                        logger.warning(f"PostHog response: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send to PostHog: {e}")
    
    async def _send_to_amplitude(self, event_data: Dict[str, Any]):
        """Send event to Amplitude"""
        try:
            url = "https://api2.amplitude.com/2/httpapi"
            
            payload = {
                "api_key": self.amplitude_api_key,
                "events": [{
                    "user_id": event_data.get("user_email"),
                    "event_type": "Page View",
                    "event_properties": {
                        "path": event_data.get("path"),
                        "method": event_data.get("method"),
                        "tenant_id": event_data.get("tenant_id"),
                        "response_time_ms": event_data.get("response_time_ms"),
                        "status_code": event_data.get("status_code")
                    },
                    "time": int(datetime.utcnow().timestamp() * 1000)
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Successfully sent to Amplitude")
                    else:
                        logger.warning(f"Amplitude response: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send to Amplitude: {e}")

external_analytics = ExternalAnalyticsService()