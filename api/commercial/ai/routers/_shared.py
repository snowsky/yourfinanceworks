# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

"""
Shared imports and utilities for AI sub-routers.
This file documents the common dependencies used across AI routers.
Each sub-router file directly imports what it needs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
import httpx
import logging
import os
import json
import re

from core.models.database import get_master_db, get_db, set_tenant_context
from core.routers.auth import get_current_user
from core.models.models import MasterUser, Tenant
from core.models.models_per_tenant import Invoice, Client, ClientNote, AIConfig, AIChatHistory, Settings
from core.schemas.settings import Settings as SettingsSchema
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.feature_gate import require_feature
from commercial.ai.services.ai_config_service import AIConfigService
from core.constants.recommendation_codes import (
    CONSIDER_STRICTER_PAYMENT_TERMS,
    REVIEW_PAYMENT_TERMS_SLOW_CLIENTS,
    START_CREATING_INVOICES,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
