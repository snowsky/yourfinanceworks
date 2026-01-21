"""
Achievement Engine for the gamification system.

This service handles achievement definitions, milestone tracking, and badge awarding.
It provides comprehensive achievement management across all categories defined in the requirements.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from core.models.gamification import (
    Achievement,
    UserAchievement,
    UserGamificationProfile,
    UserStreak,
    PointHistory,
    AchievementCategory,
    AchievementDifficulty,
    HabitType
)
from core.schemas.gamification import (
    FinancialEvent,
    ActionType,
    AchievementResponse,
    AchievementCreate,
    AchievementRequirement
)

logger = logging.getLogger(__name__)


class AchievementEngine:
    """
    Core achievement engine that manages all achievement-related functionality.
    
    This engine handles:
    - Achievement definitions for all categories
    - Milestone detection and progress tracking
    - Achievement unlocking and badge awarding
    - Progress calculation and validation
    """

    def __init__(self, db: Session):
        self.db = db
        self._achievement_definitions = None

    def initialize_achievements(self) -> bool:
        """
        Initialize all achievement definitions in the database.
        This should be called during system setup or migration.
        """
        try:
            logger.info("Initializing achievement definitions...")
            
            # Get all achievement definitions
            definitions = self._get_achievement_definitions()
            
            # Create or update achievements in database
            for definition in definitions:
                existing = self.db.query(Achievement).filter(
                    Achievement.achievement_id == definition["achievement_id"]
                ).first()
                
                if existing:
                    # Update existing achievement
                    existing.name = definition["name"]
                    existing.description = definition["description"]
                    existing.category = definition["category"]
                    existing.difficulty = definition["difficulty"]
                    existing.requirements = definition["requirements"]
                    existing.reward_xp = definition["reward_xp"]
                    existing.reward_badge_url = definition.get("reward_badge_url")
                    existing.is_hidden = definition.get("is_hidden", False)
                    existing.is_active = definition.get("is_active", True)
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    # Create new achievement
                    achievement = Achievement(
                        achievement_id=definition["achievement_id"],
                        name=definition["name"],
                        description=definition["description"],
                        category=definition["category"],
                        difficulty=definition["difficulty"],
                        requirements=definition["requirements"],
                        reward_xp=definition["reward_xp"],
                        reward_badge_url=definition.get("reward_badge_url"),
                        is_hidden=definition.get("is_hidden", False),
                        is_active=definition.get("is_active", True)
                    )
                    self.db.add(achievement)
            
            self.db.commit()
            logger.info(f"Successfully initialized {len(definitions)} achievements")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing achievements: {str(e)}")
            self.db.rollback()
            return False

    async def check_achievements(
        self, 
        profile: UserGamificationProfile, 
        event: FinancialEvent
    ) -> List[AchievementResponse]:
        """
        Check if any achievements should be unlocked based on the financial event.
        Returns a list of newly unlocked achievements.
        """
        try:
            unlocked_achievements = []
            
            # Get all active achievements that the user hasn't completed
            from sqlalchemy import select

            completed_achievement_ids = self.db.query(UserAchievement.achievement_id).filter(
                and_(
                    UserAchievement.profile_id == profile.id,
                    UserAchievement.is_completed == True
                )
            ).subquery()
            
            available_achievements = self.db.query(Achievement).filter(
                and_(
                    Achievement.is_active == True,
                    ~Achievement.id.in_(select(completed_achievement_ids.c.achievement_id))
                )
            ).all()
            
            # Check each achievement for completion
            for achievement in available_achievements:
                if await self._check_achievement_completion(profile, achievement, event):
                    # Unlock the achievement
                    unlocked_achievement = await self._unlock_achievement(profile, achievement)
                    if unlocked_achievement:
                        unlocked_achievements.append(unlocked_achievement)
            
            return unlocked_achievements
            
        except Exception as e:
            logger.error(f"Error checking achievements for user {profile.user_id}: {str(e)}")
            return []

    async def get_user_achievements(
        self, 
        profile_id: int, 
        category: Optional[AchievementCategory] = None,
        completed_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all achievements for a user, optionally filtered by category or completion status.
        """
        try:
            query = self.db.query(UserAchievement, Achievement).join(
                Achievement, UserAchievement.achievement_id == Achievement.id
            ).filter(UserAchievement.profile_id == profile_id)
            
            if category:
                query = query.filter(Achievement.category == category)
            
            if completed_only:
                query = query.filter(UserAchievement.is_completed == True)
            
            results = query.order_by(
                desc(UserAchievement.is_completed),
                Achievement.difficulty,
                Achievement.created_at
            ).all()
            
            achievements = []
            for user_achievement, achievement in results:
                achievements.append({
                    "id": user_achievement.id,
                    "achievement": AchievementResponse.model_validate(achievement),
                    "progress": user_achievement.progress,
                    "is_completed": user_achievement.is_completed,
                    "unlocked_at": user_achievement.unlocked_at,
                    "created_at": user_achievement.created_at,
                    "updated_at": user_achievement.updated_at
                })
            
            return achievements
            
        except Exception as e:
            logger.error(f"Error getting user achievements for profile {profile_id}: {str(e)}")
            return []

    async def get_achievement_progress(
        self, 
        profile: UserGamificationProfile, 
        achievement_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed progress information for a specific achievement.
        """
        try:
            achievement = self.db.query(Achievement).filter(
                Achievement.achievement_id == achievement_id
            ).first()
            
            if not achievement:
                return None
            
            user_achievement = self.db.query(UserAchievement).filter(
                and_(
                    UserAchievement.profile_id == profile.id,
                    UserAchievement.achievement_id == achievement.id
                )
            ).first()
            
            # Calculate current progress
            progress = await self._calculate_achievement_progress(profile, achievement)
            
            return {
                "achievement": AchievementResponse.model_validate(achievement),
                "current_progress": progress,
                "user_achievement": user_achievement,
                "requirements_status": await self._get_requirements_status(profile, achievement)
            }
            
        except Exception as e:
            logger.error(f"Error getting achievement progress: {str(e)}")
            return None

    async def get_milestone_achievements(self, category: AchievementCategory) -> List[AchievementResponse]:
        """
        Get all milestone achievements for a specific category.
        """
        try:
            achievements = self.db.query(Achievement).filter(
                and_(
                    Achievement.category == category,
                    Achievement.is_active == True
                )
            ).order_by(Achievement.difficulty, Achievement.created_at).all()
            
            return [AchievementResponse.model_validate(achievement) for achievement in achievements]
            
        except Exception as e:
            logger.error(f"Error getting milestone achievements for category {category}: {str(e)}")
            return []

    # Private helper methods
    async def _check_achievement_completion(
        self, 
        profile: UserGamificationProfile, 
        achievement: Achievement, 
        event: FinancialEvent
    ) -> bool:
        """
        Check if an achievement should be completed based on current user data.
        """
        try:
            # Calculate current progress
            progress = await self._calculate_achievement_progress(profile, achievement)
            
            # Check if achievement is complete (100% progress)
            return progress >= 100.0
            
        except Exception as e:
            logger.error(f"Error checking achievement completion: {str(e)}")
            return False

    async def _calculate_achievement_progress(
        self, 
        profile: UserGamificationProfile, 
        achievement: Achievement
    ) -> float:
        """
        Calculate the current progress percentage for an achievement.
        """
        try:
            requirements = achievement.requirements
            if not requirements:
                return 0.0
            
            # Handle different requirement types
            for requirement in requirements:
                req_type = requirement.get("type")
                target = requirement.get("target", 0)
                
                if req_type == "expense_count":
                    current = profile.statistics.get("expensesTracked", 0)
                    return min((current / target) * 100.0, 100.0)
                
                elif req_type == "invoice_count":
                    current = profile.statistics.get("invoicesCreated", 0)
                    return min((current / target) * 100.0, 100.0)
                
                elif req_type == "receipt_count":
                    current = profile.statistics.get("receiptsUploaded", 0)
                    return min((current / target) * 100.0, 100.0)
                
                elif req_type == "budget_review_count":
                    current = profile.statistics.get("budgetReviews", 0)
                    return min((current / target) * 100.0, 100.0)
                
                elif req_type == "streak_length":
                    habit_type = requirement.get("habit_type")
                    if habit_type:
                        streak = self.db.query(UserStreak).filter(
                            and_(
                                UserStreak.profile_id == profile.id,
                                UserStreak.habit_type == habit_type
                            )
                        ).first()
                        
                        if streak:
                            current = max(streak.current_length, streak.longest_length)
                            return min((current / target) * 100.0, 100.0)
                
                elif req_type == "total_xp":
                    current = profile.total_experience_points
                    return min((current / target) * 100.0, 100.0)
                
                elif req_type == "level_reached":
                    current = profile.level
                    return 100.0 if current >= target else 0.0
                
                elif req_type == "financial_health_score":
                    current = profile.financial_health_score
                    return min((current / target) * 100.0, 100.0)
                
                elif req_type == "consecutive_days":
                    # Check for consecutive days of activity
                    days_active = await self._count_consecutive_active_days(profile)
                    return min((days_active / target) * 100.0, 100.0)
                
                elif req_type == "perfect_week":
                    # Check if user completed all daily tasks for a week
                    perfect_weeks = await self._count_perfect_weeks(profile)
                    return min((perfect_weeks / target) * 100.0, 100.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating achievement progress: {str(e)}")
            return 0.0

    async def _unlock_achievement(
        self, 
        profile: UserGamificationProfile, 
        achievement: Achievement
    ) -> Optional[AchievementResponse]:
        """
        Unlock an achievement for a user and award the badge.
        """
        try:
            # Check if user already has this achievement
            existing = self.db.query(UserAchievement).filter(
                and_(
                    UserAchievement.profile_id == profile.id,
                    UserAchievement.achievement_id == achievement.id
                )
            ).first()
            
            if existing and existing.is_completed:
                return None  # Already unlocked
            
            if existing:
                # Update existing record
                existing.progress = 100.0
                existing.is_completed = True
                existing.unlocked_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Create new achievement record
                user_achievement = UserAchievement(
                    profile_id=profile.id,
                    achievement_id=achievement.id,
                    progress=100.0,
                    is_completed=True,
                    unlocked_at=datetime.now(timezone.utc)
                )
                self.db.add(user_achievement)
            
            # Update user statistics
            stats = profile.statistics.copy() if profile.statistics else {}
            stats["achievementsUnlocked"] = stats.get("achievementsUnlocked", 0) + 1
            profile.statistics = stats
            # Mark statistics field as dirty for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(profile, "statistics")
            
            # Award XP for the achievement
            profile.total_experience_points += achievement.reward_xp
            
            self.db.commit()
            
            logger.info(f"Achievement '{achievement.name}' unlocked for user {profile.user_id}")
            return AchievementResponse.model_validate(achievement)
            
        except Exception as e:
            logger.error(f"Error unlocking achievement: {str(e)}")
            self.db.rollback()
            return None

    async def _get_requirements_status(
        self, 
        profile: UserGamificationProfile, 
        achievement: Achievement
    ) -> List[Dict[str, Any]]:
        """
        Get detailed status for each requirement of an achievement.
        """
        try:
            requirements_status = []
            
            for requirement in achievement.requirements:
                req_type = requirement.get("type")
                target = requirement.get("target", 0)
                current = 0
                
                if req_type == "expense_count":
                    current = profile.statistics.get("expensesTracked", 0)
                elif req_type == "invoice_count":
                    current = profile.statistics.get("invoicesCreated", 0)
                elif req_type == "receipt_count":
                    current = profile.statistics.get("receiptsUploaded", 0)
                elif req_type == "budget_review_count":
                    current = profile.statistics.get("budgetReviews", 0)
                elif req_type == "total_xp":
                    current = profile.total_experience_points
                elif req_type == "level_reached":
                    current = profile.level
                elif req_type == "financial_health_score":
                    current = profile.financial_health_score
                elif req_type == "streak_length":
                    habit_type = requirement.get("habit_type")
                    if habit_type:
                        streak = self.db.query(UserStreak).filter(
                            and_(
                                UserStreak.profile_id == profile.id,
                                UserStreak.habit_type == habit_type
                            )
                        ).first()
                        if streak:
                            current = max(streak.current_length, streak.longest_length)
                
                requirements_status.append({
                    "type": req_type,
                    "target": target,
                    "current": current,
                    "completed": current >= target,
                    "progress_percentage": min((current / target) * 100.0, 100.0) if target > 0 else 0.0
                })
            
            return requirements_status
            
        except Exception as e:
            logger.error(f"Error getting requirements status: {str(e)}")
            return []

    async def _count_consecutive_active_days(self, profile: UserGamificationProfile) -> int:
        """
        Count consecutive days of financial activity.
        """
        try:
            # Get point history for the last 30 days
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            point_history = self.db.query(PointHistory).filter(
                and_(
                    PointHistory.profile_id == profile.id,
                    PointHistory.created_at >= thirty_days_ago
                )
            ).order_by(desc(PointHistory.created_at)).all()
            
            if not point_history:
                return 0
            
            # Group by date and count consecutive days
            active_dates = set()
            for record in point_history:
                active_dates.add(record.created_at.date())
            
            # Count consecutive days from today backwards
            consecutive_days = 0
            current_date = datetime.now(timezone.utc).date()
            
            while current_date in active_dates:
                consecutive_days += 1
                current_date -= timedelta(days=1)
            
            return consecutive_days
            
        except Exception as e:
            logger.error(f"Error counting consecutive active days: {str(e)}")
            return 0

    async def _count_perfect_weeks(self, profile: UserGamificationProfile) -> int:
        """
        Count weeks where user completed all daily financial tasks.
        """
        try:
            # This is a simplified implementation
            # In a full implementation, this would check for specific daily tasks completion
            
            # Get streak data for daily expense tracking
            expense_streak = self.db.query(UserStreak).filter(
                and_(
                    UserStreak.profile_id == profile.id,
                    UserStreak.habit_type == HabitType.DAILY_EXPENSE_TRACKING
                )
            ).first()
            
            if not expense_streak:
                return 0
            
            # Estimate perfect weeks based on longest streak
            # A perfect week requires 7 consecutive days
            return expense_streak.longest_length // 7
            
        except Exception as e:
            logger.error(f"Error counting perfect weeks: {str(e)}")
            return 0

    def _get_achievement_definitions(self) -> List[Dict[str, Any]]:
        """
        Get all achievement definitions organized by category.
        This defines all achievements available in the system.
        """
        if self._achievement_definitions is not None:
            return self._achievement_definitions
        
        definitions = []
        
        # Expense Tracking Achievements (Requirements 2.5, 5.1)
        definitions.extend([
            {
                "achievement_id": "expense_tracker_first",
                "name": "First Steps",
                "description": "Track your first expense",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "expense_count", "target": 1}],
                "reward_xp": 50,
                "reward_badge_url": "/badges/first_expense.png"
            },
            {
                "achievement_id": "expense_tracker_10",
                "name": "Getting Started",
                "description": "Track 10 expenses",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "expense_count", "target": 10}],
                "reward_xp": 100,
                "reward_badge_url": "/badges/expense_10.png"
            },
            {
                "achievement_id": "expense_tracker_50",
                "name": "Expense Enthusiast",
                "description": "Track 50 expenses",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "expense_count", "target": 50}],
                "reward_xp": 250,
                "reward_badge_url": "/badges/expense_50.png"
            },
            {
                "achievement_id": "expense_tracker_100",
                "name": "Expense Expert",
                "description": "Track 100 expenses",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.GOLD,
                "requirements": [{"type": "expense_count", "target": 100}],
                "reward_xp": 500,
                "reward_badge_url": "/badges/expense_100.png"
            },
            {
                "achievement_id": "expense_tracker_500",
                "name": "Expense Master",
                "description": "Track 500 expenses",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.PLATINUM,
                "requirements": [{"type": "expense_count", "target": 500}],
                "reward_xp": 1000,
                "reward_badge_url": "/badges/expense_500.png"
            },
            {
                "achievement_id": "receipt_collector_10",
                "name": "Receipt Collector",
                "description": "Upload 10 receipt photos",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "receipt_count", "target": 10}],
                "reward_xp": 75,
                "reward_badge_url": "/badges/receipt_10.png"
            },
            {
                "achievement_id": "receipt_collector_50",
                "name": "Receipt Archivist",
                "description": "Upload 50 receipt photos",
                "category": AchievementCategory.EXPENSE_TRACKING,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "receipt_count", "target": 50}],
                "reward_xp": 200,
                "reward_badge_url": "/badges/receipt_50.png"
            }
        ])
        
        # Invoice Management Achievements (Requirements 3.5, 5.2)
        definitions.extend([
            {
                "achievement_id": "invoice_creator_first",
                "name": "First Invoice",
                "description": "Create your first invoice",
                "category": AchievementCategory.INVOICE_MANAGEMENT,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "invoice_count", "target": 1}],
                "reward_xp": 75,
                "reward_badge_url": "/badges/first_invoice.png"
            },
            {
                "achievement_id": "invoice_creator_10",
                "name": "Invoice Professional",
                "description": "Create 10 invoices",
                "category": AchievementCategory.INVOICE_MANAGEMENT,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "invoice_count", "target": 10}],
                "reward_xp": 300,
                "reward_badge_url": "/badges/invoice_10.png"
            },
            {
                "achievement_id": "invoice_creator_100",
                "name": "Invoice Expert",
                "description": "Create 100 invoices",
                "category": AchievementCategory.INVOICE_MANAGEMENT,
                "difficulty": AchievementDifficulty.GOLD,
                "requirements": [{"type": "invoice_count", "target": 100}],
                "reward_xp": 750,
                "reward_badge_url": "/badges/invoice_100.png"
            }
        ])
        
        # Habit Formation Achievements (Requirements 4.5, 5.4)
        definitions.extend([
            {
                "achievement_id": "streak_warrior_7",
                "name": "Week Warrior",
                "description": "Maintain a 7-day expense tracking streak",
                "category": AchievementCategory.HABIT_FORMATION,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "streak_length", "target": 7, "habit_type": "daily_expense_tracking"}],
                "reward_xp": 150,
                "reward_badge_url": "/badges/streak_7.png"
            },
            {
                "achievement_id": "streak_warrior_30",
                "name": "Month Master",
                "description": "Maintain a 30-day expense tracking streak",
                "category": AchievementCategory.HABIT_FORMATION,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "streak_length", "target": 30, "habit_type": "daily_expense_tracking"}],
                "reward_xp": 500,
                "reward_badge_url": "/badges/streak_30.png"
            },
            {
                "achievement_id": "streak_warrior_90",
                "name": "Quarter Champion",
                "description": "Maintain a 90-day expense tracking streak",
                "category": AchievementCategory.HABIT_FORMATION,
                "difficulty": AchievementDifficulty.GOLD,
                "requirements": [{"type": "streak_length", "target": 90, "habit_type": "daily_expense_tracking"}],
                "reward_xp": 1200,
                "reward_badge_url": "/badges/streak_90.png"
            },
            {
                "achievement_id": "streak_warrior_365",
                "name": "Year Legend",
                "description": "Maintain a 365-day expense tracking streak",
                "category": AchievementCategory.HABIT_FORMATION,
                "difficulty": AchievementDifficulty.PLATINUM,
                "requirements": [{"type": "streak_length", "target": 365, "habit_type": "daily_expense_tracking"}],
                "reward_xp": 3000,
                "reward_badge_url": "/badges/streak_365.png"
            },
            {
                "achievement_id": "perfect_week",
                "name": "Perfect Week",
                "description": "Complete all daily financial tasks for a full week",
                "category": AchievementCategory.HABIT_FORMATION,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "perfect_week", "target": 1}],
                "reward_xp": 300,
                "reward_badge_url": "/badges/perfect_week.png"
            },
            {
                "achievement_id": "budget_reviewer_5",
                "name": "Budget Conscious",
                "description": "Review your budget 5 times",
                "category": AchievementCategory.HABIT_FORMATION,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "budget_review_count", "target": 5}],
                "reward_xp": 125,
                "reward_badge_url": "/badges/budget_5.png"
            }
        ])
        
        # Financial Health Achievements (Requirements 5.3)
        definitions.extend([
            {
                "achievement_id": "health_score_50",
                "name": "Getting Healthier",
                "description": "Reach a financial health score of 50",
                "category": AchievementCategory.FINANCIAL_HEALTH,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "financial_health_score", "target": 50}],
                "reward_xp": 200,
                "reward_badge_url": "/badges/health_50.png"
            },
            {
                "achievement_id": "health_score_75",
                "name": "Financially Fit",
                "description": "Reach a financial health score of 75",
                "category": AchievementCategory.FINANCIAL_HEALTH,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "financial_health_score", "target": 75}],
                "reward_xp": 400,
                "reward_badge_url": "/badges/health_75.png"
            },
            {
                "achievement_id": "health_score_90",
                "name": "Financial Guru",
                "description": "Reach a financial health score of 90",
                "category": AchievementCategory.FINANCIAL_HEALTH,
                "difficulty": AchievementDifficulty.GOLD,
                "requirements": [{"type": "financial_health_score", "target": 90}],
                "reward_xp": 750,
                "reward_badge_url": "/badges/health_90.png"
            }
        ])
        
        # Exploration Achievements (Requirements 5.5)
        definitions.extend([
            {
                "achievement_id": "level_explorer_5",
                "name": "Rising Star",
                "description": "Reach level 5",
                "category": AchievementCategory.EXPLORATION,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "level_reached", "target": 5}],
                "reward_xp": 100,
                "reward_badge_url": "/badges/level_5.png"
            },
            {
                "achievement_id": "level_explorer_10",
                "name": "Experienced User",
                "description": "Reach level 10",
                "category": AchievementCategory.EXPLORATION,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "level_reached", "target": 10}],
                "reward_xp": 250,
                "reward_badge_url": "/badges/level_10.png"
            },
            {
                "achievement_id": "level_explorer_25",
                "name": "Finance Veteran",
                "description": "Reach level 25",
                "category": AchievementCategory.EXPLORATION,
                "difficulty": AchievementDifficulty.GOLD,
                "requirements": [{"type": "level_reached", "target": 25}],
                "reward_xp": 500,
                "reward_badge_url": "/badges/level_25.png"
            },
            {
                "achievement_id": "xp_collector_1000",
                "name": "Point Collector",
                "description": "Earn 1,000 experience points",
                "category": AchievementCategory.EXPLORATION,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "total_xp", "target": 1000}],
                "reward_xp": 100,
                "reward_badge_url": "/badges/xp_1000.png"
            },
            {
                "achievement_id": "xp_collector_5000",
                "name": "Point Enthusiast",
                "description": "Earn 5,000 experience points",
                "category": AchievementCategory.EXPLORATION,
                "difficulty": AchievementDifficulty.SILVER,
                "requirements": [{"type": "total_xp", "target": 5000}],
                "reward_xp": 250,
                "reward_badge_url": "/badges/xp_5000.png"
            },
            {
                "achievement_id": "consecutive_days_7",
                "name": "Daily Dedication",
                "description": "Be active for 7 consecutive days",
                "category": AchievementCategory.EXPLORATION,
                "difficulty": AchievementDifficulty.BRONZE,
                "requirements": [{"type": "consecutive_days", "target": 7}],
                "reward_xp": 150,
                "reward_badge_url": "/badges/consecutive_7.png"
            }
        ])
        
        self._achievement_definitions = definitions
        return definitions