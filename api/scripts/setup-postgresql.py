#!/usr/bin/env python3
"""
PostgreSQL Setup Script for Invoice App
Automates the migration from SQLite to PostgreSQL
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def check_docker():
    """Check if Docker is available"""
    return run_command("docker --version", "Checking Docker installation")

def check_docker_compose():
    """Check if Docker Compose is available"""
    return run_command("docker-compose --version", "Checking Docker Compose installation")

def setup_postgresql_docker():
    """Set up PostgreSQL using Docker"""
    print("\n🐳 Setting up PostgreSQL with Docker...")
    
    # Check if docker-compose-postgresql.yml exists
    if not Path("docker-compose-postgresql.yml").exists():
        print("❌ docker-compose-postgresql.yml not found")
        return False
    
    # Copy the PostgreSQL compose file
    if run_command("cp docker-compose-postgresql.yml docker-compose.yml", "Copying PostgreSQL Docker Compose file"):
        # Start PostgreSQL
        if run_command("docker-compose up -d postgres", "Starting PostgreSQL container"):
            print("⏳ Waiting for PostgreSQL to be ready...")
            time.sleep(10)
            
            # Check if PostgreSQL is running
            if run_command("docker-compose ps postgres", "Checking PostgreSQL status"):
                return True
    
    return False

def install_dependencies():
    """Install PostgreSQL dependencies"""
    print("\n📦 Installing PostgreSQL dependencies...")
    
    # Check if requirements-postgresql.txt exists
    if not Path("api/requirements-postgresql.txt").exists():
        print("❌ requirements-postgresql.txt not found")
        return False
    
    return run_command("pip install -r requirements-postgresql.txt", "Installing PostgreSQL dependencies")

def check_sqlite_database():
    """Check if SQLite database exists"""
    sqlite_file = Path("api/invoice_app.db")
    if not sqlite_file.exists():
        print("❌ SQLite database file (invoice_app.db) not found")
        print("Please ensure you have an existing SQLite database to migrate from")
        return False
    
    print(f"✅ Found SQLite database: {sqlite_file}")
    return True

def run_migration():
    """Run the data migration"""
    print("\n🔄 Running data migration...")
    
    if not Path("migrate-to-postgresql.py").exists():
        print("❌ Migration script (migrate-to-postgresql.py) not found")
        return False
    
    return run_command("python migrate-to-postgresql.py", "Migrating data from SQLite to PostgreSQL")

def setup_environment():
    """Set up environment variables"""
    print("\n⚙️ Setting up environment variables...")
    
    if not Path("env.postgresql.example").exists():
        print("❌ env.postgresql.example not found")
        return False
    
    # Copy environment file if .env doesn't exist
    if not Path(".env").exists():
        if run_command("cp env.postgresql.example .env", "Creating .env file"):
            print("✅ Environment file created")
            print("📝 Please edit .env file with your specific settings")
            return True
    else:
        print("⚠️ .env file already exists")
        response = input("Do you want to overwrite it with PostgreSQL settings? (y/N): ")
        if response.lower() == 'y':
            if run_command("cp env.postgresql.example .env", "Overwriting .env file"):
                print("✅ Environment file updated")
                return True
    
    return True

def verify_migration():
    """Verify the migration was successful"""
    print("\n🔍 Verifying migration...")
    
    # Test database connection
    test_script = """
import os
import sys
sys.path.append('.')
from models.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()'))
        version = result.fetchone()[0]
        print(f'✅ Connected to PostgreSQL: {version}')
        
        # Check if tables exist
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result.fetchall()]
        print(f'✅ Found {len(tables)} tables: {", ".join(tables)}')
        
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
"""
    
    with open("test_db.py", "w") as f:
        f.write(test_script)
    
    success = run_command("python test_db.py", "Testing database connection")
    
    # Clean up test file
    if Path("test_db.py").exists():
        os.remove("test_db.py")
    
    return success

def main():
    """Main setup function"""
    print("🚀 PostgreSQL Setup for Invoice App")
    print("=" * 50)
    
    # Check prerequisites
    if not check_docker():
        print("❌ Docker is required for this setup")
        return False
    
    if not check_docker_compose():
        print("❌ Docker Compose is required for this setup")
        return False
    
    # Check if SQLite database exists
    if not check_sqlite_database():
        return False
    
    # Set up PostgreSQL with Docker
    if not setup_postgresql_docker():
        print("❌ Failed to set up PostgreSQL with Docker")
        return False
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install PostgreSQL dependencies")
        return False
    
    # Set up environment
    if not setup_environment():
        print("❌ Failed to set up environment variables")
        return False
    
    # Run migration
    if not run_migration():
        print("❌ Failed to migrate data")
        return False
    
    # Verify migration
    if not verify_migration():
        print("❌ Migration verification failed")
        return False
    
    print("\n🎉 PostgreSQL setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your specific settings")
    print("2. Start the application: docker-compose up -d")
    print("3. Access the application at http://localhost:3000")
    print("4. Check the migration guide for troubleshooting: DATABASE_MIGRATION_GUIDE.md")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 