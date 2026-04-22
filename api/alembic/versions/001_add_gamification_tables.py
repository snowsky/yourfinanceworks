"""Add gamification tables

Revision ID: 001_gamification
Revises: 
Create Date: 2024-12-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_gamification'
down_revision = None  # This should be set to the latest revision in your system
branch_labels = None
depends_on = None


def upgrade():
    """Add gamification tables"""
    
    # Create enum types
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dataretentionpolicy') THEN
            CREATE TYPE dataretentionpolicy AS ENUM ('preserve', 'archive', 'delete');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'habittype') THEN
            CREATE TYPE habittype AS ENUM ('daily_expense_tracking', 'weekly_budget_review', 'invoice_follow_up', 'receipt_documentation');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'achievementcategory') THEN
            CREATE TYPE achievementcategory AS ENUM ('expense_tracking', 'invoice_management', 'habit_formation', 'financial_health', 'exploration');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'achievementdifficulty') THEN
            CREATE TYPE achievementdifficulty AS ENUM ('bronze', 'silver', 'gold', 'platinum');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'challengetype') THEN
            CREATE TYPE challengetype AS ENUM ('personal', 'community', 'seasonal');
        END IF;
    END $$;
    """)
    
    # Create user_gamification_profiles table
    op.create_table(
        'user_gamification_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('module_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('enabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_retention_policy', postgresql.ENUM('preserve', 'archive', 'delete', name='dataretentionpolicy'), nullable=False, default='preserve'),
        sa.Column('level', sa.Integer(), nullable=False, default=1),
        sa.Column('total_experience_points', sa.Integer(), nullable=False, default=0),
        sa.Column('current_level_progress', sa.Float(), nullable=False, default=0.0),
        sa.Column('financial_health_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('preferences', sa.JSON(), nullable=False, default={}),
        sa.Column('statistics', sa.JSON(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_gamification_profiles_id', 'user_gamification_profiles', ['id'])
    op.create_index('ix_user_gamification_profiles_user_id', 'user_gamification_profiles', ['user_id'])
    
    # Create achievements table
    op.create_table(
        'achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('achievement_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', postgresql.ENUM('expense_tracking', 'invoice_management', 'habit_formation', 'financial_health', 'exploration', name='achievementcategory'), nullable=False),
        sa.Column('difficulty', postgresql.ENUM('bronze', 'silver', 'gold', 'platinum', name='achievementdifficulty'), nullable=False),
        sa.Column('requirements', sa.JSON(), nullable=False),
        sa.Column('reward_xp', sa.Integer(), nullable=False, default=0),
        sa.Column('reward_badge_url', sa.String(), nullable=True),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('achievement_id')
    )
    op.create_index('ix_achievements_id', 'achievements', ['id'])
    op.create_index('ix_achievements_achievement_id', 'achievements', ['achievement_id'])
    op.create_index('ix_achievements_category', 'achievements', ['category'])
    op.create_index('ix_achievements_difficulty', 'achievements', ['difficulty'])
    
    # Create user_achievements table
    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('achievement_id', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=False, default=0.0),
        sa.Column('is_completed', sa.Boolean(), nullable=False, default=False),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['profile_id'], ['user_gamification_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ondelete='CASCADE')
    )
    op.create_index('ix_user_achievements_id', 'user_achievements', ['id'])
    op.create_index('ix_user_achievements_profile_id', 'user_achievements', ['profile_id'])
    op.create_index('ix_user_achievements_achievement_id', 'user_achievements', ['achievement_id'])
    
    # Create user_streaks table
    op.create_table(
        'user_streaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('habit_type', postgresql.ENUM('daily_expense_tracking', 'weekly_budget_review', 'invoice_follow_up', 'receipt_documentation', name='habittype'), nullable=False),
        sa.Column('current_length', sa.Integer(), nullable=False, default=0),
        sa.Column('longest_length', sa.Integer(), nullable=False, default=0),
        sa.Column('last_activity_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('streak_start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('times_broken', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['profile_id'], ['user_gamification_profiles.id'], ondelete='CASCADE')
    )
    op.create_index('ix_user_streaks_id', 'user_streaks', ['id'])
    op.create_index('ix_user_streaks_profile_id', 'user_streaks', ['profile_id'])
    op.create_index('ix_user_streaks_habit_type', 'user_streaks', ['habit_type'])
    
    # Create challenges table
    op.create_table(
        'challenges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('challenge_type', postgresql.ENUM('personal', 'community', 'seasonal', name='challengetype'), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('requirements', sa.JSON(), nullable=False),
        sa.Column('reward_xp', sa.Integer(), nullable=False, default=0),
        sa.Column('reward_badge_url', sa.String(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('challenge_id')
    )
    op.create_index('ix_challenges_id', 'challenges', ['id'])
    op.create_index('ix_challenges_challenge_id', 'challenges', ['challenge_id'])
    op.create_index('ix_challenges_challenge_type', 'challenges', ['challenge_type'])
    
    # Create user_challenges table
    op.create_table(
        'user_challenges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=False, default=0.0),
        sa.Column('is_completed', sa.Boolean(), nullable=False, default=False),
        sa.Column('opted_in', sa.Boolean(), nullable=False, default=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('milestones', sa.JSON(), nullable=False, default=[]),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['profile_id'], ['user_gamification_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE')
    )
    op.create_index('ix_user_challenges_id', 'user_challenges', ['id'])
    op.create_index('ix_user_challenges_profile_id', 'user_challenges', ['profile_id'])
    op.create_index('ix_user_challenges_challenge_id', 'user_challenges', ['challenge_id'])
    
    # Create point_history table
    op.create_table(
        'point_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('points_awarded', sa.Integer(), nullable=False),
        sa.Column('action_metadata', sa.JSON(), nullable=True),
        sa.Column('base_points', sa.Integer(), nullable=False),
        sa.Column('streak_multiplier', sa.Float(), nullable=False, default=1.0),
        sa.Column('accuracy_bonus', sa.Integer(), nullable=False, default=0),
        sa.Column('completeness_bonus', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['profile_id'], ['user_gamification_profiles.id'], ondelete='CASCADE')
    )
    op.create_index('ix_point_history_id', 'point_history', ['id'])
    op.create_index('ix_point_history_profile_id', 'point_history', ['profile_id'])
    op.create_index('ix_point_history_action_type', 'point_history', ['action_type'])
    op.create_index('ix_point_history_created_at', 'point_history', ['created_at'])
    
    # Create organization_gamification_configs table
    op.create_table(
        'organization_gamification_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('custom_point_values', sa.JSON(), nullable=False, default={}),
        sa.Column('achievement_thresholds', sa.JSON(), nullable=False, default={}),
        sa.Column('enabled_features', sa.JSON(), nullable=False, default={}),
        sa.Column('team_settings', sa.JSON(), nullable=False, default={}),
        sa.Column('policy_alignment', sa.JSON(), nullable=False, default={}),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.UniqueConstraint('organization_id')
    )
    op.create_index('ix_organization_gamification_configs_id', 'organization_gamification_configs', ['id'])
    op.create_index('ix_organization_gamification_configs_organization_id', 'organization_gamification_configs', ['organization_id'])


def downgrade():
    """Remove gamification tables"""
    
    # Drop tables in reverse order
    op.drop_table('organization_gamification_configs')
    op.drop_table('point_history')
    op.drop_table('user_challenges')
    op.drop_table('challenges')
    op.drop_table('user_streaks')
    op.drop_table('user_achievements')
    op.drop_table('achievements')
    op.drop_table('user_gamification_profiles')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS challengetype")
    op.execute("DROP TYPE IF EXISTS achievementdifficulty")
    op.execute("DROP TYPE IF EXISTS achievementcategory")
    op.execute("DROP TYPE IF EXISTS habittype")
    op.execute("DROP TYPE IF EXISTS dataretentionpolicy")
