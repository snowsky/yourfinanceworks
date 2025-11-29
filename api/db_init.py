from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from datetime import datetime, timezone
import logging
from sqlalchemy.engine.url import make_url
import os
import time
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from core.models.models import Base
from core.models.models_per_tenant import Base as TenantBase, User as TenantUser
from core.models.database import SQLALCHEMY_DATABASE_URL, get_master_db, set_tenant_context
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
                conn.execute(text('SELECT 1'))
            logger.info("Database is available")
            return True
        except Exception as e:
            logger.info(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    logger.error("Database did not become available within the timeout period")
    return False

def ensure_alembic_version_table_structure(database_url):
    """Ensure alembic_version table has correct column length."""
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            inspector = inspect(conn)
            
            # Check if alembic_version table exists
            if 'alembic_version' in inspector.get_table_names():
                # Check column length
                result = conn.execute(text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name = 'alembic_version' AND column_name = 'version_num'"
                ))
                current_length = result.fetchone()
                
                if current_length and current_length[0] < 128:
                    logger.info(f"Expanding alembic_version.version_num column from {current_length[0]} to 128 characters")
                    conn.execute(text('ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)'))
                    conn.commit()
                    logger.info("Successfully expanded alembic_version column")
                else:
                    logger.info("alembic_version column already has correct length")
            else:
                logger.info("alembic_version table does not exist yet")
        
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring alembic_version table structure: {e}")
        return False

def ensure_required_columns(database_url):
    """Ensure required columns exist in master_users table."""
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            inspector = inspect(conn)
            
            # Check if master_users table exists
            if 'master_users' not in inspector.get_table_names():
                logger.info("master_users table does not exist yet")
                return True
            
            # Get existing columns
            columns = inspector.get_columns('master_users')
            existing_columns = {col['name'] for col in columns}
            
            # Required columns that should exist
            required_columns = {
                'must_reset_password': 'BOOLEAN NOT NULL DEFAULT FALSE',
                'show_analytics': 'BOOLEAN NOT NULL DEFAULT FALSE',
                'azure_ad_id': 'VARCHAR(255)',
                'azure_tenant_id': 'VARCHAR(255)'
            }
            
            # Add missing columns
            for col_name, col_definition in required_columns.items():
                if col_name not in existing_columns:
                    logger.info(f"Adding missing column: {col_name}")
                    conn.execute(text(f'ALTER TABLE master_users ADD COLUMN {col_name} {col_definition}'))
                    conn.commit()
                    logger.info(f"Successfully added column: {col_name}")
                else:
                    logger.info(f"Column {col_name} already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring required columns: {e}")
        return False

def run_database_migrations():
    """Run alembic migrations to ensure database is up to date."""
    try:
        # Create alembic config
        alembic_cfg = Config('alembic.ini')
        
        # Check current revision
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            
            # Get script directory
            script = ScriptDirectory.from_config(alembic_cfg)
            head_rev = script.get_current_head()
            
            logger.info(f"Current revision: {current_rev}")
            logger.info(f"Head revision: {head_rev}")
            
            if current_rev != head_rev:
                logger.info("Running migrations to bring database up to date...")
                command.upgrade(alembic_cfg, 'head')
                logger.info("Migrations completed successfully")
            else:
                logger.info("Database is already up to date")
        
        return True
        
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
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
            master_users = master_db.query(MasterUser).filter(
                MasterUser.tenant_id == tenant_id
            ).order_by(MasterUser.id).all()
            
            if not master_users:
                logger.info(f"No users found for tenant {tenant_id}")
                return
            
            # Only sync the first user (tenant admin) - others should only be in tenant DB
            admin_user = master_users[0]  # First user is the tenant admin
            logger.info(f"Syncing admin user {admin_user.email} to tenant database {tenant_id}")
            
            # Set tenant context
            set_tenant_context(tenant_id)
            
            # Get tenant database session
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
            tenant_db = tenant_session()
            
            try:
                # Check if admin user already exists in tenant database (by email or ID)
                existing_user = tenant_db.query(TenantUser).filter(
                    (TenantUser.email == admin_user.email) | (TenantUser.id == admin_user.id)
                ).first()
                
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
                        updated_at=admin_user.updated_at
                    )
                    
                    tenant_db.add(tenant_user)
                    logger.info(f"Created admin user {admin_user.email} in tenant database {tenant_id}")
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
                    logger.info(f"Updated existing admin user {admin_user.email} in tenant database {tenant_id}")
                
                tenant_db.commit()
                logger.info(f"Successfully synced admin user to tenant database {tenant_id}")
                
            finally:
                tenant_db.close()
                
        finally:
            master_db.close()
            
    except Exception as e:
        logger.error(f"Error syncing admin user to tenant database {tenant_id}: {str(e)}")
        raise e

def init_db(skip_migrations=True):
    """Initialize database with essential setup, optionally skipping migrations."""
    logger.info("Starting essential database initialization...")

    # Set environment variable to indicate we're in database initialization phase
    os.environ['DB_INIT_PHASE'] = 'true'

    # Step 1: Wait for database to be available
    if not wait_for_database(SQLALCHEMY_DATABASE_URL):
        logger.error("Database is not available")
        raise Exception("Database connection failed")

    # Step 2: Ensure required columns exist (fallback for manual fixes)
    if not ensure_required_columns(SQLALCHEMY_DATABASE_URL):
        logger.error("Failed to ensure required columns")
        # Continue anyway as tables might not exist yet

    # Step 3: Skip migrations if requested (to avoid hanging)
    if not skip_migrations:
        # Step 3a: Ensure alembic_version table has correct structure
        if not ensure_alembic_version_table_structure(SQLALCHEMY_DATABASE_URL):
            logger.error("Failed to ensure alembic_version table structure")
            # Continue anyway as this might be first run

        # Step 3b: Run migrations to ensure database is up to date
        if not run_database_migrations():
            logger.error("Failed to run migrations")
            # Continue anyway to allow basic table creation

    # Create database engine
    if make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() == "sqlite":
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)

    # Create all tables in the main (master) DB
    # Note: Schema creation is now handled by Alembic migrations
    # The following ALTER TABLE operations have been moved to proper migrations:
    # - must_reset_password column: 2b1a_must_reset_password_master.py
    # - show_analytics column: add_show_analytics_column.py
    Base.metadata.create_all(bind=engine)

    # Create analytics table in master DB
    from core.models.analytics import Base as AnalyticsBase
    AnalyticsBase.metadata.create_all(bind=engine)

    # Create all tables for every tenant
    master_db = next(get_master_db())
    from core.models.models import Tenant
    tenants = master_db.query(Tenant).all()
    for tenant in tenants:
        logger.info(f"Ensuring tables for tenant {tenant.id}...")
        db_url_template = os.environ.get("TENANT_DB_URL_TEMPLATE", "postgresql://postgres:password@postgres-master:5432/tenant_{tenant_id}")
        tenant_db_url = db_url_template.format(tenant_id=tenant.id)
        db_name = f"tenant_{tenant.id}"
        # Build admin URL (replace db name with 'postgres')
        admin_db_url = tenant_db_url.rsplit('/', 1)[0] + '/postgres'
        admin_engine = create_engine(admin_db_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname=:db_name"), {"db_name": db_name})
            if not result.scalar():
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"Created database {db_name}")
        # Now create tables in the tenant DB
        tenant_engine = create_engine(tenant_db_url)
        logger.info(f"Tables to be created for tenant {tenant.id}: {TenantBase.metadata.tables.keys()}")
        try:
            # Create tenant database tables
            # Note: For tenant databases, metadata.create_all is still used since
            # databases are created dynamically and need immediate schema setup
            TenantBase.metadata.create_all(bind=tenant_engine)
            logger.info(f"Tables created for tenant {tenant.id}")
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
                {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
                {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
                {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_places": 2},
                {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "decimal_places": 2},
                {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "decimal_places": 2},
                {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_places": 0},
                {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF", "decimal_places": 2},
                {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "decimal_places": 2},
                {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimal_places": 2},
                {"code": "BRL", "name": "Brazilian Real", "symbol": "R$", "decimal_places": 2},
            ]
            for currency in default_currencies:
                db.add(SupportedCurrency(
                    code=currency["code"],
                    name=currency["name"],
                    symbol=currency["symbol"],
                    decimal_places=currency["decimal_places"],
                    is_active=True
                ))
            db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing database: {str(e)}")
        raise e
    finally:
        db.close()
    
    # Skip migrations to avoid multiple heads issue
    # from scripts.run_all_migrations import run_all_migrations
    # run_all_migrations()
    # Reset users.id sequences for all tenant DBs
    reset_all_users_id_sequences()
    
    logger.info("Database initialized successfully with sample data.")

    # Clear the database initialization phase flag BEFORE syncing users
    # This ensures user data is encrypted properly
    os.environ['DB_INIT_PHASE'] = 'false'

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