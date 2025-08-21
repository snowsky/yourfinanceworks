
import sys
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import logging

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from models.models_per_tenant import AuditLog
from models.models import Base, MasterUser, Tenant
from models.database import get_master_db, DATABASE_URL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def query_audit_log(user_email: str):
    """
    Queries the audit log for a specific user.
    """
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        logger.info(f"Querying audit log for user: {user_email}")
        
        # Query for delete and update actions (including new user-friendly names)
        actions = ["DELETE", "UPDATE", "Soft Delete", "Permanent Delete", "Empty Recycle Bin", "Restore"]
        
        log_entries = db.query(AuditLog).filter(
            AuditLog.user_email == user_email,
            AuditLog.action.in_(actions)
        ).all()

        if not log_entries:
            logger.info(f"No 'DELETE' or 'UPDATE' audit log entries found for user: {user_email}")
            return

        for entry in log_entries:
            logger.info(f"  ID: {entry.id}")
            logger.info(f"  Timestamp: {entry.created_at}")
            logger.info(f"  User ID: {entry.user_id}")
            logger.info(f"  User Email: {entry.user_email}")
            logger.info(f"  Action: {entry.action}")
            logger.info(f"  Resource Type: {entry.resource_type}")
            logger.info(f"  Resource ID: {entry.resource_id}")
            logger.info(f"  Status: {entry.status}")
            logger.info(f"  Details: {entry.details}")
            logger.info("-" * 20)

    except OperationalError as e:
        logger.error(f"Database connection error: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python query_audit_log.py <user_email>")
        sys.exit(1)
    
    user_email_to_query = sys.argv[1]
    query_audit_log(user_email_to_query)
