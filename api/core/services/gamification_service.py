"""
Core gamification service for the finance application.

This service handles all gamification logic including points calculation,
achievement tracking, streak management, and user progress updates.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc


def serialize_for_json(obj: Any) -> Any:
    """Convert objects to JSON-serializable format"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj

from core.models.gamification import (
    UserGamificationProfile,
    Achievement,
    UserAchievement,
    UserStreak,
    Challenge,
    UserChallenge,
    PointHistory,
    OrganizationGamificationConfig,
    HabitType,
    AchievementCategory,
    DataRetentionPolicy
)
from core.schemas.gamification import (
    FinancialEvent,
    GamificationResult,
    ActionType,
    UserGamificationProfileCreate,
    UserGamificationProfileUpdate,
    UserGamificationProfileResponse,
    ModuleStatus,
    GamificationDashboard,
    AchievementCategory,
    AchievementResponse
)
from core.services.points_calculator import PointsCalculator
from core.services.level_progression import LevelProgressionSystem
from core.services.achievement_engine import AchievementEngine
from core.services.streak_tracker import StreakTracker
from core.services.challenge_manager import ChallengeManager
from core.services.financial_health_calculator import FinancialHealthCalculator

logger = logging.getLogger(__name__)


class GamificationService:
    """
    Core service for handling all gamification functionality.
    
    This service is responsible for:
    - Managing user gamification profiles
    - Processing financial events and awarding points
    - Tracking achievements and streaks
    - Calculating financial health scores
    - Managing module enable/disable functionality
    """

    def __init__(self, db: Session):
        self.db = db
        self.points_calculator = PointsCalculator(db)
        self.level_progression = LevelProgressionSystem(db)
        self.achievement_engine = AchievementEngine(db)
        self.streak_tracker = StreakTracker(db)
        self.challenge_manager = ChallengeManager(db)
        self.financial_health_calculator = FinancialHealthCalculator(db)

    # Module Management Methods
    async def is_enabled_for_user(self, user_id: int) -> bool:
        """Check if gamification is enabled for a specific user"""
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            return profile is not None and profile.module_enabled
        except Exception as e:
            logger.error(f"Error checking gamification status for user {user_id}: {str(e)}")
            return False

    async def get_module_status(self, user_id: int) -> ModuleStatus:
        """Get the current module status for a user"""
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return ModuleStatus(
                    enabled=False,
                    data_retention_policy=DataRetentionPolicy.PRESERVE,
                    features={}
                )
            
            return ModuleStatus(
                enabled=profile.module_enabled,
                enabled_at=profile.enabled_at,
                disabled_at=profile.disabled_at,
                data_retention_policy=profile.data_retention_policy,
                features=profile.preferences.get("features", {})
            )
        except Exception as e:
            logger.error(f"Error getting module status for user {user_id}: {str(e)}")
            return ModuleStatus(
                enabled=False,
                data_retention_policy=DataRetentionPolicy.PRESERVE,
                features={}
            )

    async def enable_gamification(self, user_id: int, preferences: Optional[Dict] = None) -> UserGamificationProfileResponse:
        """Enable gamification for a user"""
        try:
            # Check if profile already exists
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if profile:
                # Re-enable existing profile
                profile.module_enabled = True
                profile.enabled_at = datetime.now(timezone.utc)
                profile.disabled_at = None
                if preferences:
                    profile.preferences = preferences
            else:
                # Create new profile
                default_preferences = {
                    "features": {
                        "points": True,
                        "achievements": True,
                        "streaks": True,
                        "challenges": True,
                        "social": False,
                        "notifications": True
                    },
                    "privacy": {
                        "shareAchievements": False,
                        "showOnLeaderboard": False,
                        "allowFriendRequests": False
                    },
                    "notifications": {
                        "streakReminders": True,
                        "achievementCelebrations": True,
                        "challengeUpdates": True,
                        "frequency": "daily"
                    }
                }
                
                profile = UserGamificationProfile(
                    user_id=user_id,
                    module_enabled=True,
                    enabled_at=datetime.now(timezone.utc),
                    preferences=preferences or default_preferences,
                    statistics={
                        "totalActionsCompleted": 0,
                        "expensesTracked": 0,
                        "invoicesCreated": 0,
                        "receiptsUploaded": 0,
                        "budgetReviews": 0,
                        "longestStreak": 0,
                        "achievementsUnlocked": 0,
                        "challengesCompleted": 0
                    }
                )
                self.db.add(profile)
            
            self.db.commit()
            self.db.refresh(profile)
            
            # Initialize default streaks for new profiles
            if not profile.streaks:
                await self._initialize_user_streaks(profile.id)
            
            # Initialize achievements for new profiles
            existing_achievements = self.db.query(UserAchievement).filter(
                UserAchievement.profile_id == profile.id
            ).count()

            if existing_achievements == 0:
                self._initialize_user_achievements(profile.id)

            self.db.commit()
            return UserGamificationProfileResponse.model_validate(profile)

        except Exception as e:
            logger.error(f"Error enabling gamification for user {user_id}: {str(e)}")
            self.db.rollback()
            raise

    async def disable_gamification(self, user_id: int, data_retention_policy: DataRetentionPolicy) -> bool:
        """Disable gamification for a user"""
        try:
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return True  # Already disabled/doesn't exist

            profile.module_enabled = False
            profile.disabled_at = datetime.now(timezone.utc)
            profile.data_retention_policy = data_retention_policy
            
            # Handle data based on retention policy
            if data_retention_policy == DataRetentionPolicy.DELETE:
                await self._delete_user_gamification_data(profile.id)
            elif data_retention_policy == DataRetentionPolicy.ARCHIVE:
                await self._archive_user_gamification_data(profile.id)
            
            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error disabling gamification for user {user_id}: {str(e)}")
            self.db.rollback()
            return False

    # Core Gamification Processing
    async def process_financial_event(self, event: FinancialEvent) -> Optional[GamificationResult]:
        """
        Process a financial event and update user gamification data.
        Returns None if gamification is disabled for the user.
        """
        try:
            # Check if gamification is enabled for this user
            if not await self.is_enabled_for_user(event.user_id):
                return None

            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == event.user_id
            ).first()

            if not profile:
                logger.warning(f"No gamification profile found for user {event.user_id}")
                return None

            # Calculate points for this action using the points calculator
            points_awarded, point_breakdown = await self.points_calculator.calculate_points(
                event, profile, organization_id=None  # TODO: Get organization_id from user context
            )

            # Update user statistics
            await self._update_user_statistics(profile, event)

            # Commit statistics update before checking achievements
            self.db.commit()

            # Refresh profile to get updated statistics
            self.db.refresh(profile)

            # Update streaks using the streak tracker
            streaks_updated_raw = await self.streak_tracker.update_streaks_from_event(event)

            # Convert streak updates to response format
            streaks_updated = []
            if streaks_updated_raw:
                for streak in streaks_updated_raw:
                    if hasattr(streak, '__dict__'):
                        # It's a plain object, convert to dict
                        streak_dict = streak.__dict__
                    else:
                        streak_dict = streak

                    # Get the actual UserStreak from database for proper response
                    user_streak = self.db.query(UserStreak).filter(
                        and_(
                            UserStreak.profile_id == profile.id,
                            UserStreak.habit_type == streak_dict.get('habit_type', streak.habit_type)
                        )
                    ).first()
                    
                    if user_streak:
                        streaks_updated.append(user_streak)

            # Check for achievements using the achievement engine
            achievements_unlocked = await self.achievement_engine.check_achievements(profile, event)

            # Update challenge progress using the challenge manager
            challenges_updated = await self.challenge_manager.update_challenge_progress_from_event(event)

            # Update financial health score using the dedicated calculator
            health_score_change = await self.financial_health_calculator.update_score(event.user_id, event)

            # Check for level up using the level progression system
            level_up = await self.level_progression.check_level_up(profile, points_awarded)

            # Record point history with detailed breakdown
            await self._record_point_history(profile, event, points_awarded, point_breakdown)

            # Update profile totals (level progression system handles XP updates)
            # profile.total_experience_points is updated by level_progression.check_level_up
            profile.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            
            # Determine if celebration should be triggered
            celebration_triggered = bool(achievements_unlocked or level_up or any(c.get("completed", False) for c in challenges_updated))
            
            return GamificationResult(
                points_awarded=points_awarded,
                achievements_unlocked=achievements_unlocked,
                streaks_updated=streaks_updated,
                celebration_triggered=celebration_triggered,
                level_up=level_up,
                financial_health_score_change=health_score_change,
                challenges_updated=challenges_updated
            )
            
        except Exception as e:
            logger.error(f"Error processing financial event for user {event.user_id}: {str(e)}")
            self.db.rollback()
            return None

    # Dashboard and Analytics
    async def get_user_dashboard(self, user_id: int) -> Optional[GamificationDashboard]:
        """Get comprehensive dashboard data for a user"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None
            
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return None

            # Get recent achievements (last 10)
            recent_achievements = self.db.query(UserAchievement).filter(
                and_(
                    UserAchievement.profile_id == profile.id,
                    UserAchievement.is_completed == True
                )
            ).order_by(desc(UserAchievement.unlocked_at)).limit(10).all()

            # Get active streaks
            active_streaks = self.db.query(UserStreak).filter(
                and_(
                    UserStreak.profile_id == profile.id,
                    UserStreak.is_active == True,
                    UserStreak.current_length > 0
                )
            ).all()

            # Get active challenges
            active_challenges = self.db.query(UserChallenge).filter(
                and_(
                    UserChallenge.profile_id == profile.id,
                    UserChallenge.is_completed == False,
                    UserChallenge.opted_in == True
                )
            ).all()

            # Get recent points (last 20)
            recent_points = self.db.query(PointHistory).filter(
                PointHistory.profile_id == profile.id
            ).order_by(desc(PointHistory.created_at)).limit(20).all()

            # Calculate level progress
            level_progress = await self._calculate_level_progress(profile)

            # Get financial health trend (last 30 days)
            financial_health_trend = await self._get_financial_health_trend(profile)

            return GamificationDashboard(
                profile=UserGamificationProfileResponse.model_validate(profile),
                recent_achievements=recent_achievements,
                active_streaks=active_streaks,
                active_challenges=active_challenges,
                recent_points=recent_points,
                level_progress=level_progress,
                financial_health_trend=financial_health_trend
            )

        except Exception as e:
            logger.error(f"Error getting dashboard for user {user_id}: {str(e)}")
            return None

    # Achievement Management Methods
    async def initialize_achievements(self) -> bool:
        """Initialize all achievement definitions in the database"""
        return await self.achievement_engine.initialize_achievements()

    async def get_user_achievements(
        self, 
        user_id: int, 
        category: Optional[AchievementCategory] = None,
        completed_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all achievements for a user"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return []

            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()

            if not profile:
                return []
            
            return await self.achievement_engine.get_user_achievements(
                profile.id, category, completed_only
            )

        except Exception as e:
            logger.error(f"Error getting user achievements for user {user_id}: {str(e)}")
            return []

    async def get_achievement_progress(
        self, 
        user_id: int, 
        achievement_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get detailed progress information for a specific achievement"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()

            if not profile:
                return None
            
            return await self.achievement_engine.get_achievement_progress(profile, achievement_id)
            
        except Exception as e:
            logger.error(f"Error getting achievement progress for user {user_id}: {str(e)}")
            return None

    async def get_milestone_achievements(
        self, 
        category: AchievementCategory
    ) -> List[AchievementResponse]:
        """Get all milestone achievements for a specific category"""
        return await self.achievement_engine.get_milestone_achievements(category)

    # Streak Management Methods
    async def get_user_streaks(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all streaks for a user"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return []

            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()

            if not profile:
                return []

            streaks = self.db.query(UserStreak).filter(
                UserStreak.profile_id == profile.id
            ).all()

            streak_data = []
            for streak in streaks:
                status = await self.streak_tracker.track_streak(
                    user_id, streak.habit_type, datetime.now(timezone.utc)
                )
                
                streak_data.append({
                    "habit_type": streak.habit_type.value,
                    "current_length": status.current,
                    "longest_length": status.longest,
                    "last_activity": status.last_activity,
                    "is_active": status.is_active,
                    "risk_level": status.risk_level.value,
                    "days_since_activity": status.days_since_activity,
                    "times_broken": status.times_broken,
                    "streak_multiplier": await self.streak_tracker.calculate_streak_bonus(
                        status.current, streak.habit_type
                    )
                })
            
            return streak_data
            
        except Exception as e:
            logger.error(f"Error getting user streaks for user {user_id}: {str(e)}")
            return []

    async def get_streak_analytics(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive streak analytics for a user"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            analytics = await self.streak_tracker.get_streak_insights(user_id)

            return {
                "total_active_streaks": analytics.total_active_streaks,
                "longest_overall_streak": analytics.longest_overall_streak,
                "most_consistent_habit": analytics.most_consistent_habit.value if analytics.most_consistent_habit else None,
                "habit_strength_scores": {
                    habit.value: score for habit, score in analytics.habit_strength_scores.items()
                },
                "weekly_consistency": analytics.weekly_consistency,
                "monthly_trends": analytics.monthly_trends
            }
            
        except Exception as e:
            logger.error(f"Error getting streak analytics for user {user_id}: {str(e)}")
            return None

    async def get_users_at_streak_risk(self, risk_level: str = "medium_risk") -> List[Dict[str, Any]]:
        """Get users whose streaks are at risk of breaking"""
        try:
            from core.services.streak_tracker import StreakRiskLevel
            
            # Convert string to enum
            risk_enum_map = {
                "safe": StreakRiskLevel.SAFE,
                "low_risk": StreakRiskLevel.LOW_RISK,
                "medium_risk": StreakRiskLevel.MEDIUM_RISK,
                "high_risk": StreakRiskLevel.HIGH_RISK,
                "broken": StreakRiskLevel.BROKEN
            }
            
            risk_level_enum = risk_enum_map.get(risk_level, StreakRiskLevel.MEDIUM_RISK)
            return await self.streak_tracker.get_users_at_risk(risk_level_enum)
            
        except Exception as e:
            logger.error(f"Error getting users at streak risk: {str(e)}")
            return []

    async def handle_streak_break(self, user_id: int, habit_type_str: str) -> Optional[Dict[str, Any]]:
        """Handle a broken streak and provide recovery options"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            # Convert string to enum
            habit_type_map = {
                "daily_expense_tracking": HabitType.DAILY_EXPENSE_TRACKING,
                "weekly_budget_review": HabitType.WEEKLY_BUDGET_REVIEW,
                "invoice_follow_up": HabitType.INVOICE_FOLLOW_UP,
                "receipt_documentation": HabitType.RECEIPT_DOCUMENTATION
            }
            
            habit_type = habit_type_map.get(habit_type_str)
            if not habit_type:
                return None
            
            recovery = await self.streak_tracker.handle_streak_break(user_id, habit_type)
            
            return {
                "habit_type": recovery.habit_type.value,
                "broken_streak_length": recovery.broken_streak_length,
                "recovery_suggestions": recovery.recovery_suggestions,
                "encouragement_message": recovery.encouragement_message,
                "recovery_challenge_available": recovery.recovery_challenge_available
            }
            
        except Exception as e:
            logger.error(f"Error handling streak break for user {user_id}: {str(e)}")
            return None

    # Challenge Management Methods
    async def get_available_challenges(
        self, 
        user_id: int, 
        challenge_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available challenges for a user"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return []

            from core.models.gamification import ChallengeType as ChallengeTypeEnum

            # Convert string to enum if provided
            challenge_type_enum = None
            if challenge_type:
                challenge_type_map = {
                    "personal": ChallengeTypeEnum.PERSONAL,
                    "community": ChallengeTypeEnum.COMMUNITY,
                    "seasonal": ChallengeTypeEnum.SEASONAL
                }
                challenge_type_enum = challenge_type_map.get(challenge_type)
            
            challenges = await self.challenge_manager.get_available_challenges(
                user_id, challenge_type_enum, organization_id=None
            )
            
            return [challenge.dict() for challenge in challenges]
            
        except Exception as e:
            logger.error(f"Error getting available challenges for user {user_id}: {str(e)}")
            return []

    async def get_user_challenges(
        self, 
        user_id: int, 
        active_only: bool = True,
        completed_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get user's challenges"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return []

            challenges = await self.challenge_manager.get_user_challenges(
                user_id, active_only, completed_only
            )

            return [challenge.dict() for challenge in challenges]
            
        except Exception as e:
            logger.error(f"Error getting user challenges for user {user_id}: {str(e)}")
            return []

    async def opt_into_challenge(self, user_id: int, challenge_id: int) -> Optional[Dict[str, Any]]:
        """Opt user into a challenge"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            user_challenge = await self.challenge_manager.opt_into_challenge(user_id, challenge_id)

            if user_challenge:
                return user_challenge.model_dump()

            return None
            
        except Exception as e:
            logger.error(f"Error opting user {user_id} into challenge {challenge_id}: {str(e)}")
            return None

    async def opt_out_of_challenge(self, user_id: int, challenge_id: int) -> bool:
        """Opt user out of a challenge"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return False

            return await self.challenge_manager.opt_out_of_challenge(user_id, challenge_id)

        except Exception as e:
            logger.error(f"Error opting user {user_id} out of challenge {challenge_id}: {str(e)}")
            return False

    async def get_challenge_progress(self, user_id: int, challenge_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed challenge progress"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            return await self.challenge_manager.get_challenge_progress(user_id, challenge_id)

        except Exception as e:
            logger.error(f"Error getting challenge progress for user {user_id}: {str(e)}")
            return None

    async def initialize_challenges(self) -> bool:
        """Initialize default challenge templates"""
        return await self.challenge_manager.initialize_default_challenges()

    # Financial Health Score Methods
    async def get_financial_health_score(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get the complete financial health score for a user"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            health_score = await self.financial_health_calculator.calculate_score(user_id)

            if not health_score:
                return None
            
            return {
                "overall": health_score.overall,
                "components": health_score.components,
                "trend": health_score.trend.value,
                "recommendations": health_score.recommendations,
                "last_updated": health_score.last_updated.isoformat(),
                "score_history": [
                    {
                        "date": entry["date"].isoformat() if isinstance(entry["date"], datetime) else entry["date"],
                        "score": entry["score"]
                    }
                    for entry in health_score.score_history
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting financial health score for user {user_id}: {str(e)}")
            return None

    async def get_health_score_components(self) -> List[Dict[str, Any]]:
        """Get information about all health score components"""
        try:
            components = await self.financial_health_calculator.get_score_components()

            return [
                {
                    "name": comp.name,
                    "weight": comp.weight,
                    "description": comp.description,
                    "recommendations": comp.recommendations
                }
                for comp in components
            ]
            
        except Exception as e:
            logger.error(f"Error getting health score components: {str(e)}")
            return []

    async def recalculate_financial_health_score(self, user_id: int) -> Optional[float]:
        """Force recalculation of financial health score"""
        try:
            if not await self.is_enabled_for_user(user_id):
                return None

            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()

            if not profile:
                return None

            health_score = await self.financial_health_calculator.calculate_score(user_id)

            if not health_score:
                return None

            # Update the profile
            profile.financial_health_score = health_score.overall
            profile.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            
            return health_score.overall
            
        except Exception as e:
            logger.error(f"Error recalculating financial health score for user {user_id}: {str(e)}")
            self.db.rollback()
            return None

    # Private Helper Methods
    async def _update_user_statistics(self, profile: UserGamificationProfile, event: FinancialEvent):
        """Update user statistics based on the event"""
        # Get current statistics or use defaults
        stats = profile.statistics.copy() if profile.statistics else {
            "totalActionsCompleted": 0,
            "expensesTracked": 0,
            "invoicesCreated": 0,
            "receiptsUploaded": 0,
            "budgetReviews": 0
        }

        # Update counters
        stats["totalActionsCompleted"] = stats.get("totalActionsCompleted", 0) + 1

        # Update specific action counters
        if event.action_type == ActionType.EXPENSE_ADDED:
            stats["expensesTracked"] = stats.get("expensesTracked", 0) + 1
        elif event.action_type == ActionType.INVOICE_CREATED:
            stats["invoicesCreated"] = stats.get("invoicesCreated", 0) + 1
        elif event.action_type == ActionType.RECEIPT_UPLOADED:
            stats["receiptsUploaded"] = stats.get("receiptsUploaded", 0) + 1
        elif event.action_type == ActionType.BUDGET_REVIEWED:
            stats["budgetReviews"] = stats.get("budgetReviews", 0) + 1
        
        # Update the profile statistics field
        profile.statistics = stats
        # Mark the field as dirty for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(profile, "statistics")

    async def _update_streaks(self, profile: UserGamificationProfile, event: FinancialEvent) -> List:
        """Update user streaks based on the event"""
        # This is a simplified implementation
        # In a full implementation, this would check daily/weekly patterns
        streaks_updated = []
        
        habit_mapping = {
            ActionType.EXPENSE_ADDED: HabitType.DAILY_EXPENSE_TRACKING,
            ActionType.RECEIPT_UPLOADED: HabitType.RECEIPT_DOCUMENTATION,
            ActionType.INVOICE_CREATED: HabitType.INVOICE_FOLLOW_UP,
            ActionType.BUDGET_REVIEWED: HabitType.WEEKLY_BUDGET_REVIEW
        }
        
        habit_type = habit_mapping.get(event.action_type)
        if habit_type:
            streak = self.db.query(UserStreak).filter(
                and_(
                    UserStreak.profile_id == profile.id,
                    UserStreak.habit_type == habit_type
                )
            ).first()

            if streak:
                # Simplified streak update logic
                today = datetime.now(timezone.utc).date()
                last_activity = streak.last_activity_date.date() if streak.last_activity_date else None
                
                if last_activity != today:
                    streak.current_length += 1
                    streak.longest_length = max(streak.longest_length, streak.current_length)
                    streak.last_activity_date = datetime.now(timezone.utc)
                    streak.is_active = True
                    streaks_updated.append(streak)
        
        return streaks_updated

    async def _check_achievements(self, profile: UserGamificationProfile, event: FinancialEvent) -> List:
        """
        Check if any achievements should be unlocked based on the event.
        This method is deprecated - use achievement_engine.check_achievements instead.
        """
        # Delegate to the achievement engine
        return await self.achievement_engine.check_achievements(profile, event)

    async def _record_point_history(
        self, 
        profile: UserGamificationProfile, 
        event: FinancialEvent, 
        points_awarded: int,
        point_breakdown: Dict[str, Any]
    ):
        """Record point award in history with detailed breakdown"""
        try:
            # Serialize metadata to handle datetime objects
            serialized_metadata = serialize_for_json({
                **event.metadata,
                "point_breakdown": point_breakdown
            })

            point_record = PointHistory(
                profile_id=profile.id,
                action_type=event.action_type.value,
                points_awarded=points_awarded,
                base_points=point_breakdown.get("base_points", 0),
                streak_multiplier=point_breakdown.get("streak_multiplier", 1.0),
                accuracy_bonus=point_breakdown.get("accuracy_bonus", 0),
                completeness_bonus=point_breakdown.get("completeness_bonus", 0),
                timeliness_bonus=point_breakdown.get("timeliness_bonus", 0),
                action_metadata=serialized_metadata
            )

            self.db.add(point_record)

        except Exception as e:
            logger.error(f"Error recording point history: {str(e)}")
            # Create minimal record on error
            serialized_metadata = serialize_for_json(event.metadata)
            point_record = PointHistory(
                profile_id=profile.id,
                action_type=event.action_type.value,
                points_awarded=points_awarded,
                base_points=points_awarded,
                streak_multiplier=1.0,
                accuracy_bonus=0,
                completeness_bonus=0,
                timeliness_bonus=0,
                action_metadata=serialized_metadata
            )
            self.db.add(point_record)

    async def _initialize_user_streaks(self, profile_id: int):
        """Initialize default streaks for a new user"""
        default_habits = [
            HabitType.DAILY_EXPENSE_TRACKING,
            HabitType.WEEKLY_BUDGET_REVIEW,
            HabitType.INVOICE_FOLLOW_UP,
            HabitType.RECEIPT_DOCUMENTATION
        ]
        
        for habit_type in default_habits:
            streak = UserStreak(
                profile_id=profile_id,
                habit_type=habit_type,
                current_length=0,
                longest_length=0,
                is_active=True
            )
            self.db.add(streak)

    def _initialize_user_achievements(self, profile_id: int):
        """Initialize all achievements for a new user"""
        try:
            # First ensure achievement definitions exist
            from core.services.achievement_engine import AchievementEngine
            engine = AchievementEngine(self.db)
            engine.initialize_achievements()

            # Get all active achievements from the database
            achievements = self.db.query(Achievement).filter(
                Achievement.is_active == True
            ).all()

            if not achievements:
                logger.warning(f"No active achievements found to initialize for profile {profile_id}")
                return

            # Create UserAchievement records for each achievement
            for achievement in achievements:
                user_achievement = UserAchievement(
                    profile_id=profile_id,
                    achievement_id=achievement.id,
                    progress=0.0,
                    is_completed=False
                )
                self.db.add(user_achievement)

            logger.info(f"Initialized {len(achievements)} achievements for profile {profile_id}")

        except Exception as e:
            logger.error(f"Error initializing achievements for profile {profile_id}: {str(e)}")

    async def _delete_user_gamification_data(self, profile_id: int):
        """Delete all gamification data for a user"""
        # Delete related records
        self.db.query(UserAchievement).filter(UserAchievement.profile_id == profile_id).delete()
        self.db.query(UserStreak).filter(UserStreak.profile_id == profile_id).delete()
        self.db.query(UserChallenge).filter(UserChallenge.profile_id == profile_id).delete()
        self.db.query(PointHistory).filter(PointHistory.profile_id == profile_id).delete()

        # Delete profile
        self.db.query(UserGamificationProfile).filter(UserGamificationProfile.id == profile_id).delete()

    async def _archive_user_gamification_data(self, profile_id: int):
        """Archive gamification data (mark as archived but don't delete)"""
        # In a full implementation, this might move data to archive tables
        # For now, we'll just mark the profile as archived
        profile = self.db.query(UserGamificationProfile).filter(
            UserGamificationProfile.id == profile_id
        ).first()

        if profile:
            # Add archived flag to preferences
            preferences = profile.preferences or {}
            preferences["archived"] = True
            profile.preferences = preferences

    async def _calculate_level_progress(self, profile: UserGamificationProfile) -> Dict[str, Any]:
        """Calculate level progress information using the level progression system"""
        return await self.level_progression.calculate_level_progress(profile)

    async def _get_financial_health_trend(self, profile: UserGamificationProfile) -> List[Dict[str, Any]]:
        """Get financial health score trend over time using the dedicated calculator"""
        try:
            health_score = await self.financial_health_calculator.calculate_score(profile.user_id)
            if health_score:
                return health_score.score_history
            else:
                # Fallback to simple trend if calculator fails
                return [
                    {
                        "date": datetime.now(timezone.utc) - timedelta(days=30),
                        "score": max(profile.financial_health_score - 10, 0)
                    },
                    {
                        "date": datetime.now(timezone.utc) - timedelta(days=15),
                        "score": max(profile.financial_health_score - 5, 0)
                    },
                    {
                        "date": datetime.now(timezone.utc),
                        "score": profile.financial_health_score
                    }
                ]
        except Exception as e:
            logger.error(f"Error getting financial health trend: {str(e)}")
            # Fallback to simple trend
            return [
                {
                    "date": datetime.now(timezone.utc) - timedelta(days=30),
                    "score": max(profile.financial_health_score - 10, 0)
                },
                {
                    "date": datetime.now(timezone.utc) - timedelta(days=15),
                    "score": max(profile.financial_health_score - 5, 0)
                },
                {
                    "date": datetime.now(timezone.utc),
                    "score": profile.financial_health_score
                }
            ]