"""
Challenge management service for the gamification system.

This service handles challenge creation, management, progress tracking,
and completion detection for the finance application gamification system.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from core.models.gamification import (
    Challenge,
    UserChallenge,
    UserGamificationProfile,
    ChallengeType,
    PointHistory
)
from core.schemas.gamification import (
    ChallengeCreate,
    ChallengeResponse,
    UserChallengeResponse,
    ChallengeRequirement,
    FinancialEvent,
    ActionType
)

logger = logging.getLogger(__name__)


class ChallengeManager:
    """
    Service for managing challenges in the gamification system.
    
    This service handles:
    - Creating and managing challenge templates
    - Tracking user participation in challenges
    - Monitoring challenge progress
    - Detecting challenge completion and awarding rewards
    """

    def __init__(self, db: Session):
        self.db = db

    # Challenge Template Management
    async def create_challenge_template(self, challenge_data: ChallengeCreate) -> ChallengeResponse:
        """Create a new challenge template"""
        try:
            challenge = Challenge(
                challenge_id=challenge_data.challenge_id,
                name=challenge_data.name,
                description=challenge_data.description,
                challenge_type=challenge_data.challenge_type,
                duration_days=challenge_data.duration_days,
                requirements=[req.dict() for req in challenge_data.requirements],
                reward_xp=challenge_data.reward_xp,
                reward_badge_url=challenge_data.reward_badge_url,
                start_date=challenge_data.start_date,
                end_date=challenge_data.end_date,
                organization_id=challenge_data.organization_id,
                is_active=True
            )
            
            self.db.add(challenge)
            self.db.commit()
            self.db.refresh(challenge)
            
            logger.info(f"Created challenge template: {challenge.challenge_id}")
            return ChallengeResponse.model_validate(challenge)
            
        except Exception as e:
            logger.error(f"Error creating challenge template: {str(e)}")
            self.db.rollback()
            raise

    async def get_available_challenges(
        self, 
        user_id: int, 
        challenge_type: Optional[ChallengeType] = None,
        organization_id: Optional[int] = None
    ) -> List[ChallengeResponse]:
        """Get all available challenges for a user"""
        try:
            now = datetime.now(timezone.utc)
            
            # Base query for active challenges
            query = self.db.query(Challenge).filter(
                Challenge.is_active == True
            )
            
            # Filter by type if specified
            if challenge_type:
                query = query.filter(Challenge.challenge_type == challenge_type)
            
            # Filter by organization (include system-wide challenges)
            if organization_id:
                query = query.filter(
                    or_(
                        Challenge.organization_id == organization_id,
                        Challenge.organization_id.is_(None)
                    )
                )
            else:
                query = query.filter(Challenge.organization_id.is_(None))
            
            # Filter by date availability
            query = query.filter(
                or_(
                    Challenge.start_date.is_(None),
                    Challenge.start_date <= now
                )
            ).filter(
                or_(
                    Challenge.end_date.is_(None),
                    Challenge.end_date >= now
                )
            )
            
            challenges = query.all()
            return [ChallengeResponse.model_validate(challenge) for challenge in challenges]
            
        except Exception as e:
            logger.error(f"Error getting available challenges for user {user_id}: {str(e)}")
            return []

    async def get_weekly_challenges(self, organization_id: Optional[int] = None) -> List[ChallengeResponse]:
        """Get weekly challenges that are currently active"""
        try:
            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=now.weekday())
            week_end = week_start + timedelta(days=7)
            
            query = self.db.query(Challenge).filter(
                and_(
                    Challenge.is_active == True,
                    Challenge.challenge_type == ChallengeType.PERSONAL,
                    Challenge.duration_days <= 7,
                    or_(
                        Challenge.start_date.is_(None),
                        Challenge.start_date <= week_end
                    ),
                    or_(
                        Challenge.end_date.is_(None),
                        Challenge.end_date >= week_start
                    )
                )
            )
            
            # Filter by organization
            if organization_id:
                query = query.filter(
                    or_(
                        Challenge.organization_id == organization_id,
                        Challenge.organization_id.is_(None)
                    )
                )
            else:
                query = query.filter(Challenge.organization_id.is_(None))
            
            challenges = query.all()
            return [ChallengeResponse.model_validate(challenge) for challenge in challenges]
            
        except Exception as e:
            logger.error(f"Error getting weekly challenges: {str(e)}")
            return []

    async def get_monthly_challenges(self, organization_id: Optional[int] = None) -> List[ChallengeResponse]:
        """Get monthly challenges that are currently active"""
        try:
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1)
            next_month = month_start.replace(month=month_start.month + 1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1)
            
            query = self.db.query(Challenge).filter(
                and_(
                    Challenge.is_active == True,
                    Challenge.challenge_type.in_([ChallengeType.PERSONAL, ChallengeType.COMMUNITY]),
                    Challenge.duration_days > 7,
                    or_(
                        Challenge.start_date.is_(None),
                        Challenge.start_date <= next_month
                    ),
                    or_(
                        Challenge.end_date.is_(None),
                        Challenge.end_date >= month_start
                    )
                )
            )
            
            # Filter by organization
            if organization_id:
                query = query.filter(
                    or_(
                        Challenge.organization_id == organization_id,
                        Challenge.organization_id.is_(None)
                    )
                )
            else:
                query = query.filter(Challenge.organization_id.is_(None))
            
            challenges = query.all()
            return [ChallengeResponse.model_validate(challenge) for challenge in challenges]
            
        except Exception as e:
            logger.error(f"Error getting monthly challenges: {str(e)}")
            return []

    # User Challenge Participation
    async def opt_into_challenge(self, user_id: int, challenge_id: int) -> Optional[UserChallengeResponse]:
        """Opt a user into a challenge"""
        try:
            # Get user profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile or not profile.module_enabled:
                logger.warning(f"Gamification not enabled for user {user_id}")
                return None
            
            # Check if challenge exists and is active
            challenge = self.db.query(Challenge).filter(
                and_(
                    Challenge.id == challenge_id,
                    Challenge.is_active == True
                )
            ).first()
            
            if not challenge:
                logger.warning(f"Challenge {challenge_id} not found or inactive")
                return None
            
            # Check if user is already participating
            existing = self.db.query(UserChallenge).filter(
                and_(
                    UserChallenge.profile_id == profile.id,
                    UserChallenge.challenge_id == challenge_id
                )
            ).first()
            
            if existing:
                # Update opt-in status if they previously opted out
                existing.opted_in = True
                existing.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(existing)
                return UserChallengeResponse.model_validate(existing)
            
            # Create new participation record
            user_challenge = UserChallenge(
                profile_id=profile.id,
                challenge_id=challenge_id,
                progress=0.0,
                is_completed=False,
                opted_in=True,
                started_at=datetime.now(timezone.utc),
                milestones=[]
            )
            
            self.db.add(user_challenge)
            self.db.commit()
            self.db.refresh(user_challenge)
            
            logger.info(f"User {user_id} opted into challenge {challenge_id}")
            return UserChallengeResponse.model_validate(user_challenge)
            
        except Exception as e:
            logger.error(f"Error opting user {user_id} into challenge {challenge_id}: {str(e)}")
            self.db.rollback()
            return None

    async def opt_out_of_challenge(self, user_id: int, challenge_id: int) -> bool:
        """Opt a user out of a challenge"""
        try:
            # Get user profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return False
            
            # Find user challenge participation
            user_challenge = self.db.query(UserChallenge).filter(
                and_(
                    UserChallenge.profile_id == profile.id,
                    UserChallenge.challenge_id == challenge_id
                )
            ).first()
            
            if not user_challenge:
                return True  # Already not participating
            
            user_challenge.opted_in = False
            user_challenge.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            
            logger.info(f"User {user_id} opted out of challenge {challenge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error opting user {user_id} out of challenge {challenge_id}: {str(e)}")
            self.db.rollback()
            return False

    async def get_user_challenges(
        self, 
        user_id: int, 
        active_only: bool = True,
        completed_only: bool = False
    ) -> List[UserChallengeResponse]:
        """Get all challenges for a user"""
        try:
            # Get user profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile or not profile.module_enabled:
                return []
            
            query = self.db.query(UserChallenge).filter(
                UserChallenge.profile_id == profile.id
            )
            
            if active_only:
                query = query.filter(
                    and_(
                        UserChallenge.opted_in == True,
                        UserChallenge.is_completed == False
                    )
                )
            
            if completed_only:
                query = query.filter(UserChallenge.is_completed == True)
            
            user_challenges = query.order_by(desc(UserChallenge.started_at)).all()
            return [UserChallengeResponse.model_validate(uc) for uc in user_challenges]
            
        except Exception as e:
            logger.error(f"Error getting user challenges for user {user_id}: {str(e)}")
            return []

    # Challenge Progress Tracking
    async def update_challenge_progress_from_event(self, event: FinancialEvent) -> List[Dict[str, Any]]:
        """Update challenge progress based on a financial event"""
        try:
            # Get user profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == event.user_id
            ).first()
            
            if not profile or not profile.module_enabled:
                return []
            
            # Get active user challenges
            active_challenges = self.db.query(UserChallenge).filter(
                and_(
                    UserChallenge.profile_id == profile.id,
                    UserChallenge.opted_in == True,
                    UserChallenge.is_completed == False
                )
            ).all()
            
            updated_challenges = []
            
            for user_challenge in active_challenges:
                challenge = user_challenge.challenge
                
                # Check if this event contributes to the challenge
                progress_made = await self._calculate_progress_from_event(
                    challenge, user_challenge, event
                )
                
                if progress_made > 0:
                    old_progress = user_challenge.progress
                    user_challenge.progress = min(user_challenge.progress + progress_made, 100.0)
                    user_challenge.updated_at = datetime.now(timezone.utc)
                    
                    # Check for completion
                    if user_challenge.progress >= 100.0 and not user_challenge.is_completed:
                        await self._complete_challenge(user_challenge, profile)
                    
                    # Check for milestones
                    await self._check_challenge_milestones(user_challenge, old_progress)
                    
                    updated_challenges.append({
                        "challenge_id": challenge.challenge_id,
                        "challenge_name": challenge.name,
                        "old_progress": old_progress,
                        "new_progress": user_challenge.progress,
                        "progress_made": progress_made,
                        "completed": user_challenge.is_completed
                    })
            
            if updated_challenges:
                self.db.commit()
                logger.info(f"Updated {len(updated_challenges)} challenges for user {event.user_id}")
            
            return updated_challenges
            
        except Exception as e:
            logger.error(f"Error updating challenge progress from event: {str(e)}")
            self.db.rollback()
            return []

    async def get_challenge_progress(self, user_id: int, challenge_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed progress information for a specific challenge"""
        try:
            # Get user profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return None
            
            # Get user challenge
            user_challenge = self.db.query(UserChallenge).filter(
                and_(
                    UserChallenge.profile_id == profile.id,
                    UserChallenge.challenge_id == challenge_id
                )
            ).first()
            
            if not user_challenge:
                return None
            
            challenge = user_challenge.challenge
            
            # Calculate detailed progress
            progress_details = await self._calculate_detailed_progress(user_challenge)
            
            return {
                "challenge_id": challenge.challenge_id,
                "challenge_name": challenge.name,
                "description": challenge.description,
                "challenge_type": challenge.challenge_type.value,
                "duration_days": challenge.duration_days,
                "requirements": challenge.requirements,
                "progress": user_challenge.progress,
                "is_completed": user_challenge.is_completed,
                "opted_in": user_challenge.opted_in,
                "started_at": user_challenge.started_at,
                "completed_at": user_challenge.completed_at,
                "milestones": user_challenge.milestones,
                "progress_details": progress_details,
                "time_remaining": await self._calculate_time_remaining(user_challenge),
                "reward_xp": challenge.reward_xp,
                "reward_badge_url": challenge.reward_badge_url
            }
            
        except Exception as e:
            logger.error(f"Error getting challenge progress for user {user_id}: {str(e)}")
            return None

    # Challenge Completion and Rewards
    async def complete_challenge(self, user_id: int, challenge_id: int) -> Optional[Dict[str, Any]]:
        """Manually complete a challenge (for testing or admin purposes)"""
        try:
            # Get user profile
            profile = self.db.query(UserGamificationProfile).filter(
                UserGamificationProfile.user_id == user_id
            ).first()
            
            if not profile:
                return None
            
            # Get user challenge
            user_challenge = self.db.query(UserChallenge).filter(
                and_(
                    UserChallenge.profile_id == profile.id,
                    UserChallenge.challenge_id == challenge_id
                )
            ).first()
            
            if not user_challenge or user_challenge.is_completed:
                return None
            
            # Complete the challenge
            completion_result = await self._complete_challenge(user_challenge, profile)
            
            self.db.commit()
            
            return completion_result
            
        except Exception as e:
            logger.error(f"Error completing challenge for user {user_id}: {str(e)}")
            self.db.rollback()
            return None

    # Initialize Default Challenges
    async def initialize_default_challenges(self) -> bool:
        """Initialize default challenge templates"""
        try:
            default_challenges = await self._get_default_challenge_templates()
            
            for challenge_data in default_challenges:
                # Check if challenge already exists
                existing = self.db.query(Challenge).filter(
                    Challenge.challenge_id == challenge_data["challenge_id"]
                ).first()
                
                if not existing:
                    challenge = Challenge(**challenge_data)
                    self.db.add(challenge)
            
            self.db.commit()
            logger.info(f"Initialized {len(default_challenges)} default challenges")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing default challenges: {str(e)}")
            self.db.rollback()
            return False

    # Private Helper Methods
    async def _calculate_progress_from_event(
        self, 
        challenge: Challenge, 
        user_challenge: UserChallenge, 
        event: FinancialEvent
    ) -> float:
        """Calculate how much progress an event contributes to a challenge"""
        try:
            progress_made = 0.0
            
            for requirement in challenge.requirements:
                req_type = requirement.get("type")
                req_target = requirement.get("target", 1)
                req_period = requirement.get("period", "total")
                
                # Check if this event matches the requirement type
                if self._event_matches_requirement(event, req_type):
                    # Calculate progress based on period
                    if req_period == "total":
                        # Simple increment towards total target
                        progress_made += (100.0 / req_target)
                    elif req_period == "daily":
                        # Check if this is the first qualifying event today
                        if await self._is_first_event_today(user_challenge, event, req_type):
                            progress_made += (100.0 / req_target)
                    elif req_period == "weekly":
                        # Check if this is the first qualifying event this week
                        if await self._is_first_event_this_week(user_challenge, event, req_type):
                            progress_made += (100.0 / req_target)
            
            return min(progress_made, 100.0 - user_challenge.progress)
            
        except Exception as e:
            logger.error(f"Error calculating progress from event: {str(e)}")
            return 0.0

    def _event_matches_requirement(self, event: FinancialEvent, req_type: str) -> bool:
        """Check if an event matches a challenge requirement type"""
        event_type_mapping = {
            "track_expenses": [ActionType.EXPENSE_ADDED],
            "create_invoices": [ActionType.INVOICE_CREATED],
            "upload_receipts": [ActionType.RECEIPT_UPLOADED],
            "review_budget": [ActionType.BUDGET_REVIEWED],
            "record_payments": [ActionType.PAYMENT_RECORDED],
            "categorize_expenses": [ActionType.CATEGORY_ASSIGNED],
            "any_financial_action": [
                ActionType.EXPENSE_ADDED,
                ActionType.INVOICE_CREATED,
                ActionType.RECEIPT_UPLOADED,
                ActionType.BUDGET_REVIEWED,
                ActionType.PAYMENT_RECORDED,
                ActionType.CATEGORY_ASSIGNED
            ]
        }
        
        matching_actions = event_type_mapping.get(req_type, [])
        return event.action_type in matching_actions

    async def _is_first_event_today(
        self, 
        user_challenge: UserChallenge, 
        event: FinancialEvent, 
        req_type: str
    ) -> bool:
        """Check if this is the first qualifying event today for this challenge"""
        try:
            today = event.timestamp.date()
            
            # Check point history for today
            from core.models.gamification import PointHistory
            
            existing_today = self.db.query(PointHistory).filter(
                and_(
                    PointHistory.profile_id == user_challenge.profile_id,
                    func.date(PointHistory.created_at) == today,
                    PointHistory.action_metadata.contains(f'"challenge_id": {user_challenge.challenge_id}'),
                    PointHistory.action_metadata.contains(f'"requirement_type": "{req_type}"')
                )
            ).first()
            
            return existing_today is None
            
        except Exception as e:
            logger.error(f"Error checking first event today: {str(e)}")
            return False

    async def _is_first_event_this_week(
        self, 
        user_challenge: UserChallenge, 
        event: FinancialEvent, 
        req_type: str
    ) -> bool:
        """Check if this is the first qualifying event this week for this challenge"""
        try:
            # Get start of week (Monday)
            event_date = event.timestamp.date()
            week_start = event_date - timedelta(days=event_date.weekday())
            
            # Check point history for this week
            from core.models.gamification import PointHistory
            
            existing_this_week = self.db.query(PointHistory).filter(
                and_(
                    PointHistory.profile_id == user_challenge.profile_id,
                    func.date(PointHistory.created_at) >= week_start,
                    PointHistory.action_metadata.contains(f'"challenge_id": {user_challenge.challenge_id}'),
                    PointHistory.action_metadata.contains(f'"requirement_type": "{req_type}"')
                )
            ).first()
            
            return existing_this_week is None
            
        except Exception as e:
            logger.error(f"Error checking first event this week: {str(e)}")
            return False

    async def _complete_challenge(
        self, 
        user_challenge: UserChallenge, 
        profile: UserGamificationProfile
    ) -> Dict[str, Any]:
        """Complete a challenge and award rewards"""
        try:
            challenge = user_challenge.challenge
            
            # Mark as completed
            user_challenge.is_completed = True
            user_challenge.completed_at = datetime.now(timezone.utc)
            user_challenge.progress = 100.0
            
            # Award XP
            if challenge.reward_xp > 0:
                profile.total_experience_points += challenge.reward_xp
            
            # Update statistics
            stats = profile.statistics or {}
            stats["challengesCompleted"] = stats.get("challengesCompleted", 0) + 1
            profile.statistics = stats
            
            # Record completion in point history
            from core.models.gamification import PointHistory
            
            completion_record = PointHistory(
                profile_id=profile.id,
                action_type="challenge_completed",
                points_awarded=challenge.reward_xp,
                base_points=challenge.reward_xp,
                streak_multiplier=1.0,
                accuracy_bonus=0,
                completeness_bonus=0,
                timeliness_bonus=0,
                action_metadata={
                    "challenge_id": challenge.id,
                    "challenge_name": challenge.name,
                    "challenge_type": challenge.challenge_type.value,
                    "completion_time": datetime.now(timezone.utc).isoformat()
                }
            )
            
            self.db.add(completion_record)
            
            logger.info(f"Completed challenge {challenge.challenge_id} for user {profile.user_id}")
            
            return {
                "challenge_id": challenge.challenge_id,
                "challenge_name": challenge.name,
                "reward_xp": challenge.reward_xp,
                "reward_badge_url": challenge.reward_badge_url,
                "completed_at": user_challenge.completed_at,
                "celebration_triggered": True
            }
            
        except Exception as e:
            logger.error(f"Error completing challenge: {str(e)}")
            raise

    async def _check_challenge_milestones(
        self, 
        user_challenge: UserChallenge, 
        old_progress: float
    ):
        """Check and record challenge milestones"""
        try:
            milestone_thresholds = [25.0, 50.0, 75.0]
            milestones = user_challenge.milestones or []
            
            for threshold in milestone_thresholds:
                if old_progress < threshold <= user_challenge.progress:
                    milestone = {
                        "threshold": threshold,
                        "achieved_at": datetime.now(timezone.utc).isoformat(),
                        "message": f"You're {int(threshold)}% of the way through this challenge!"
                    }
                    milestones.append(milestone)
            
            user_challenge.milestones = milestones
            
        except Exception as e:
            logger.error(f"Error checking challenge milestones: {str(e)}")

    async def _calculate_detailed_progress(self, user_challenge: UserChallenge) -> Dict[str, Any]:
        """Calculate detailed progress information for a challenge"""
        try:
            challenge = user_challenge.challenge
            progress_details = {
                "overall_progress": user_challenge.progress,
                "requirements_progress": []
            }
            
            for i, requirement in enumerate(challenge.requirements):
                req_progress = await self._calculate_requirement_progress(
                    user_challenge, requirement
                )
                
                progress_details["requirements_progress"].append({
                    "requirement_index": i,
                    "type": requirement.get("type"),
                    "target": requirement.get("target"),
                    "period": requirement.get("period", "total"),
                    "current_progress": req_progress.get("current", 0),
                    "percentage": req_progress.get("percentage", 0.0),
                    "description": req_progress.get("description", "")
                })
            
            return progress_details
            
        except Exception as e:
            logger.error(f"Error calculating detailed progress: {str(e)}")
            return {"overall_progress": user_challenge.progress, "requirements_progress": []}

    async def _calculate_requirement_progress(
        self, 
        user_challenge: UserChallenge, 
        requirement: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate progress for a specific requirement"""
        try:
            req_type = requirement.get("type")
            req_target = requirement.get("target", 1)
            req_period = requirement.get("period", "total")
            
            # This is a simplified implementation
            # In a full implementation, this would query the database for actual progress
            current_progress = int(user_challenge.progress * req_target / 100.0)
            
            return {
                "current": current_progress,
                "target": req_target,
                "percentage": (current_progress / req_target) * 100.0,
                "description": f"{current_progress}/{req_target} {req_type.replace('_', ' ')}"
            }
            
        except Exception as e:
            logger.error(f"Error calculating requirement progress: {str(e)}")
            return {"current": 0, "target": 1, "percentage": 0.0, "description": "Error calculating progress"}

    async def _calculate_time_remaining(self, user_challenge: UserChallenge) -> Optional[Dict[str, Any]]:
        """Calculate time remaining for a challenge"""
        try:
            challenge = user_challenge.challenge
            
            if challenge.end_date:
                now = datetime.now(timezone.utc)
                if challenge.end_date > now:
                    time_remaining = challenge.end_date - now
                    return {
                        "days": time_remaining.days,
                        "hours": time_remaining.seconds // 3600,
                        "minutes": (time_remaining.seconds % 3600) // 60,
                        "total_seconds": time_remaining.total_seconds()
                    }
                else:
                    return {
                        "days": 0,
                        "hours": 0,
                        "minutes": 0,
                        "total_seconds": 0,
                        "expired": True
                    }
            
            # Calculate based on duration from start date
            if user_challenge.started_at and challenge.duration_days:
                end_time = user_challenge.started_at + timedelta(days=challenge.duration_days)
                now = datetime.now(timezone.utc)
                
                if end_time > now:
                    time_remaining = end_time - now
                    return {
                        "days": time_remaining.days,
                        "hours": time_remaining.seconds // 3600,
                        "minutes": (time_remaining.seconds % 3600) // 60,
                        "total_seconds": time_remaining.total_seconds()
                    }
                else:
                    return {
                        "days": 0,
                        "hours": 0,
                        "minutes": 0,
                        "total_seconds": 0,
                        "expired": True
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating time remaining: {str(e)}")
            return None

    async def _get_default_challenge_templates(self) -> List[Dict[str, Any]]:
        """Get default challenge templates to initialize"""
        return [
            {
                "challenge_id": "weekly_expense_tracker",
                "name": "Weekly Expense Tracker",
                "description": "Track at least one expense every day for a week",
                "challenge_type": ChallengeType.PERSONAL,
                "duration_days": 7,
                "requirements": [
                    {
                        "type": "track_expenses",
                        "target": 7,
                        "period": "daily"
                    }
                ],
                "reward_xp": 100,
                "reward_badge_url": "/badges/weekly_tracker.png",
                "is_active": True
            },
            {
                "challenge_id": "invoice_master",
                "name": "Invoice Master",
                "description": "Create 10 invoices this month",
                "challenge_type": ChallengeType.PERSONAL,
                "duration_days": 30,
                "requirements": [
                    {
                        "type": "create_invoices",
                        "target": 10,
                        "period": "total"
                    }
                ],
                "reward_xp": 200,
                "reward_badge_url": "/badges/invoice_master.png",
                "is_active": True
            },
            {
                "challenge_id": "receipt_collector",
                "name": "Receipt Collector",
                "description": "Upload receipts for 20 expenses",
                "challenge_type": ChallengeType.PERSONAL,
                "duration_days": 14,
                "requirements": [
                    {
                        "type": "upload_receipts",
                        "target": 20,
                        "period": "total"
                    }
                ],
                "reward_xp": 150,
                "reward_badge_url": "/badges/receipt_collector.png",
                "is_active": True
            },
            {
                "challenge_id": "budget_reviewer",
                "name": "Budget Reviewer",
                "description": "Review your budget every week for a month",
                "challenge_type": ChallengeType.PERSONAL,
                "duration_days": 30,
                "requirements": [
                    {
                        "type": "review_budget",
                        "target": 4,
                        "period": "weekly"
                    }
                ],
                "reward_xp": 250,
                "reward_badge_url": "/badges/budget_reviewer.png",
                "is_active": True
            },
            {
                "challenge_id": "financial_organizer",
                "name": "Financial Organizer",
                "description": "Complete 50 financial actions this month",
                "challenge_type": ChallengeType.PERSONAL,
                "duration_days": 30,
                "requirements": [
                    {
                        "type": "any_financial_action",
                        "target": 50,
                        "period": "total"
                    }
                ],
                "reward_xp": 300,
                "reward_badge_url": "/badges/financial_organizer.png",
                "is_active": True
            },
            {
                "challenge_id": "monthly_consistency",
                "name": "Monthly Consistency",
                "description": "Track expenses every day for 30 days",
                "challenge_type": ChallengeType.COMMUNITY,
                "duration_days": 30,
                "requirements": [
                    {
                        "type": "track_expenses",
                        "target": 30,
                        "period": "daily"
                    }
                ],
                "reward_xp": 500,
                "reward_badge_url": "/badges/monthly_consistency.png",
                "is_active": True
            }
        ]