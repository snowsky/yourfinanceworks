# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

from fastapi import APIRouter
import os

router = APIRouter()


@router.get("/sso-status")
async def get_sso_status():
    """Get the status of available SSO providers (public endpoint)"""
    google_available = False
    azure_available = False

    # Keep status endpoint independent from commercial.sso.router import health.
    # If the router import fails for unrelated reasons (e.g. optional MFA package),
    # we still want accurate capability flags from env/dependencies.
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        try:
            from httpx_oauth.clients.google import GoogleOAuth2  # noqa: F401
            google_available = True
        except Exception:
            google_available = False

    if os.getenv("AZURE_CLIENT_ID") and os.getenv("AZURE_CLIENT_SECRET"):
        try:
            from msal import ConfidentialClientApplication  # noqa: F401
            azure_available = True
        except Exception:
            azure_available = False

    google_enabled = os.getenv("GOOGLE_SSO_ENABLED", "false").lower() == "true" and google_available
    azure_enabled = os.getenv("AZURE_SSO_ENABLED", "false").lower() == "true" and azure_available

    return {
        "google": google_enabled,
        "microsoft": azure_enabled,
        "has_sso": google_enabled or azure_enabled
    }
