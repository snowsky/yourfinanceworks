"""
Gamification Module Manager Service.

This service manages the enable/disable functionality for the entire gamification system.
It provides a clean interface for controlling the gamification module at the user level.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.models.gamification import (
    UserGamificationProfile,
    DataRetentionPolicy
)
from core.schemas.gamification import (
    ModuleStatus,
    UserGamificationProfileResponse,
    EnableGamificationRequest,
    DisableGamificationRequest,
    GamificationPreferences
)
from core.services.gamification_service import GamificationService
from core.services.data_retention_manager import DataRetentionManager

logger = logging.getLogger(__name__)


class GamificationModuleManager:
    """
    Manages the gamification module state for users.
    
    This service provides a high-level interface for:
    - Checking if gamification is enabled for a user
    - Enabling/disabling gamification with proper data handling
    - Managing data retention policies
    - Providing module status information
    """

    def __init__(self, db: Session):
        self.db = db
        self.gamification_service = GamificationService(db)
        self.data_retention_manager = DataRetentionManager(db)

    async def is_enabled(self, user_id: int) -> bool:
        """
        Check if gamification is enabled for a specific user.
        
        Args:
            user_id: The ID of the user to check
            
        Returns:
            bool: True if gamification is enabled, False otherwise
        """
        try:
            return await self.gamification_service.is_enabled_for_user(user_id)
        except Exception as e:
            logger.error(f"Error checking if gamification is enabled for user {user_id}: {str(e)}")
            return False

    async def get_module_status(self, user_id: int) -> ModuleStatus:
        """
        Get the current module status for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            ModuleStatus: Current status of the gamification module
        """
        try:
            return await self.gamification_service.get_module_status(user_id)
        except Exception as e:
            logger.error(f"Error getting module status for user {user_id}: {str(e)}")
            return ModuleStatus(
                enabled=False,
                data_retention_policy=DataRetentionPolicy.PRESERVE,
                features={}
            )

    async def enable_gamification(
        self, 
        user_id: int, 
        request: EnableGamificationRequest
    ) -> UserGamificationProfileResponse:
        """
        Enable gamification for a user.
        
        Args:
            user_id: The ID of the user
            request: Request containing preferences and data retention policy
            
        Returns:
            UserGamificationProfileResponse: The user's gamification profile
            
        Raises:
            Exception: If enabling gamification fails
        """
        try:
            logger.info(f"Enabling gamification for user {user_id}")
            
            # Convert preferences to dict if provided
            preferences_dict = None
            if request.preferences:
                preferences_dict = {
                    "features": request.preferences.features,
                    "privacy": request.preferences.privacy,
                    "notifications": request.preferences.notifications
                }
            
            # Enable gamification using the service
            profile = await self.gamification_service.enable_gamification(
                user_id=user_id,
                preferences=preferences_dict
            )
            
            # Update data retention policy
            if request.data_retention_policy:
                profile_obj = self.db.query(UserGamificationProfile).filter(
                    UserGamificationProfile.user_id == user_id
                ).first()
                
                if profile_obj:
                    # If re-enabling with ARCHIVE policy, restore archived data
                    if request.data_retention_policy == DataRetentionPolicy.ARCHIVE:
                        await self.data_retention_manager.apply_retention_policy(
                            profile_obj.id,
                            request.data_retention_policy,
                            action="enable"
                        )
                    
                    profile_obj.data_retention_policy = request.data_retention_policy
                    self.db.commit()
            
            logger.info(f"Successfully enabled gamification for user {user_id}")
            return profile
            
        except Exception as e:
            logger.error(f"Error enabling gamification for user {user_id}: {str(e)}")
            raise

    async def disable_gamification(
        self, 
        user_id: int, 
        request: DisableGamificationRequest
    ) -> bool:
        """
        Disable gamification for a user.
        
        Args:
            user_id: The ID of the user
            request: Request containing data retention policy
            
        Returns:
            bool: True if successfully disabled, False otherwise
        """
        try:
            logger.info(f"Disabling gamification for user {user_id} with policy {request.data_retention_policy}")
            
            # Get the profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                logger.warning(f"No gamification profile found for user {user_id}")
                return False
            
            # Apply data retention policy
            success = await self.data_retention_manager.apply_retention_policy(
                profile.id,
                request.data_retention_policy,
                action="disable"
            )
            
            if not success:
                logger.error(f"Failed to apply retention policy for user {user_id}")
                return False
            
            # Update profile status
            profile.module_enabled = False
            profile.disabled_at = datetime.now(timezone.utc)
            profile.data_retention_policy = request.data_retention_policy
            profile.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            logger.info(f"Successfully disabled gamification for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling gamification for user {user_id}: {str(e)}")
            self.db.rollback()
            return False

    async def migrate_user_data(self, user_id: int, enabled: bool) -> bool:
        """
        Migrate user data when enabling/disabling gamification.
        
        Args:
            user_id: The ID of the user
            enabled: Whether gamification is being enabled or disabled
            
        Returns:
            bool: True if migration was successful, False otherwise
        """
        try:
            logger.info(f"Migrating gamification data for user {user_id}, enabled={enabled}")
            
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                logger.warning(f"No gamification profile found for user {user_id}")
                return True  # Nothing to migrate
            
            # Apply retention policy based on current state
            action = "enable" if enabled else "disable"
            success = await self.data_retention_manager.apply_retention_policy(
                profile.id,
                profile.data_retention_policy,
                action=action
            )
            
            if success:
                logger.info(f"Successfully migrated gamification data for user {user_id}")
            else:
                logger.error(f"Failed to migrate gamification data for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error migrating gamification data for user {user_id}: {str(e)}")
            return False

    async def update_user_preferences(
        self, 
        user_id: int, 
        preferences: GamificationPreferences
    ) -> Optional[UserGamificationProfileResponse]:
        """
        Update user gamification preferences.
        
        Args:
            user_id: The ID of the user
            preferences: New preferences to apply
            
        Returns:
            UserGamificationProfileResponse: Updated profile, or None if not found
        """
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                logger.warning(f"No gamification profile found for user {user_id}")
                return None
            
            # Update preferences
            preferences_dict = {
                "features": preferences.features,
                "privacy": preferences.privacy,
                "notifications": preferences.notifications
            }
            
            profile.preferences = preferences_dict
            profile.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(profile)
            
            logger.info(f"Updated gamification preferences for user {user_id}")
            return UserGamificationProfileResponse.model_validate(profile)
            
        except Exception as e:
            logger.error(f"Error updating preferences for user {user_id}: {str(e)}")
            self.db.rollback()
            return None

    async def get_user_profile(self, user_id: int) -> Optional[UserGamificationProfileResponse]:
        """
        Get the user's gamification profile.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            UserGamificationProfileResponse: The user's profile, or None if not found
        """
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return None
            
            return UserGamificationProfileResponse.model_validate(profile)
            
        except Exception as e:
            logger.error(f"Error getting profile for user {user_id}: {str(e)}")
            return None

    async def validate_module_state(self, user_id: int) -> Dict[str, Any]:
        """
        Validate the current state of the gamification module for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict containing validation results
        """
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            validation_result = {
                "user_id": user_id,
                "profile_exists": profile is not None,
                "module_enabled": False,
                "data_consistent": True,
                "issues": []
            }
            
            if profile:
                validation_result["module_enabled"] = profile.module_enabled
                
                # Check for data consistency issues
                if profile.module_enabled and not profile.enabled_at:
                    validation_result["data_consistent"] = False
                    validation_result["issues"].append("Profile enabled but no enabled_at timestamp")
                
                if not profile.module_enabled and not profile.disabled_at:
                    validation_result["data_consistent"] = False
                    validation_result["issues"].append("Profile disabled but no disabled_at timestamp")
                
                # Check for orphaned data
                if not profile.module_enabled and profile.data_retention_policy == DataRetentionPolicy.DELETE:
                    # Should have minimal data
                    if profile.achievements or profile.streaks or profile.challenges:
                        validation_result["data_consistent"] = False
                        validation_result["issues"].append("Profile has data but should be deleted")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating module state for user {user_id}: {str(e)}")
            return {
                "user_id": user_id,
                "profile_exists": False,
                "module_enabled": False,
                "data_consistent": False,
                "issues": [f"Validation error: {str(e)}"]
            }

    async def get_data_retention_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get the data retention status for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict containing retention status information
        """
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return {
                    "user_id": user_id,
                    "profile_found": False,
                    "status": "not_found"
                }
            
            return await self.data_retention_manager.get_data_retention_status(profile.id)
            
        except Exception as e:
            logger.error(f"Error getting retention status for user {user_id}: {str(e)}")
            return {
                "user_id": user_id,
                "profile_found": False,
                "error": str(e)
            }

    async def validate_data_consistency(self, user_id: int) -> Dict[str, Any]:
        """
        Validate data consistency for a user's gamification profile.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict containing validation results
        """
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return {
                    "user_id": user_id,
                    "valid": False,
                    "issues": ["Profile not found"]
                }
            
            return await self.data_retention_manager.validate_data_consistency(profile.id)
            
        except Exception as e:
            logger.error(f"Error validating data consistency for user {user_id}: {str(e)}")
            return {
                "user_id": user_id,
                "valid": False,
                "issues": [f"Validation error: {str(e)}"]
            }

    async def change_retention_policy(
        self,
        user_id: int,
        new_policy: DataRetentionPolicy
    ) -> bool:
        """
        Change the data retention policy for a user.
        
        Args:
            user_id: The ID of the user
            new_policy: The new retention policy to apply
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                logger.warning(f"No gamification profile found for user {user_id}")
                return False
            
            old_policy = profile.data_retention_policy
            
            logger.info(f"Changing retention policy for user {user_id} from {old_policy.value} to {new_policy.value}")
            
            # Migrate data based on policy change
            success = await self.data_retention_manager.migrate_data_on_policy_change(
                profile.id,
                old_policy,
                new_policy
            )
            
            if success:
                profile.data_retention_policy = new_policy
                profile.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                logger.info(f"Successfully changed retention policy for user {user_id}")
            else:
                logger.error(f"Failed to change retention policy for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error changing retention policy for user {user_id}: {str(e)}")
            self.db.rollback()
            return False