from sqlalchemy import Column, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine

Base = declarative_base()

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True, index=True)
    enable_ai_assistant = Column(Boolean, default=False)

def upgrade(engine):
    Base.metadata.create_all(engine)

def downgrade(engine):
    # In a real migration, you might drop the column or handle data.
    # For simplicity, we'll just pass here.
    pass

if __name__ == "__main__":
    # This part is for local testing of the migration script
    # In a real application, you'd use Alembic or similar.
    DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    print("Running upgrade...")
    upgrade(engine)
    print("Upgrade complete.")

    # You can add code here to verify the column was added
    # For example, by trying to insert a new setting or inspect the table schema.
