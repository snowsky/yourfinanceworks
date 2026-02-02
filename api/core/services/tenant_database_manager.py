import os
import logging
from typing import Dict, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from core.models.models import Base, Tenant
from core.models.database import SQLALCHEMY_DATABASE_URL
from core.models.models_per_tenant import Base as TenantBase

logger = logging.getLogger(__name__)

class TenantDatabaseManager:
    """
    Manages database connections and operations for individual tenants
    """

    def __init__(self):
        self.tenant_engines: Dict[str, Engine] = {}
        self.tenant_sessions: Dict[str, sessionmaker] = {}
        self.master_engine = None
        self.master_session = None
        self._init_master_connection()

    def _init_master_connection(self):
        """Initialize connection to master database for tenant management"""
        try:
            self.master_engine = create_engine(
                SQLALCHEMY_DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10
            )
            self.master_session = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=self.master_engine
            )
            logger.info("Master database connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize master database: {e}")
            raise

    def get_tenant_database_url(self, tenant_id: int) -> str:
        """Generate database URL for a specific tenant"""
        base_url = SQLALCHEMY_DATABASE_URL

        # Extract components from base URL
        if base_url.startswith("postgresql://"):
            # Example: postgresql://user:password@host:port/database
            parts = base_url.split("/")
            base_connection = "/".join(parts[:-1])
            return f"{base_connection}/tenant_{tenant_id}"
        else:
            raise ValueError(f"Unsupported database URL format: {base_url}")

    def create_tenant_database(self, tenant_id: int, tenant_name: str) -> bool:
        """Create a new database for a tenant"""
        try:
            db_name = f"tenant_{tenant_id}"
            logger.info(f"Creating database for tenant {tenant_id}: {db_name}")

            # Check if database already exists and drop it to ensure clean schema
            try:
                with self.master_engine.connect() as conn:
                    conn.execute(text("COMMIT"))
                    # Check if database exists
                    result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
                    if result.fetchone():
                        logger.info(f"Database {db_name} already exists, dropping to recreate with correct schema")
                        # Terminate connections before dropping
                        self.terminate_db_connections(db_name)
                        # Drop existing database
                        conn.execute(text(f"DROP DATABASE {db_name}"))
                        logger.info(f"Dropped existing database {db_name}")
            except Exception as e:
                logger.warning(f"Could not check/drop existing database {db_name}: {e}")

            # Connect to master database to create new database
            with self.master_engine.connect() as conn:
                # Use autocommit mode for database creation
                conn.execute(text("COMMIT"))
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"Database {db_name} created successfully")

            # Initialize schema in new tenant database
            self._init_tenant_schema(tenant_id)

            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to create database for tenant {tenant_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating database for tenant {tenant_id}: {e}")
            return False

    def recreate_tenant_database(self, tenant_id: int, tenant_name: str) -> bool:
        """Recreate a tenant database with the correct schema"""
        try:
            db_name = f"tenant_{tenant_id}"
            logger.info(f"Recreating database for tenant {tenant_id}: {db_name}")

            # Close any existing connections to this database
            tenant_key = f"tenant_{tenant_id}"
            if tenant_key in self.tenant_engines:
                self.tenant_engines[tenant_key].dispose()
                del self.tenant_engines[tenant_key]
                del self.tenant_sessions[tenant_key]

            # Terminate connections before dropping
            self.terminate_db_connections(db_name)
            # Drop and recreate the database
            with self.master_engine.connect() as conn:
                conn.execute(text("COMMIT"))
                conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"Database {db_name} recreated successfully")

            # Initialize schema in new tenant database
            self._init_tenant_schema(tenant_id)

            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to recreate database for tenant {tenant_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error recreating database for tenant {tenant_id}: {e}")
            return False

    def _init_tenant_schema(self, tenant_id: int):
        """Initialize schema in tenant database"""
        try:
            tenant_url = self.get_tenant_database_url(tenant_id)
            tenant_engine = create_engine(
                tenant_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10
            )

            # Create all tables in tenant database
            TenantBase.metadata.create_all(bind=tenant_engine)

            # Create prompt templates tables (uses a different Base class)
            # Import here to avoid circular imports
            from commercial.prompt_management.models.prompt_templates import PromptTemplate, PromptUsageLog
            from core.models.database import Base as DatabaseBase
            DatabaseBase.metadata.create_all(bind=tenant_engine, tables=[
                PromptTemplate.__table__,
                PromptUsageLog.__table__
            ])
            logger.info(f"Created prompt templates tables for tenant {tenant_id}")

            # Initialize any default data if needed
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
            db = SessionLocal()

            try:
                # Add any tenant-specific initialization here
                # For example, create default settings, currencies, etc.
                self._create_tenant_defaults(db)

                # Seed default prompt templates
                self._seed_prompt_templates(db)

                db.commit()
                logger.info(f"Schema initialized for tenant {tenant_id}")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to initialize schema for tenant {tenant_id}: {e}")
            raise

    def _create_tenant_defaults(self, db_session):
        """Create default data for a new tenant database"""
        # Import here to avoid circular imports
        from core.models.models_per_tenant import SupportedCurrency

        # Create default supported currencies
        default_currencies = [
            {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
            {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
            {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_places": 2},
            {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_places": 0},
            {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "decimal_places": 2},
            {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "decimal_places": 2},
            {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF", "decimal_places": 2},
            {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "decimal_places": 2},
            {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimal_places": 2},
            {"code": "BRL", "name": "Brazilian Real", "symbol": "R$", "decimal_places": 2},
        ]

        for currency_data in default_currencies:
            currency = SupportedCurrency(**currency_data)
            db_session.add(currency)

    def _seed_prompt_templates(self, db_session):
        """Seed default prompt templates for a new tenant database"""
        import json
        from commercial.prompt_management.models.prompt_templates import PromptTemplate
        from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES

        # Check if templates already exist
        existing_count = db_session.query(PromptTemplate).count()
        if existing_count > 0:
            logger.info("Prompt templates already exist, skipping seed")
            return

        for template_data in DEFAULT_PROMPT_TEMPLATES:
            # Create a copy to modify for DB insertion
            db_template_data = template_data.copy()

            # Serialize JSON fields
            if isinstance(db_template_data.get('template_variables'), (list, dict)):
                db_template_data['template_variables'] = json.dumps(db_template_data['template_variables'])

            if isinstance(db_template_data.get('default_values'), (list, dict)):
                db_template_data['default_values'] = json.dumps(db_template_data['default_values'])

            if isinstance(db_template_data.get('provider_overrides'), (list, dict)):
                db_template_data['provider_overrides'] = json.dumps(db_template_data['provider_overrides'])

            template = PromptTemplate(**db_template_data)
            db_session.add(template)

        logger.info(f"Seeded {len(DEFAULT_PROMPT_TEMPLATES)} default prompt templates")

    def tenant_database_exists(self, tenant_id: int) -> bool:
        """Check if a tenant database exists"""
        try:
            db_name = f"tenant_{tenant_id}"
            with self.master_engine.connect() as conn:
                result = conn.execute(text(
                    f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"
                ))
                return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check if tenant database exists for tenant {tenant_id}: {e}")
            return False

    def get_tenant_engine(self, tenant_id: int) -> Engine:
        """Get or create database engine for a tenant"""
        tenant_key = f"tenant_{tenant_id}"

        if tenant_key not in self.tenant_engines:
            # Check if tenant database exists before creating connection
            if not self.tenant_database_exists(tenant_id):
                raise ValueError(f"Tenant database does not exist for tenant {tenant_id}")

            tenant_url = self.get_tenant_database_url(tenant_id)

            self.tenant_engines[tenant_key] = create_engine(
                tenant_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10
            )

            self.tenant_sessions[tenant_key] = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.tenant_engines[tenant_key]
            )

            logger.info(f"Created database connection for {tenant_key}")

        return self.tenant_engines[tenant_key]

    def get_tenant_session(self, tenant_id: int) -> sessionmaker:
        """Get database session factory for a tenant"""
        tenant_key = f"tenant_{tenant_id}"

        if tenant_key not in self.tenant_sessions:
            # Check if tenant database exists before creating session
            if not self.tenant_database_exists(tenant_id):
                raise ValueError(f"Tenant database does not exist for tenant {tenant_id}")
            self.get_tenant_engine(tenant_id)  # This will create both engine and session

        return self.tenant_sessions[tenant_key]

    def drop_tenant_database(self, tenant_id: int) -> bool:
        """Drop a tenant database (use with caution!)"""
        try:
            db_name = f"tenant_{tenant_id}"
            logger.warning(f"Dropping database for tenant {tenant_id}: {db_name}")

            # Close any existing connections
            tenant_key = f"tenant_{tenant_id}"
            if tenant_key in self.tenant_engines:
                self.tenant_engines[tenant_key].dispose()
                del self.tenant_engines[tenant_key]
                del self.tenant_sessions[tenant_key]

            # Terminate connections before dropping
            self.terminate_db_connections(db_name)
            # Drop the database
            with self.master_engine.connect() as conn:
                conn.execute(text("COMMIT"))
                conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
                logger.info(f"Database {db_name} dropped successfully")

            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to drop database for tenant {tenant_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error dropping database for tenant {tenant_id}: {e}")
            return False

    # Alias for compatibility with tests
    delete_tenant_database = drop_tenant_database

    def migrate_tenant_schema(self, tenant_id: int):
        """Apply schema migrations to a tenant database"""
        try:
            tenant_engine = self.get_tenant_engine(tenant_id)

            # Apply any pending migrations
            TenantBase.metadata.create_all(bind=tenant_engine)

            logger.info(f"Schema migration completed for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Failed to migrate schema for tenant {tenant_id}: {e}")
            raise

    def get_all_tenant_databases(self) -> list:
        """Get list of all tenant database names"""
        try:
            with self.master_engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%'"
                ))
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get tenant databases: {e}")
            return []

    def get_existing_tenant_ids(self) -> list:
        """Get list of tenant IDs that have both master record and database

        Optimized to use a single JOIN query instead of N+1 queries
        """
        try:
            # Get tenant IDs from master database and check database existence in one query
            master_session_factory = self.master_session
            if master_session_factory is None:
                return []

            master_db = master_session_factory()
            try:
                # Use a single query to get active tenants that have databases
                # This joins the tenants table with pg_database to check existence
                query = text("""
                    SELECT t.id 
                    FROM tenants t
                    INNER JOIN pg_database d ON d.datname = 'tenant_' || t.id
                    WHERE t.is_active = TRUE
                    ORDER BY t.id
                """)
                tenant_rows = master_db.execute(query).fetchall()
                existing_tenant_ids = [row[0] for row in tenant_rows]

                logger.debug(f"Found {len(existing_tenant_ids)} active tenants with databases")
                return existing_tenant_ids
            finally:
                master_db.close()

        except Exception as e:
            logger.error(f"Failed to get existing tenant IDs: {e}")
            # Fallback to old method if the optimized query fails
            try:
                master_db = master_session_factory()
                try:
                    tenant_rows = master_db.execute(text("SELECT id FROM tenants WHERE is_active = TRUE")).fetchall()
                    master_tenant_ids = [row[0] for row in tenant_rows]
                finally:
                    master_db.close()

                # Filter to only those with existing databases
                existing_tenant_ids = []
                for tenant_id in master_tenant_ids:
                    if self.tenant_database_exists(tenant_id):
                        existing_tenant_ids.append(tenant_id)
                    else:
                        logger.warning(f"Tenant {tenant_id} exists in master but database is missing")

                return existing_tenant_ids
            except Exception as fallback_error:
                logger.error(f"Fallback method also failed: {fallback_error}")
                return []

    def close_all_connections(self):
        """Close all database connections"""
        for engine in self.tenant_engines.values():
            engine.dispose()

        if self.master_engine:
            self.master_engine.dispose()

        self.tenant_engines.clear()
        self.tenant_sessions.clear()

        logger.info("All database connections closed")

    def terminate_db_connections(self, db_name):
        """Terminate all connections to a specific database except the current one."""
        try:
            with self.master_engine.connect() as conn:
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = '{db_name}' AND pid <> pg_backend_pid();
                """))
                logger.info(f"Terminated all connections to database {db_name}")
        except Exception as e:
            logger.warning(f"Failed to terminate connections for {db_name}: {e}")

    def sync_postgres_sequences(self, db_session):
        """Sync all Postgres sequences with current table max IDs to avoid UniqueViolation on next inserts"""
        try:
            # Only relevant for Postgres
            if not str(db_session.bind.url).startswith("postgresql"):
                return True

            # Query to get all sequences and their tables/columns
            # This is a bit complex in Postgres but can be automated
            query = text("""
                SELECT
                    t.relname AS table_name,
                    a.attname AS column_name,
                    s.relname AS sequence_name
                FROM
                    pg_class s
                    JOIN pg_depend d ON d.objid = s.oid
                    JOIN pg_class t ON d.refobjid = t.oid
                    JOIN pg_attribute a ON (d.refobjid = a.attrelid AND d.refobjsubid = a.attnum)
                WHERE
                    s.relkind = 'S'
                    AND d.deptype = 'a'
                    AND t.relname NOT LIKE 'pg_%'
            """)

            sequences = db_session.execute(query).fetchall()

            for table_name, column_name, sequence_name in sequences:
                # Update sequence to max(id) + 1
                sync_query = text(f"""
                    SELECT setval('{sequence_name}', (SELECT COALESCE(MAX({column_name}), 0) + 1 FROM {table_name}), false)
                """)
                db_session.execute(sync_query)

            db_session.commit()
            logger.info("Successfully synchronized Postgres sequences")
            return True
        except Exception as e:
            logger.error(f"Failed to synchronize Postgres sequences: {e}")
            db_session.rollback()
            return False

# Global instance
tenant_db_manager = TenantDatabaseManager()
