from core.models.database import engine, Base

if __name__ == "__main__":
    print("Creating all tables in PostgreSQL database...")
    Base.metadata.create_all(bind=engine)
    print("✅ Schema created successfully!") 