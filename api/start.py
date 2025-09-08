import uvicorn
import os
from dotenv import load_dotenv
from models.database import engine, Base
from models.models import Client, Invoice, Item, Payment
from db_init import init_db

# Load environment variables from .env file
load_dotenv()

# Create the database and tables
Base.metadata.create_all(bind=engine)

# Initialize with sample data if db file doesn't exist or is empty
db_file = "./invoice_app.db"
if not os.path.exists(db_file) or os.path.getsize(db_file) < 5000:
    print("Initializing database with sample data...")
    init_db()
    print("Database initialized successfully!")

# Run the FastAPI app
if __name__ == "__main__":
    print("Starting API server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 