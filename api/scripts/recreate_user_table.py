"""
Script to drop and recreate the User table with the correct schema.
"""
from core.models.database import engine
from core.models.models import Base, User

def recreate_user_table():
    # Drop the existing User table
    User.__table__.drop(bind=engine, checkfirst=True)
    print("Dropped existing User table")
    
    # Create the User table with the correct schema
    User.__table__.create(bind=engine, checkfirst=True)
    print("User table recreated successfully!")

if __name__ == "__main__":
    recreate_user_table() 