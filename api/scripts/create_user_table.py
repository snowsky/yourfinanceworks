"""
Script to create the User table in the existing database.
"""
from core.models.database import engine
from core.models.models import Base, User

def create_user_table():
    # Create only the User table
    User.__table__.create(bind=engine, checkfirst=True)
    print("User table created successfully!")

if __name__ == "__main__":
    create_user_table() 