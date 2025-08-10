from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.engine.url import make_url
import os

from models.models import Base, User, Client, Invoice, Settings, Payment, Invite, ClientNote, DiscountRule, SupportedCurrency, CurrencyRate, InvoiceItem, InvoiceHistory, AIConfig
from models.models_per_tenant import Base as TenantBase, User as TenantUser
from models.analytics import PageView
from models.database import SQLALCHEMY_DATABASE_URL, get_master_db, set_tenant_context
from utils.auth import get_password_hash
from scripts.reset_users_id_sequences import reset_all_users_id_sequences
from scripts.migrate_database import migrate_database
from services.tenant_database_manager import tenant_db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable foreign key support for SQLite
if make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() == "sqlite":
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def sync_users_to_tenant_db(tenant_id: int):
    """Sync only admin users from master database to tenant database"""
    try:
        logger.info(f"Syncing admin users to tenant database {tenant_id}")
        
        # Get master database session
        master_db = next(get_master_db())
        
        try:
            # Get only admin users for this tenant from master database
            # Only the first user (tenant admin) should be in both master and tenant databases
            from models.models import Tenant, MasterUser
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
                # Check if admin user already exists in tenant database
                existing_user = tenant_db.query(TenantUser).filter(TenantUser.email == admin_user.email).first()
                
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
                    logger.info(f"Updated admin user {admin_user.email} in tenant database {tenant_id}")
                
                tenant_db.commit()
                logger.info(f"Successfully synced admin user to tenant database {tenant_id}")
                
            finally:
                tenant_db.close()
                
        finally:
            master_db.close()
            
    except Exception as e:
        logger.error(f"Error syncing admin user to tenant database {tenant_id}: {str(e)}")
        raise e

def run_migrations():
    """Run all necessary migrations"""
    try:
        logger.info("Running database migrations...")
        
        # Import and run the tested field migration for all tenants
        from scripts.migrate_ai_config_tested_all_tenants import add_tested_field_to_all_tenant_databases
        add_tested_field_to_all_tenant_databases()
        
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        # Don't raise the exception - migrations are optional for initial setup
        logger.warning("Continuing with database initialization despite migration errors")

def init_db():
    # Create database engine
    if make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() == "sqlite":
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    
    
    # Create all tables in the main (master) DB
    Base.metadata.create_all(bind=engine)
    
    # Add show_analytics column to master_users if it doesn't exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if 'master_users' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('master_users')]
        if 'show_analytics' not in columns:
            try:
                with engine.connect() as connection:
                    connection.execute(text("ALTER TABLE master_users ADD COLUMN show_analytics BOOLEAN DEFAULT FALSE NOT NULL"))
                    connection.commit()
                logger.info("Successfully added 'show_analytics' column to 'master_users' table.")
            except Exception as e:
                logger.error(f"Error adding 'show_analytics' column to 'master_users' table: {e}")
    
    # Create analytics table in master DB
    from models.analytics import Base as AnalyticsBase
    AnalyticsBase.metadata.create_all(bind=engine)

    

    # Run recent migration logic before post-setup steps
    migrate_database()

    # Create all tables for every tenant
    master_db = next(get_master_db())
    from models.models import Tenant
    tenants = master_db.query(Tenant).all()
    for tenant in tenants:
        print(f"Ensuring tables for tenant {tenant.id}...")
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
                print(f"Created database {db_name}")
        # Now create tables in the tenant DB
        tenant_engine = create_engine(tenant_db_url)
        logger.info(f"Tables to be created for tenant {tenant.id}: {TenantBase.metadata.tables.keys()}")
        try:
            TenantBase.metadata.create_all(bind=tenant_engine)
            print(f"Tables created for tenant {tenant.id}")
            
            # Add the 'theme' column to 'users' table in tenant DB if it doesn't exist
            from sqlalchemy import inspect
            inspector = inspect(tenant_engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            if 'theme' not in columns:
                try:
                    with tenant_engine.connect() as connection:
                        connection.execute(text("ALTER TABLE users ADD COLUMN theme VARCHAR(255) DEFAULT 'system'"))
                        connection.commit()
                    logger.info(f"Successfully added 'theme' column to 'users' table for tenant {tenant.id}.")
                except Exception as e:
                    logger.error(f"Error adding 'theme' column to 'users' table for tenant {tenant.id}: {e}")

            # Add the 'show_discount_in_pdf' column to 'invoices' table in tenant DB if it doesn't exist
            columns = [col['name'] for col in inspector.get_columns('invoices')]
            if 'show_discount_in_pdf' not in columns:
                try:
                    tenant_engine.execute(text('ALTER TABLE invoices ADD COLUMN show_discount_in_pdf BOOLEAN DEFAULT TRUE NOT NULL'))
                    logger.info(f"Successfully added 'show_discount_in_pdf' column to 'invoices' table for tenant {tenant.id}.")
                except Exception as e:
                    logger.error(f"Error adding 'show_discount_in_pdf' column to 'invoices' table for tenant {tenant.id}: {e}")

            # Add email_notification_settings table if it doesn't exist
            if 'email_notification_settings' not in inspector.get_table_names():
                try:
                    from models.models_per_tenant import EmailNotificationSettings
                    EmailNotificationSettings.__table__.create(tenant_engine)
                    logger.info(f"Created email_notification_settings table for tenant {tenant.id}")
                except Exception as e:
                    logger.error(f"Error creating email_notification_settings table for tenant {tenant.id}: {e}")
            
            # Ensure expenses.invoice_id column exists for expense->invoice linking
            try:
                expense_columns = [col['name'] for col in inspector.get_columns('expenses')]
                if 'invoice_id' not in expense_columns:
                    with tenant_engine.connect() as connection:
                        connection.execute(text("ALTER TABLE expenses ADD COLUMN invoice_id INTEGER"))
                        # Add FK if invoices table exists
                        invoice_columns = [col['name'] for col in inspector.get_columns('invoices')]
                        if 'id' in invoice_columns:
                            try:
                                connection.execute(text("ALTER TABLE expenses ADD CONSTRAINT fk_expenses_invoice_id FOREIGN KEY (invoice_id) REFERENCES invoices(id)"))
                            except Exception as fk_err:
                                logger.warning(f"Could not add FK for expenses.invoice_id in tenant {tenant.id}: {fk_err}")
                        connection.commit()
                    logger.info(f"Added expenses.invoice_id column for tenant {tenant.id}")
            except Exception as e:
                logger.error(f"Error ensuring expenses.invoice_id for tenant {tenant.id}: {e}")
            
            # Verify if audit_logs table exists
            if 'audit_logs' in inspector.get_table_names():
                logger.info(f"audit_logs table successfully created for tenant {tenant.id}")
            else:
                logger.error(f"audit_logs table NOT found for tenant {tenant.id} after create_all")
        except Exception as e:
            logger.error(f"Error creating tables for tenant {tenant.id}: {str(e)}")
        
        # Sync users from master database to tenant database
        try:
            sync_users_to_tenant_db(tenant.id)
        except Exception as e:
            logger.error(f"Failed to sync users for tenant {tenant.id}: {str(e)}")
            # Continue with other tenants even if one fails
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Seed default supported currencies if none exist for this tenant
        from models.models import SupportedCurrency
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
    
    # Run comprehensive migrations after initial setup
    from scripts.run_all_migrations import run_all_migrations
    run_all_migrations()
    # Reset users.id sequences for all tenant DBs
    reset_all_users_id_sequences()
    
    logger.info("Database initialized successfully with sample data.")

if __name__ == "__main__":
    init_db() 