from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from datetime import datetime, timezone
import logging
from sqlalchemy.engine.url import make_url
import os
import time

from core.models.models import Base
from core.models.models_per_tenant import Base as TenantBase, User as TenantUser
from core.models.database import (
    SQLALCHEMY_DATABASE_URL,
    get_master_db,
    set_tenant_context,
)
from scripts.reset_users_id_sequences import reset_all_users_id_sequences
from core.services.tenant_database_manager import tenant_db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable foreign key support for SQLite (kept minimal)
if make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() == "sqlite":

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def wait_for_database(database_url, max_retries=30, retry_delay=2):
    """Wait for database to be available."""
    logger.info("Waiting for database to be available...")

    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is available")
            return True
        except Exception as e:
            logger.info(
                f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    logger.error("Database did not become available within the timeout period")
    return False


def ensure_required_columns(database_url):
    """Ensure all required columns exist in tables."""
    try:
        engine = create_engine(database_url)

        with engine.connect() as conn:
            inspector = inspect(conn)

            # Check and add missing columns to master_users table
            if "master_users" in inspector.get_table_names():
                columns = inspector.get_columns("master_users")
                existing_columns = {col["name"] for col in columns}

                required_columns = {
                    "must_reset_password": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "show_analytics": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "azure_ad_id": "VARCHAR(255)",
                    "azure_tenant_id": "VARCHAR(255)",
                }

                for col_name, col_definition in required_columns.items():
                    if col_name not in existing_columns:
                        logger.info(
                            f"Adding missing column to master_users: {col_name}"
                        )
                        conn.execute(
                            text(
                                f"ALTER TABLE master_users ADD COLUMN {col_name} {col_definition}"
                            )
                        )
                        conn.commit()
                        logger.info(
                            f"Successfully added column to master_users: {col_name}"
                        )

            # Check and add missing columns to tenants table
            if "tenants" in inspector.get_table_names():
                columns = inspector.get_columns("tenants")
                existing_columns = {col["name"] for col in columns}

                required_columns_tenants = {
                    "is_enabled": "BOOLEAN NOT NULL DEFAULT TRUE",
                    "allow_join_lookup": "BOOLEAN NOT NULL DEFAULT TRUE",
                    "join_lookup_exact_match": "BOOLEAN NOT NULL DEFAULT FALSE",
                    "count_against_license": "BOOLEAN NOT NULL DEFAULT TRUE",
                }

                for col_name, col_definition in required_columns_tenants.items():
                    if col_name not in existing_columns:
                        logger.info(f"Adding missing column to tenants: {col_name}")
                        conn.execute(
                            text(
                                f"ALTER TABLE tenants ADD COLUMN {col_name} {col_definition}"
                            )
                        )
                        conn.commit()
                        logger.info(f"Successfully added column to tenants: {col_name}")

            # Check and add missing columns to global_installation_info table
            if "global_installation_info" in inspector.get_table_names():
                columns = inspector.get_columns("global_installation_info")
                existing_columns = {col["name"] for col in columns}

                required_columns_global = {
                    "allow_password_signup": "BOOLEAN NOT NULL DEFAULT TRUE",
                    "allow_sso_signup": "BOOLEAN NOT NULL DEFAULT TRUE",
                    "license_scope": "VARCHAR(20)",
                }

                for col_name, col_definition in required_columns_global.items():
                    if col_name not in existing_columns:
                        logger.info(f"Adding missing column to global_installation_info: {col_name}")
                        conn.execute(
                            text(
                                f"ALTER TABLE global_installation_info ADD COLUMN {col_name} {col_definition}"
                            )
                        )
                        conn.commit()
                        logger.info(f"Successfully added column to global_installation_info: {col_name}")

            # Check and add missing columns to installation_info table (per-tenant)
            if "installation_info" in inspector.get_table_names():
                columns = inspector.get_columns("installation_info")
                existing_columns = {col["name"] for col in columns}

                required_columns_install = {
                    "license_scope": "VARCHAR(20)",
                }

                for col_name, col_definition in required_columns_install.items():
                    if col_name not in existing_columns:
                        logger.info(f"Adding missing column to installation_info: {col_name}")
                        conn.execute(
                            text(
                                f"ALTER TABLE installation_info ADD COLUMN {col_name} {col_definition}"
                            )
                        )
                        conn.commit()
                        logger.info(f"Successfully added column to installation_info: {col_name}")

        return True

    except Exception as e:
        logger.error(f"Error ensuring required columns: {e}")
        return False


def sync_users_to_tenant_db(tenant_id: int):
    """Sync only admin users from master database to tenant database"""
    try:
        logger.info(f"Syncing admin users to tenant database {tenant_id}")

        # Get master database session
        master_db = next(get_master_db())

        try:
            # Get only admin users for this tenant from master database
            # Only the first user (tenant admin) should be in both master and tenant databases
            from core.models.models import Tenant, MasterUser

            master_users = (
                master_db.query(MasterUser)
                .filter(MasterUser.tenant_id == tenant_id)
                .order_by(MasterUser.id)
                .all()
            )

            if not master_users:
                logger.info(f"No users found for tenant {tenant_id}")
                return

            # Only sync the first user (tenant admin) - others should only be in tenant DB
            admin_user = master_users[0]  # First user is the tenant admin
            logger.info(
                f"Syncing admin user {admin_user.email} to tenant database {tenant_id}"
            )

            # Set tenant context
            set_tenant_context(tenant_id)

            # Get tenant database session
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
            tenant_db = tenant_session()

            try:
                # Check if admin user already exists in tenant database (by email or ID)
                existing_user = (
                    tenant_db.query(TenantUser)
                    .filter(
                        (TenantUser.email == admin_user.email)
                        | (TenantUser.id == admin_user.id)
                    )
                    .first()
                )

                if not existing_user:
                    # Create admin user in tenant database
                    tenant_user = TenantUser(
                        email=admin_user.email,
                        hashed_password=admin_user.hashed_password,
                        first_name=admin_user.first_name,
                        last_name=admin_user.last_name,
                        role=admin_user.role,
                        is_active=admin_user.is_active,
                        is_superuser=admin_user.is_superuser,
                        is_verified=admin_user.is_verified,
                        google_id=admin_user.google_id,
                        created_at=admin_user.created_at,
                        updated_at=admin_user.updated_at,
                    )

                    tenant_db.add(tenant_user)
                    logger.info(
                        f"Created admin user {admin_user.email} in tenant database {tenant_id}"
                    )
                else:
                    # Update existing admin user if needed
                    existing_user.email = admin_user.email
                    existing_user.hashed_password = admin_user.hashed_password
                    existing_user.first_name = admin_user.first_name
                    existing_user.last_name = admin_user.last_name
                    existing_user.role = admin_user.role
                    existing_user.is_active = admin_user.is_active
                    existing_user.is_superuser = admin_user.is_superuser
                    existing_user.is_verified = admin_user.is_verified
                    existing_user.google_id = admin_user.google_id
                    existing_user.updated_at = datetime.now(timezone.utc)
                    logger.info(
                        f"Updated existing admin user {admin_user.email} in tenant database {tenant_id}"
                    )

                tenant_db.commit()
                logger.info(
                    f"Successfully synced admin user to tenant database {tenant_id}"
                )

            finally:
                tenant_db.close()

        finally:
            master_db.close()

    except Exception as e:
        logger.error(
            f"Error syncing admin user to tenant database {tenant_id}: {str(e)}"
        )
        raise e


def create_gamification_tables(database_url):
    """Create gamification tables directly without migrations."""
    try:
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Create enum types if they don't exist
            enums_to_create = [
                ("dataretentionpolicy", "('preserve', 'archive', 'delete')"),
                (
                    "habittype",
                    "('daily_expense_tracking', 'weekly_budget_review', 'invoice_follow_up', 'receipt_documentation')",
                ),
                (
                    "achievementcategory",
                    "('expense_tracking', 'invoice_management', 'habit_formation', 'financial_health', 'exploration')",
                ),
                ("achievementdifficulty", "('bronze', 'silver', 'gold', 'platinum')"),
                ("challengetype", "('personal', 'community', 'seasonal')"),
            ]

            for enum_name, enum_values in enums_to_create:
                try:
                    conn.execute(text(f"CREATE TYPE {enum_name} AS ENUM {enum_values}"))
                    logger.info(f"Created enum type {enum_name}")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"Enum type {enum_name} already exists")
                    else:
                        logger.warning(f"Error creating enum {enum_name}: {e}")

            conn.commit()

            # Create tables
            tables_sql = [
                """CREATE TABLE IF NOT EXISTS user_gamification_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE,
                    module_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    enabled_at TIMESTAMP WITH TIME ZONE,
                    disabled_at TIMESTAMP WITH TIME ZONE,
                    data_retention_policy dataretentionpolicy NOT NULL DEFAULT 'preserve',
                    level INTEGER NOT NULL DEFAULT 1,
                    total_experience_points INTEGER NOT NULL DEFAULT 0,
                    current_level_progress FLOAT NOT NULL DEFAULT 0.0,
                    financial_health_score FLOAT NOT NULL DEFAULT 0.0,
                    preferences JSONB NOT NULL DEFAULT '{}',
                    statistics JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )""",
                """CREATE TABLE IF NOT EXISTS achievements (
                    id SERIAL PRIMARY KEY,
                    achievement_id VARCHAR NOT NULL UNIQUE,
                    name VARCHAR NOT NULL,
                    description TEXT NOT NULL,
                    category achievementcategory NOT NULL,
                    difficulty achievementdifficulty NOT NULL,
                    requirements JSONB NOT NULL,
                    reward_xp INTEGER NOT NULL DEFAULT 0,
                    reward_badge_url VARCHAR,
                    is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS user_achievements (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    achievement_id INTEGER NOT NULL,
                    progress FLOAT NOT NULL DEFAULT 0.0,
                    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
                    unlocked_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    FOREIGN KEY (profile_id) REFERENCES user_gamification_profiles(id) ON DELETE CASCADE,
                    FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE
                )""",
                """CREATE TABLE IF NOT EXISTS user_streaks (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    habit_type habittype NOT NULL,
                    current_length INTEGER NOT NULL DEFAULT 0,
                    longest_length INTEGER NOT NULL DEFAULT 0,
                    last_activity_date TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    streak_start_date TIMESTAMP WITH TIME ZONE,
                    times_broken INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    FOREIGN KEY (profile_id) REFERENCES user_gamification_profiles(id) ON DELETE CASCADE
                )""",
                """CREATE TABLE IF NOT EXISTS challenges (
                    id SERIAL PRIMARY KEY,
                    challenge_id VARCHAR NOT NULL UNIQUE,
                    name VARCHAR NOT NULL,
                    description TEXT NOT NULL,
                    challenge_type challengetype NOT NULL,
                    duration_days INTEGER NOT NULL,
                    requirements JSONB NOT NULL,
                    reward_xp INTEGER NOT NULL DEFAULT 0,
                    reward_badge_url VARCHAR,
                    start_date TIMESTAMP WITH TIME ZONE,
                    end_date TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    organization_id INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS user_challenges (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    challenge_id INTEGER NOT NULL,
                    progress FLOAT NOT NULL DEFAULT 0.0,
                    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
                    opted_in BOOLEAN NOT NULL DEFAULT TRUE,
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    milestones JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    FOREIGN KEY (profile_id) REFERENCES user_gamification_profiles(id) ON DELETE CASCADE,
                    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE
                )""",
                """CREATE TABLE IF NOT EXISTS point_history (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    action_type VARCHAR NOT NULL,
                    points_awarded INTEGER NOT NULL,
                    action_metadata JSONB,
                    base_points INTEGER NOT NULL,
                    streak_multiplier FLOAT NOT NULL DEFAULT 1.0,
                    accuracy_bonus INTEGER NOT NULL DEFAULT 0,
                    completeness_bonus INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    FOREIGN KEY (profile_id) REFERENCES user_gamification_profiles(id) ON DELETE CASCADE
                )""",
                """CREATE TABLE IF NOT EXISTS organization_gamification_configs (
                    id SERIAL PRIMARY KEY,
                    organization_id INTEGER NOT NULL UNIQUE,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    custom_point_values JSONB NOT NULL DEFAULT '{}',
                    achievement_thresholds JSONB NOT NULL DEFAULT '{}',
                    enabled_features JSONB NOT NULL DEFAULT '{}',
                    team_settings JSONB NOT NULL DEFAULT '{}',
                    policy_alignment JSONB NOT NULL DEFAULT '{}',
                    created_by INTEGER,
                    updated_by INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id)
                )""",
            ]

            for sql in tables_sql:
                try:
                    conn.execute(text(sql))
                    logger.info(f"Created table from SQL")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"Table already exists")
                    else:
                        logger.warning(f"Error creating table: {e}")

            # Create indexes
            indexes_sql = [
                "CREATE INDEX IF NOT EXISTS ix_user_gamification_profiles_id ON user_gamification_profiles(id)",
                "CREATE INDEX IF NOT EXISTS ix_user_gamification_profiles_user_id ON user_gamification_profiles(user_id)",
                "CREATE INDEX IF NOT EXISTS ix_achievements_id ON achievements(id)",
                "CREATE INDEX IF NOT EXISTS ix_achievements_achievement_id ON achievements(achievement_id)",
                "CREATE INDEX IF NOT EXISTS ix_achievements_category ON achievements(category)",
                "CREATE INDEX IF NOT EXISTS ix_achievements_difficulty ON achievements(difficulty)",
                "CREATE INDEX IF NOT EXISTS ix_user_achievements_id ON user_achievements(id)",
                "CREATE INDEX IF NOT EXISTS ix_user_achievements_profile_id ON user_achievements(profile_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_achievements_achievement_id ON user_achievements(achievement_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_streaks_id ON user_streaks(id)",
                "CREATE INDEX IF NOT EXISTS ix_user_streaks_profile_id ON user_streaks(profile_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_streaks_habit_type ON user_streaks(habit_type)",
                "CREATE INDEX IF NOT EXISTS ix_challenges_id ON challenges(id)",
                "CREATE INDEX IF NOT EXISTS ix_challenges_challenge_id ON challenges(challenge_id)",
                "CREATE INDEX IF NOT EXISTS ix_challenges_challenge_type ON challenges(challenge_type)",
                "CREATE INDEX IF NOT EXISTS ix_user_challenges_id ON user_challenges(id)",
                "CREATE INDEX IF NOT EXISTS ix_user_challenges_profile_id ON user_challenges(profile_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_challenges_challenge_id ON user_challenges(challenge_id)",
                "CREATE INDEX IF NOT EXISTS ix_point_history_id ON point_history(id)",
                "CREATE INDEX IF NOT EXISTS ix_point_history_profile_id ON point_history(profile_id)",
                "CREATE INDEX IF NOT EXISTS ix_point_history_action_type ON point_history(action_type)",
                "CREATE INDEX IF NOT EXISTS ix_point_history_created_at ON point_history(created_at)",
                "CREATE INDEX IF NOT EXISTS ix_organization_gamification_configs_id ON organization_gamification_configs(id)",
                "CREATE INDEX IF NOT EXISTS ix_organization_gamification_configs_organization_id ON organization_gamification_configs(organization_id)",
            ]

            for sql in indexes_sql:
                try:
                    conn.execute(text(sql))
                except Exception as e:
                    logger.debug(f"Index creation note: {e}")

            conn.commit()
            logger.info("Gamification tables created successfully")
            return True

    except Exception as e:
        logger.error(f"Error creating gamification tables: {e}")
        return False


def init_db():
    """Initialize database with essential setup."""
    logger.info("Starting database initialization...")

    # Set environment variable to indicate we're in database initialization phase
    os.environ["DB_INIT_PHASE"] = "true"

    # Step 1: Wait for database to be available
    if not wait_for_database(SQLALCHEMY_DATABASE_URL):
        logger.error("Database is not available")
        raise Exception("Database connection failed")

    # Step 2: Ensure all required columns exist (handles schema evolution)
    if not ensure_required_columns(SQLALCHEMY_DATABASE_URL):
        logger.error("Failed to ensure required columns")
        # Continue anyway as this is just a safety check

    # Create database engine
    if make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() == "sqlite":
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)

    # Create all tables in the main (master) DB from SQLAlchemy models
    Base.metadata.create_all(bind=engine)

    # Create analytics table in master DB
    from core.models.analytics import Base as AnalyticsBase

    AnalyticsBase.metadata.create_all(bind=engine)

    # Create gamification tables in master DB
    create_gamification_tables(SQLALCHEMY_DATABASE_URL)

    # Create all tables for every tenant
    master_db = next(get_master_db())
    from core.models.models import Tenant

    tenants = master_db.query(Tenant).all()
    for tenant in tenants:
        logger.info(f"Ensuring tables for tenant {tenant.id}...")
        db_url_template = os.environ.get(
            "TENANT_DB_URL_TEMPLATE",
            "postgresql://postgres:password@postgres-master:5432/tenant_{tenant_id}",
        )
        tenant_db_url = db_url_template.format(tenant_id=tenant.id)
        db_name = f"tenant_{tenant.id}"
        # Build admin URL (replace db name with 'postgres')
        admin_db_url = tenant_db_url.rsplit("/", 1)[0] + "/postgres"
        admin_engine = create_engine(admin_db_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname=:db_name"),
                {"db_name": db_name},
            )
            if not result.scalar():
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"Created database {db_name}")
        # Now create tables in the tenant DB
        tenant_engine = create_engine(tenant_db_url)
        logger.info(
            f"Tables to be created for tenant {tenant.id}: {TenantBase.metadata.tables.keys()}"
        )
        try:
            # Create tenant database tables
            # Note: For tenant databases, metadata.create_all is still used since
            # databases are created dynamically and need immediate schema setup
            TenantBase.metadata.create_all(bind=tenant_engine)
            logger.info(f"Tables created for tenant {tenant.id}")

            # Create gamification tables for this tenant
            create_gamification_tables(tenant_db_url)

        except Exception as e:
            logger.error(f"Error creating tables for tenant {tenant.id}: {str(e)}")

        # Note: User sync is deferred until after DB_INIT_PHASE to ensure proper encryption

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Seed default supported currencies if none exist for this tenant
        from core.models.models import SupportedCurrency

        existing_currencies = db.query(SupportedCurrency).count()
        if existing_currencies == 0:
            default_currencies = [
                {
                    "code": "USD",
                    "name": "US Dollar",
                    "symbol": "$",
                    "decimal_places": 2,
                },
                {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
                {
                    "code": "GBP",
                    "name": "British Pound",
                    "symbol": "£",
                    "decimal_places": 2,
                },
                {
                    "code": "CAD",
                    "name": "Canadian Dollar",
                    "symbol": "C$",
                    "decimal_places": 2,
                },
                {
                    "code": "AUD",
                    "name": "Australian Dollar",
                    "symbol": "A$",
                    "decimal_places": 2,
                },
                {
                    "code": "JPY",
                    "name": "Japanese Yen",
                    "symbol": "¥",
                    "decimal_places": 0,
                },
                {
                    "code": "CHF",
                    "name": "Swiss Franc",
                    "symbol": "CHF",
                    "decimal_places": 2,
                },
                {
                    "code": "CNY",
                    "name": "Chinese Yuan",
                    "symbol": "¥",
                    "decimal_places": 2,
                },
                {
                    "code": "INR",
                    "name": "Indian Rupee",
                    "symbol": "₹",
                    "decimal_places": 2,
                },
                {
                    "code": "BRL",
                    "name": "Brazilian Real",
                    "symbol": "R$",
                    "decimal_places": 2,
                },
            ]
            for currency in default_currencies:
                db.add(
                    SupportedCurrency(
                        code=currency["code"],
                        name=currency["name"],
                        symbol=currency["symbol"],
                        decimal_places=currency["decimal_places"],
                        is_active=True,
                    )
                )
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing database: {str(e)}")
        raise e
    finally:
        db.close()

    # Initialize achievements for all tenant databases
    logger.info("Initializing achievements for all tenants...")
    for tenant in tenants:
        try:
            logger.info(f"Initializing achievements for tenant {tenant.id}...")
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)
            tenant_db = tenant_session()

            try:
                from core.services.achievement_engine import AchievementEngine

                achievement_engine = AchievementEngine(tenant_db)
                success = achievement_engine.initialize_achievements()
                if success:
                    logger.info(
                        f"Successfully initialized achievements for tenant {tenant.id}"
                    )
                else:
                    logger.error(
                        f"Failed to initialize achievements for tenant {tenant.id}"
                    )
            finally:
                tenant_db.close()

        except Exception as e:
            logger.error(
                f"Failed to initialize achievements for tenant {tenant.id}: {str(e)}"
            )

    # Reset users.id sequences for all tenant DBs
    reset_all_users_id_sequences()

    logger.info("Database initialized successfully with sample data.")

    # Clear the database initialization phase flag BEFORE syncing users
    # This ensures user data is encrypted properly
    os.environ["DB_INIT_PHASE"] = "false"

    # Generate encryption keys for all tenants
    logger.info("Generating encryption keys for all tenants...")
    try:
        from core.services.key_management_service import KeyManagementService

        key_management = KeyManagementService()

        for tenant in tenants:
            try:
                # Check if tenant key already exists
                existing_keys = key_management.list_tenant_keys()
                if tenant.id not in existing_keys:
                    logger.info(f"Generating encryption key for tenant {tenant.id}...")
                    key_management.generate_tenant_key(tenant.id)
                    logger.info(f"Generated encryption key for tenant {tenant.id}")
                else:
                    logger.info(f"Encryption key already exists for tenant {tenant.id}")
            except Exception as e:
                logger.error(
                    f"Failed to generate encryption key for tenant {tenant.id}: {str(e)}"
                )
    except Exception as e:
        logger.error(f"Failed to initialize encryption keys: {str(e)}")

    # Re-sync users with encryption enabled to ensure proper encryption
    logger.info("Re-syncing users with encryption enabled...")
    for tenant in tenants:
        try:
            sync_users_to_tenant_db(tenant.id)
            logger.info(f"Re-synced users for tenant {tenant.id} with encryption")
        except Exception as e:
            logger.error(f"Failed to re-sync users for tenant {tenant.id}: {str(e)}")


if __name__ == "__main__":
    init_db()
