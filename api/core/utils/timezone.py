"""
Timezone utilities for handling tenant-specific timezone settings.
"""
from datetime import datetime, timezone
from typing import Optional
import logging

from sqlalchemy.orm import Session
from core.models.models_per_tenant import Settings

logger = logging.getLogger(__name__)


def get_tenant_timezone(db: Session) -> str:
    """
    Get the timezone setting for the current tenant.
    
    Args:
        db: Database session for tenant database
        
    Returns:
        str: Timezone string (e.g., 'UTC', 'America/New_York', 'Europe/London')
               Defaults to 'UTC' if not set
    """
    try:
        timezone_setting = db.query(Settings).filter(Settings.key == "timezone").first()
        if timezone_setting and timezone_setting.value:
            timezone_str = str(timezone_setting.value).strip()
            if timezone_str:
                logger.debug(f"Using tenant timezone: {timezone_str}")
                return timezone_str
        
        logger.debug("No tenant timezone setting found, using UTC")
        return "UTC"
    except Exception as e:
        logger.warning(f"Error getting tenant timezone: {e}, using UTC")
        return "UTC"


def get_tenant_timezone_aware_datetime(db: Session) -> datetime:
    """
    Get current datetime in tenant's timezone with proper seconds precision.
    
    Args:
        db: Database session for tenant database
        
    Returns:
        datetime: Current timezone-aware datetime in tenant's timezone
    """
    try:
        import pytz
        
        # Get tenant timezone setting
        tenant_tz_str = get_tenant_timezone(db)
        
        # Try to get the timezone object
        try:
            tenant_tz = pytz.timezone(tenant_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone '{tenant_tz_str}', falling back to UTC")
            tenant_tz = pytz.UTC
        
        # Get current time in tenant timezone with seconds precision
        now = datetime.now(tenant_tz)
        
        # Ensure we have seconds precision (not microseconds)
        if now.microsecond > 0:
            # Round to nearest second
            from datetime import timedelta
            if now.microsecond >= 500000:
                now = now + timedelta(seconds=1)
            now = now.replace(microsecond=0)
        
        logger.debug(f"Generated tenant timezone-aware datetime: {now.isoformat()}")
        return now
        
    except ImportError:
        # If pytz is not available, fall back to UTC
        logger.warning("pytz not available, using UTC timezone")
        now = datetime.now(timezone.utc)
        # Remove microseconds for seconds precision
        if now.microsecond > 0:
            from datetime import timedelta
            if now.microsecond >= 500000:
                now = now + timedelta(seconds=1)
            now = now.replace(microsecond=0)
        return now
    except Exception as e:
        logger.error(f"Error creating timezone-aware datetime: {e}, falling back to UTC")
        now = datetime.now(timezone.utc)
        # Remove microseconds for seconds precision
        if now.microsecond > 0:
            from datetime import timedelta
            if now.microsecond >= 500000:
                now = now + timedelta(seconds=1)
            now = now.replace(microsecond=0)
        return now


def convert_to_tenant_timezone(dt: datetime, db: Session) -> datetime:
    """
    Convert a datetime to tenant's timezone.
    
    Args:
        dt: Datetime to convert (can be naive or timezone-aware)
        db: Database session for tenant database
        
    Returns:
        datetime: Datetime converted to tenant's timezone
    """
    try:
        import pytz
        
        # Get tenant timezone setting
        tenant_tz_str = get_tenant_timezone(db)
        
        # Try to get the timezone object
        try:
            tenant_tz = pytz.timezone(tenant_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone '{tenant_tz_str}', falling back to UTC")
            tenant_tz = pytz.UTC
        
        # If datetime is naive, assume UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        # Convert to tenant timezone
        dt_converted = dt.astimezone(tenant_tz)
        
        # Ensure seconds precision
        if dt_converted.microsecond > 0:
            from datetime import timedelta
            if dt_converted.microsecond >= 500000:
                dt_converted = dt_converted + timedelta(seconds=1)
            dt_converted = dt_converted.replace(microsecond=0)
        
        return dt_converted
        
    except ImportError:
        logger.warning("pytz not available, returning original datetime")
        return dt
    except Exception as e:
        logger.error(f"Error converting timezone: {e}, returning original datetime")
        return dt
