from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.engine.url import make_url

from models.models import Base, User, Tenant, Client, Invoice, Settings, Payment, Invite, ClientNote, DiscountRule, SupportedCurrency, CurrencyRate, InvoiceItem, InvoiceHistory, AIConfig, MasterUser
from models.database import SQLALCHEMY_DATABASE_URL
from utils.auth import get_password_hash
from scripts.reset_users_id_sequences import reset_all_users_id_sequences

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
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Remove creation of Default Tenant and all sample data
        pass  # No default tenant, admin user, or sample data will be created

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
    # Reset users.id sequences for all tenant DBs (redundant if run_all_migrations already does it, but safe)
    reset_all_users_id_sequences()
    
    logger.info("Database initialized successfully with sample data.")

if __name__ == "__main__":
    init_db() 