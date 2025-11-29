from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool
from alembic import context

# Add the parent directory to the path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models for autogenerate support
try:
    from core.models.models import Base as MasterBase
    from core.models.models_per_tenant import Base as TenantBase
except ImportError:
    MasterBase = None
    TenantBase = None

# Determine which database to migrate based on environment variable
db_type = os.getenv('ALEMBIC_DB_TYPE', 'master')  # 'master' or 'tenant'

if db_type == 'master':
    target_metadata = MasterBase.metadata if MasterBase else None
else:
    target_metadata = TenantBase.metadata if TenantBase else None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Get database URL based on type
    if db_type == 'master':
        url = os.getenv('DATABASE_URL') or config.get_main_option("sqlalchemy.url")
    else:
        # For tenant databases, use the tenant-specific URL
        tenant_id = os.getenv('TENANT_ID')
        if tenant_id:
            base_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432')
            url = base_url.replace('/invoice_master', f'/tenant_{tenant_id}')
        else:
            url = config.get_main_option("sqlalchemy.url")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get database URL based on type
    if db_type == 'master':
        url = os.getenv('DATABASE_URL') or config.get_main_option("sqlalchemy.url")
    else:
        # For tenant databases, use the tenant-specific URL
        tenant_id = os.getenv('TENANT_ID')
        if tenant_id:
            base_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432')
            url = base_url.replace('/invoice_master', f'/tenant_{tenant_id}')
        else:
            url = config.get_main_option("sqlalchemy.url")
    
    # Create engine with the appropriate URL
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
