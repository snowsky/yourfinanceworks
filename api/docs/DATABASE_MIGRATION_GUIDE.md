# Database Migration Guide: SQLite to PostgreSQL

This guide will help you migrate your Invoice App from SQLite to PostgreSQL.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ installed
- Your existing SQLite database file (`invoice_app.db`)

## Option 1: Using Docker Compose (Recommended)

### Step 1: Set up PostgreSQL with Docker

1. **Copy the PostgreSQL Docker Compose file:**
   ```bash
   cp docker-compose-postgresql.yml docker-compose.yml
   ```

2. **Start PostgreSQL:**
   ```bash
   docker-compose up -d postgres
   ```

3. **Wait for PostgreSQL to be ready:**
   ```bash
   docker-compose logs postgres
   ```

### Step 2: Install PostgreSQL Dependencies

1. **Install PostgreSQL requirements:**
   ```bash
   cd api
   pip install -r requirements-postgresql.txt
   ```

### Step 3: Migrate Data

1. **Run the migration script:**
   ```bash
   cd api
   python migrate-to-postgresql.py
   ```

### Step 4: Update Environment Variables

1. **Copy the PostgreSQL environment example:**
   ```bash
   cp env.postgresql.example .env
   ```

2. **Edit the `.env` file with your settings:**
   ```bash
   nano .env
   ```

### Step 5: Start the Application

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

## Option 2: Manual PostgreSQL Installation

### Step 1: Install PostgreSQL

**On macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**On Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**On Windows:**
Download and install from https://www.postgresql.org/download/windows/

### Step 2: Create Database

1. **Connect to PostgreSQL:**
   ```bash
   sudo -u postgres psql
   ```

2. **Create database and user:**
   ```sql
   CREATE DATABASE invoice_app;
   CREATE USER postgres WITH PASSWORD 'password';
   GRANT ALL PRIVILEGES ON DATABASE invoice_app TO postgres;
   \q
   ```

### Step 3: Install Dependencies

```bash
cd api
pip install -r requirements-postgresql.txt
```

### Step 4: Migrate Data

```bash
python migrate-to-postgresql.py
```

### Step 5: Update Environment

```bash
cp env.postgresql.example .env
# Edit .env with your PostgreSQL connection details
```

## Option 3: Using Cloud PostgreSQL

### Step 1: Set up Cloud Database

Choose one of these providers:
- **AWS RDS:** Create a PostgreSQL instance
- **Google Cloud SQL:** Create a PostgreSQL instance
- **Azure Database:** Create a PostgreSQL server
- **Heroku Postgres:** Add PostgreSQL addon

### Step 2: Get Connection Details

Get your database URL from your cloud provider. It should look like:
```
postgresql://username:password@host:port/database
```

### Step 3: Update Environment

```bash
cp env.postgresql.example .env
```

Edit `.env` and set:
```
DATABASE_URL=postgresql://username:password@host:port/database
```

### Step 4: Migrate Data

```bash
cd api
python migrate-to-postgresql.py
```

## Verification Steps

### 1. Check Database Connection

```bash
cd api
python -c "
from models.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('PostgreSQL version:', result.fetchone()[0])
"
```

### 2. Verify Data Migration

```bash
cd api
python -c "
from models.database import SessionLocal
from models.models import Invoice, Client, User
db = SessionLocal()
print(f'Users: {db.query(User).count()}')
print(f'Clients: {db.query(Client).count()}')
print(f'Invoices: {db.query(Invoice).count()}')
db.close()
"
```

### 3. Test API Endpoints

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/invoices
```

## Troubleshooting

### Common Issues

1. **Connection Refused:**
   - Check if PostgreSQL is running
   - Verify port 5432 is not blocked
   - Check firewall settings

2. **Authentication Failed:**
   - Verify username/password in DATABASE_URL
   - Check pg_hba.conf for authentication method

3. **Database Does Not Exist:**
   - Create the database manually
   - Check database name in connection string

4. **Migration Errors:**
   - Check if SQLite file exists and is readable
   - Verify PostgreSQL connection
   - Check for data type conflicts

### Performance Optimization

1. **Connection Pooling:**
   - Already configured in `database.py`
   - Adjust pool_size and max_overflow as needed

2. **Indexes:**
   - PostgreSQL automatically creates indexes for primary keys
   - Consider adding indexes for frequently queried columns

3. **Vacuum and Analyze:**
   ```sql
   VACUUM ANALYZE;
   ```

## Rollback Plan

If you need to rollback to SQLite:

1. **Stop PostgreSQL services:**
   ```bash
   docker-compose down
   ```

2. **Update environment:**
   ```bash
   # In .env file
   DATABASE_URL=sqlite:///./invoice_app.db
   ```

3. **Restart with SQLite:**
   ```bash
   docker-compose up -d
   ```

## Security Considerations

1. **Change Default Passwords:**
   - Update PostgreSQL user password
   - Use strong, unique passwords

2. **Network Security:**
   - Use SSL connections in production
   - Restrict database access to application servers

3. **Backup Strategy:**
   ```bash
   # Create backup
   pg_dump invoice_app > backup.sql
   
   # Restore backup
   psql invoice_app < backup.sql
   ```

## Production Deployment

1. **Environment Variables:**
   - Use strong SECRET_KEY
   - Set DEBUG=False
   - Configure proper DATABASE_URL

2. **SSL Configuration:**
   ```bash
   # Add to DATABASE_URL
   DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
   ```

3. **Monitoring:**
   - Set up database monitoring
   - Monitor connection pool usage
   - Set up alerts for disk space

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Verify database connection
3. Check environment variables
4. Review PostgreSQL logs: `docker-compose logs postgres`

## Next Steps

After successful migration:

1. Test all application features
2. Update backup procedures
3. Monitor performance
4. Consider setting up read replicas for high availability 