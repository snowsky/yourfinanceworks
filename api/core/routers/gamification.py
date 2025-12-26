"""
Gamification API router.

This module provides REST API endpoints for the gamification system,
including user profile management, module control, and dashboard data.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging

from core.models.database import get_db
from core.services.gamification_module_manager import GamificationModuleManager
from core.services.gamification_service import GamificationService
from core.services.level_progression import LevelProgressionSystem
from core.services.challenge_manager import ChallengeManager
from core.schemas.gamification import (
    UserGamificationProfileResponse,
    ModuleStatus,
    EnableGamificationRequest,
    DisableGamificationRequest,
    GamificationPreferences,
    FinancialEvent,
    ProcessFinancialEventRequest,
    ProcessFinancialEventResponse,
    GamificationDashboard,
    GamificationResult,
    AchievementCategory,
    AchievementResponse,
    StreakStatusResponse,
    StreakRecoveryResponse,
    StreakAnalyticsResponse,
    UsersAtRiskResponse,
    ChallengeCreate,
    ChallengeResponse,
    UserChallengeResponse,
    ChallengeType,
    FinancialHealthScoreResponse,
    HealthScoreComponentResponse
)
from core.routers.auth import get_current_user
from core.models.models_per_tenant import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/status", response_model=ModuleStatus)
async def get_gamification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current gamification module status for the authenticated user.
    """
    try:
        module_manager = GamificationModuleManager(db)
        status = await module_manager.get_module_status(current_user.id)
        return status
    except Exception as e:
        logger.error(f"Error getting gamification status for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get gamification status"
        )


@router.post("/enable", response_model=UserGamificationProfileResponse)
async def enable_gamification(
    request: EnableGamificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable gamification for the authenticated user.
    """
    try:
        module_manager = GamificationModuleManager(db)
        profile = await module_manager.enable_gamification(current_user.id, request)
        return profile
    except Exception as e:
        logger.error(f"Error enabling gamification for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable gamification"
        )


@router.post("/disable")
async def disable_gamification(
    request: DisableGamificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable gamification for the authenticated user.
    """
    try:
        module_manager = GamificationModuleManager(db)
        success = await module_manager.disable_gamification(current_user.id, request)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disable gamification"
            )
        
        return {"message": "Gamification disabled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling gamification for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable gamification"
        )


@router.get("/profile", response_model=Optional[UserGamificationProfileResponse])
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the authenticated user's gamification profile.
    Returns null if gamification is disabled.
    """
    try:
        module_manager = GamificationModuleManager(db)
        profile = await module_manager.get_user_profile(current_user.id)
        return profile
    except Exception as e:
        logger.error(f"Error getting profile for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


@router.put("/preferences", response_model=Optional[UserGamificationProfileResponse])
async def update_preferences(
    preferences: GamificationPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the authenticated user's gamification preferences.
    """
    try:
        module_manager = GamificationModuleManager(db)
        profile = await module_manager.update_user_preferences(current_user.id, preferences)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gamification profile not found"
            )
        
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preferences for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )


@router.get("/dashboard", response_model=Optional[GamificationDashboard])
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard data for the authenticated user.
    Returns null if gamification is disabled.
    """
    try:
        gamification_service = GamificationService(db)
        dashboard = await gamification_service.get_user_dashboard(current_user.id)
        return dashboard
    except Exception as e:
        logger.error(f"Error getting dashboard for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data"
        )


@router.post("/events/process", response_model=ProcessFinancialEventResponse)
async def process_financial_event(
    request: ProcessFinancialEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process a financial event for gamification.
    This endpoint is typically called by other services when financial actions occur.
    """
    try:
        # Ensure the event is for the current user
        if request.event.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot process events for other users"
            )
        
        gamification_service = GamificationService(db)
        result = await gamification_service.process_financial_event(request.event)
        
        if result is None:
            return ProcessFinancialEventResponse(
                success=True,
                result=None,
                message="Gamification is disabled for this user"
            )
        
        return ProcessFinancialEventResponse(
            success=True,
            result=result,
            message="Event processed successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing financial event for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process financial event"
        )


@router.get("/validate")
async def validate_module_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate the current state of the gamification module for the authenticated user.
    Useful for debugging and health checks.
    """
    try:
        module_manager = GamificationModuleManager(db)
        validation_result = await module_manager.validate_module_state(current_user.id)
        return validation_result
    except Exception as e:
        logger.error(f"Error validating module state for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate module state"
        )


# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check endpoint for the gamification module.
    """
    return {
        "status": "healthy",
        "module": "gamification",
        "version": "1.0.0"
    }


# Internal endpoints for system integration
@router.post("/internal/process-event", response_model=Optional[GamificationResult])
async def internal_process_event(
    event: FinancialEvent,
    db: Session = Depends(get_db)
):
    """
    Internal endpoint for processing financial events.
    This endpoint is used by other services and doesn't require user authentication.
    Should be protected by internal network security.
    """
    try:
        gamification_service = GamificationService(db)
        result = await gamification_service.process_financial_event(event)
        return result
    except Exception as e:
        logger.error(f"Error processing internal financial event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process financial event"
        )


@router.get("/level/progress")
async def get_level_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed level progress information for the authenticated user.
    """
    try:
        gamification_service = GamificationService(db)
        
        # Check if gamification is enabled
        if not await gamification_service.is_enabled_for_user(current_user.id):
            return None
        
        # Get user profile
        from core.models.gamification import UserGamificationProfile
        profile = db.query(UserGamificationProfile).filter(
            UserGamificationProfile.user_id == current_user.id
        ).first()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gamification profile not found"
            )
        
        level_progression = LevelProgressionSystem(db)
        progress = await level_progression.calculate_level_progress(profile)
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting level progress for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get level progress"
        )


@router.get("/level/rewards/{level}")
async def get_level_rewards(
    level: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get information about rewards and benefits for a specific level.
    """
    try:
        if level < 1 or level > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Level must be between 1 and 100"
            )
        
        level_progression = LevelProgressionSystem(db)
        rewards = await level_progression.get_level_rewards_info(level)
        
        return rewards
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting level rewards for level {level}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get level rewards"
        )


@router.get("/level/curve")
async def get_level_curve_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get information about the level progression curve.
    """
    try:
        level_progression = LevelProgressionSystem(db)
        curve_info = level_progression.get_level_curve_info()
        
        return curve_info
    except Exception as e:
        logger.error(f"Error getting level curve info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get level curve information"
        )


@router.get("/internal/user/{user_id}/enabled")
async def internal_check_enabled(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to check if gamification is enabled for a specific user.
    Used by other services to determine if they should send gamification events.
    """
    try:
        gamification_service = GamificationService(db)
        enabled = await gamification_service.is_enabled_for_user(user_id)
        return {"user_id": user_id, "enabled": enabled}
    except Exception as e:
        logger.error(f"Error checking if gamification is enabled for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check gamification status"
        )


# Achievement Management Endpoints
@router.get("/achievements", response_model=List[Dict[str, Any]])
async def get_user_achievements(
    category: Optional[AchievementCategory] = None,
    completed_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all achievements for the authenticated user.
    Can be filtered by category or completion status.
    """
    try:
        gamification_service = GamificationService(db)
        achievements = await gamification_service.get_user_achievements(
            current_user.id, category, completed_only
        )
        return achievements
    except Exception as e:
        logger.error(f"Error getting achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user achievements"
        )


@router.get("/achievements/{achievement_id}/progress")
async def get_achievement_progress(
    achievement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed progress information for a specific achievement.
    """
    try:
        gamification_service = GamificationService(db)
        progress = await gamification_service.get_achievement_progress(
            current_user.id, achievement_id
        )
        
        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Achievement not found or gamification disabled"
            )
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting achievement progress for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get achievement progress"
        )


@router.get("/achievements/milestones/{category}", response_model=List[AchievementResponse])
async def get_milestone_achievements(
    category: AchievementCategory,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all milestone achievements for a specific category.
    """
    try:
        gamification_service = GamificationService(db)
        achievements = await gamification_service.get_milestone_achievements(category)
        return achievements
    except Exception as e:
        logger.error(f"Error getting milestone achievements for category {category}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get milestone achievements"
        )


@router.post("/admin/achievements/initialize")
async def initialize_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialize all achievement definitions in the database.
    This endpoint should be called during system setup or when adding new achievements.
    Requires admin privileges.
    """
    try:
        # TODO: Add admin privilege check
        # For now, any authenticated user can initialize achievements
        
        gamification_service = GamificationService(db)
        success = await gamification_service.initialize_achievements()
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize achievements"
            )
        
        return {"message": "Achievements initialized successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing achievements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize achievements"
        )


@router.get("/admin/achievements/rules")
async def get_achievement_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all achievement definitions/rules.
    Returns the complete list of achievement rules with their requirements.
    """
    try:
        # TODO: Add admin privilege check if needed
        # For now, any authenticated user can view achievement rules
        
        from core.services.achievement_engine import AchievementEngine
        achievement_engine = AchievementEngine(db)
        rules = achievement_engine._get_achievement_definitions()
        
        return {
            "rules": rules,
            "total_count": len(rules)
        }
    except Exception as e:
        logger.error(f"Error getting achievement rules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get achievement rules"
        )


@router.put("/admin/achievements/rules/{achievement_id}/toggle")
async def toggle_achievement_rule(
    achievement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle an achievement rule's active status.
    Requires admin privileges.
    """
    try:
        # TODO: Add admin privilege check if needed
        # For now, any authenticated user can toggle achievement rules
        
        from core.models.gamification import Achievement
        from sqlalchemy import select
        
        # Find the achievement in the database
        result = db.execute(
            select(Achievement).where(Achievement.achievement_id == achievement_id)
        )
        achievement = result.scalar_one_or_none()
        
        if not achievement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Achievement rule not found"
            )
        
        # Toggle the active status
        achievement.is_active = not achievement.is_active
        db.commit()
        db.refresh(achievement)
        
        return {
            "achievement_id": achievement.achievement_id,
            "is_active": achievement.is_active,
            "message": f"Achievement rule '{achievement.name}' {'activated' if achievement.is_active else 'deactivated'} successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling achievement rule {achievement_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle achievement rule"
        )


# Streak Management Endpoints
@router.get("/streaks", response_model=List[Dict[str, Any]])
async def get_user_streaks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all streaks for the authenticated user.
    """
    try:
        gamification_service = GamificationService(db)
        streaks = await gamification_service.get_user_streaks(current_user.id)
        return streaks
    except Exception as e:
        logger.error(f"Error getting streaks for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user streaks"
        )


@router.get("/streaks/analytics")
async def get_streak_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive streak analytics for the authenticated user.
    """
    try:
        gamification_service = GamificationService(db)
        analytics = await gamification_service.get_streak_analytics(current_user.id)
        
        if not analytics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Streak analytics not found or gamification disabled"
            )
        
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting streak analytics for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get streak analytics"
        )


@router.post("/streaks/{habit_type}/break")
async def handle_streak_break(
    habit_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle a broken streak and get recovery suggestions.
    
    Args:
        habit_type: One of 'daily_expense_tracking', 'weekly_budget_review', 
                   'invoice_follow_up', 'receipt_documentation'
    """
    try:
        valid_habits = [
            "daily_expense_tracking", 
            "weekly_budget_review", 
            "invoice_follow_up", 
            "receipt_documentation"
        ]
        
        if habit_type not in valid_habits:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid habit type. Must be one of: {', '.join(valid_habits)}"
            )
        
        gamification_service = GamificationService(db)
        recovery = await gamification_service.handle_streak_break(current_user.id, habit_type)
        
        if not recovery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Streak not found or gamification disabled"
            )
        
        return recovery
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling streak break for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to handle streak break"
        )


@router.get("/admin/streaks/at-risk")
async def get_users_at_streak_risk(
    risk_level: str = "medium_risk",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get users whose streaks are at risk of breaking.
    
    Args:
        risk_level: One of 'safe', 'low_risk', 'medium_risk', 'high_risk', 'broken'
    
    Requires admin privileges.
    """
    try:
        # TODO: Add admin privilege check
        
        valid_risk_levels = ["safe", "low_risk", "medium_risk", "high_risk", "broken"]
        if risk_level not in valid_risk_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid risk level. Must be one of: {', '.join(valid_risk_levels)}"
            )
        
        gamification_service = GamificationService(db)
        at_risk_users = await gamification_service.get_users_at_streak_risk(risk_level)
        
        return {
            "risk_level": risk_level,
            "users_at_risk": at_risk_users,
            "total_count": len(at_risk_users)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting users at streak risk: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users at streak risk"
        )


# Challenge Management Endpoints
@router.get("/challenges/available", response_model=List[ChallengeResponse])
async def get_available_challenges(
    challenge_type: Optional[ChallengeType] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all available challenges for the authenticated user.
    Can be filtered by challenge type.
    """
    try:
        challenge_manager = ChallengeManager(db)
        challenges = await challenge_manager.get_available_challenges(
            current_user.id, challenge_type, organization_id=None  # TODO: Get org from user context
        )
        return challenges
    except Exception as e:
        logger.error(f"Error getting available challenges for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available challenges"
        )


@router.get("/challenges/weekly", response_model=List[ChallengeResponse])
async def get_weekly_challenges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get weekly challenges that are currently active.
    """
    try:
        challenge_manager = ChallengeManager(db)
        challenges = await challenge_manager.get_weekly_challenges(
            organization_id=None  # TODO: Get org from user context
        )
        return challenges
    except Exception as e:
        logger.error(f"Error getting weekly challenges: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weekly challenges"
        )


@router.get("/challenges/monthly", response_model=List[ChallengeResponse])
async def get_monthly_challenges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get monthly challenges that are currently active.
    """
    try:
        challenge_manager = ChallengeManager(db)
        challenges = await challenge_manager.get_monthly_challenges(
            organization_id=None  # TODO: Get org from user context
        )
        return challenges
    except Exception as e:
        logger.error(f"Error getting monthly challenges: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get monthly challenges"
        )


@router.post("/challenges/{challenge_id}/opt-in", response_model=Optional[UserChallengeResponse])
async def opt_into_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Opt the authenticated user into a challenge.
    """
    try:
        challenge_manager = ChallengeManager(db)
        user_challenge = await challenge_manager.opt_into_challenge(current_user.id, challenge_id)
        
        if not user_challenge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to opt into challenge. Challenge may not exist or gamification may be disabled."
            )
        
        return user_challenge
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error opting user {current_user.id} into challenge {challenge_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to opt into challenge"
        )


@router.post("/challenges/{challenge_id}/opt-out")
async def opt_out_of_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Opt the authenticated user out of a challenge.
    """
    try:
        challenge_manager = ChallengeManager(db)
        success = await challenge_manager.opt_out_of_challenge(current_user.id, challenge_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to opt out of challenge"
            )
        
        return {"message": "Successfully opted out of challenge"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error opting user {current_user.id} out of challenge {challenge_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to opt out of challenge"
        )


@router.get("/challenges/my", response_model=List[UserChallengeResponse])
async def get_my_challenges(
    active_only: bool = True,
    completed_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all challenges for the authenticated user.
    Can be filtered to show only active or completed challenges.
    """
    try:
        challenge_manager = ChallengeManager(db)
        challenges = await challenge_manager.get_user_challenges(
            current_user.id, active_only, completed_only
        )
        return challenges
    except Exception as e:
        logger.error(f"Error getting user challenges for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user challenges"
        )


@router.get("/challenges/{challenge_id}/progress")
async def get_challenge_progress(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed progress information for a specific challenge.
    """
    try:
        challenge_manager = ChallengeManager(db)
        progress = await challenge_manager.get_challenge_progress(current_user.id, challenge_id)
        
        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Challenge progress not found or user not participating in challenge"
            )
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting challenge progress for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get challenge progress"
        )


@router.post("/admin/challenges", response_model=ChallengeResponse)
async def create_challenge(
    challenge_data: ChallengeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new challenge template.
    Requires admin privileges.
    """
    try:
        # TODO: Add admin privilege check
        
        challenge_manager = ChallengeManager(db)
        challenge = await challenge_manager.create_challenge_template(challenge_data)
        return challenge
    except Exception as e:
        logger.error(f"Error creating challenge: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create challenge"
        )


@router.post("/admin/challenges/initialize")
async def initialize_default_challenges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialize default challenge templates.
    This endpoint should be called during system setup.
    Requires admin privileges.
    """
    try:
        # TODO: Add admin privilege check
        
        challenge_manager = ChallengeManager(db)
        success = await challenge_manager.initialize_default_challenges()
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize default challenges"
            )
        
        return {"message": "Default challenges initialized successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing default challenges: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize default challenges"
        )


# Financial Health Score Endpoints
@router.get("/health-score", response_model=FinancialHealthScoreResponse)
async def get_financial_health_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the complete financial health score for the authenticated user.
    Returns detailed component scores, trends, and recommendations.
    """
    try:
        gamification_service = GamificationService(db)
        health_score = await gamification_service.get_financial_health_score(current_user.id)
        
        if not health_score:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial health score not found or gamification disabled"
            )
        
        return health_score
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting financial health score for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get financial health score"
        )


@router.get("/health-score/components", response_model=List[HealthScoreComponentResponse])
async def get_health_score_components(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get information about all financial health score components.
    Includes component weights, descriptions, and recommendations.
    """
    try:
        gamification_service = GamificationService(db)
        components = await gamification_service.get_health_score_components()
        return components
    except Exception as e:
        logger.error(f"Error getting health score components: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get health score components"
        )


@router.post("/health-score/recalculate")
async def recalculate_financial_health_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Force recalculation of the financial health score for the authenticated user.
    Useful for updating the score after bulk data changes.
    """
    try:
        gamification_service = GamificationService(db)
        new_score = await gamification_service.recalculate_financial_health_score(current_user.id)
        
        if new_score is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unable to recalculate score. Gamification may be disabled."
            )
        
        return {
            "message": "Financial health score recalculated successfully",
            "new_score": new_score
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating financial health score for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to recalculate financial health score"
        )


@router.post("/admin/challenges/{challenge_id}/complete/{user_id}")
async def admin_complete_challenge(
    challenge_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually complete a challenge for a user (admin only).
    Useful for testing or resolving issues.
    """
    try:
        # TODO: Add admin privilege check
        
        challenge_manager = ChallengeManager(db)
        result = await challenge_manager.complete_challenge(user_id, challenge_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Challenge or user participation not found"
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing challenge {challenge_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete challenge"
        )