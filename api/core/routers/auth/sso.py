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

    try:
        from commercial.sso.router import google_oauth_client, azure_oauth_client
        google_available = google_oauth_client is not None
        azure_available = azure_oauth_client is not None
    except ImportError:
        pass

    google_enabled = os.getenv("GOOGLE_SSO_ENABLED", "false").lower() == "true" and google_available
    azure_enabled = os.getenv("AZURE_SSO_ENABLED", "false").lower() == "true" and azure_available

    return {
        "google": google_enabled,
        "microsoft": azure_enabled,
        "has_sso": google_enabled or azure_enabled
    }
