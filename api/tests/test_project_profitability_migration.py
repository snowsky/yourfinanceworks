"""Isolated schema tests. Run with --noconftest; never use the shared tenant DB."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.fixture
def connection():
    # A dedicated disposable database may be supplied for PostgreSQL verification.
    engine = sa.create_engine(os.getenv("PROFITABILITY_TEST_DATABASE_URL", "sqlite://"))
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.commit()
        transaction = conn.begin()
        yield conn
        transaction.rollback()
    engine.dispose()


def legacy_schema(conn, expense_mapping=True):
    metadata = sa.MetaData()
    for name in ("users", "clients", "invoices", "invoice_items", "projects", "project_tasks"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
    metadata.tables["users"].append_column(sa.Column("is_active", sa.Boolean, server_default=sa.true()))
    sa.Table("time_entries", metadata, sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("amount", sa.Float), sa.Column("hourly_rate", sa.Float))
    expense_columns = [sa.Column("id", sa.Integer, primary_key=True)]
    if expense_mapping:
        expense_columns.extend([sa.Column("project_id", sa.Integer), sa.Column("invoiced", sa.Boolean)])
    sa.Table("expenses", metadata, *expense_columns)
    metadata.create_all(conn)
    for name in ("users", "projects", "invoice_items", "expenses"):
        conn.execute(metadata.tables[name].insert().values(id=1))
    conn.execute(metadata.tables["time_entries"].insert().values(id=1, amount=125.5, hourly_rate=100))


def migrate(conn):
    import importlib.util
    path = Path(__file__).parents[1] / "alembic/versions/028_add_project_profitability.py"
    assert path.exists(), "profitability migration is missing"
    spec = importlib.util.spec_from_file_location("profitability_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "027_add_net_worth_tables"
    with Operations.context(MigrationContext.configure(conn)):
        migration.upgrade()


def test_old_tenant_upgrade_preserves_time_and_unknown_costs(connection):
    legacy_schema(connection)
    migrate(connection)
    assert connection.exec_driver_sql("SELECT amount, hourly_rate FROM time_entries").one() == (125.5, 100)
    assert connection.exec_driver_sql("SELECT count(*) FROM time_entry_costs").scalar() == 0
    connection.exec_driver_sql("UPDATE expenses SET project_id=1")
    from core.models.models_per_tenant import Expense
    assert connection.execute(sa.select(Expense.project_id).where(Expense.id == 1)).scalar() == 1


def test_new_tenant_has_same_schema(connection):
    from core.models.models_per_tenant import Base, Expense
    import plugins.time_tracking.models
    from plugins.time_tracking.cost_models import TimeEntryCost
    Base.metadata.create_all(connection)
    assert "project_id" in Expense.__table__.columns
    assert "invoiced" in Expense.__table__.columns
    columns = {c["name"]: c for c in sa.inspect(connection).get_columns("time_entry_costs")}
    assert columns["hourly_cost"]["type"].precision == 19
    assert columns["hourly_cost"]["type"].scale == 6
    assert TimeEntryCost.__table__.metadata is Base.metadata
    # Compare the additive migration against the metadata initializer.
    upgraded = sa.create_engine("sqlite://")
    with upgraded.begin() as old:
        legacy_schema(old)
        migrate(old)
        for table in ("contributor_cost_rates", "time_entry_costs", "time_entry_cost_expenses", "project_invoice_sources"):
            actual = sa.inspect(connection).get_columns(table)
            prior = sa.inspect(old).get_columns(table)
            assert [(c["name"], c["nullable"]) for c in actual] == [(c["name"], c["nullable"]) for c in prior]
    upgraded.dispose()


def test_snapshot_and_source_uniqueness(connection):
    legacy_schema(connection)
    migrate(connection)
    connection.exec_driver_sql("INSERT INTO time_entry_costs (time_entry_id, method, hourly_cost, currency, version) VALUES (1, 'hourly', 40, 'USD', 1)")
    for sql in (
        "INSERT INTO time_entry_costs (time_entry_id, method, hourly_cost, currency, version) VALUES (1, 'hourly', 50, 'USD', 1)",
        "INSERT INTO project_invoice_sources (invoice_item_id, project_id, time_entry_id, expense_id) VALUES (1, 1, 1, 1)",
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.exec_driver_sql(sql)
    connection.exec_driver_sql("INSERT INTO project_invoice_sources (invoice_item_id, project_id, time_entry_id) VALUES (1, 1, 1)")
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.exec_driver_sql("INSERT INTO project_invoice_sources (invoice_item_id, project_id, time_entry_id) VALUES (1, 1, 1)")
    connection.exec_driver_sql("INSERT INTO time_entry_cost_expenses (time_entry_id, expense_id) VALUES (1, 1)")
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.exec_driver_sql("INSERT INTO time_entry_cost_expenses (time_entry_id, expense_id) VALUES (1, 1)")


def test_core_metadata_without_plugin_is_creatable():
    script = """
import sys
from importlib.abc import MetaPathFinder
class NoTimePlugin(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('plugins.time_tracking'):
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, NoTimePlugin())
from core.models.models_per_tenant import Base
from sqlalchemy import create_engine
assert 'projects' not in Base.metadata.tables
Base.metadata.create_all(create_engine('sqlite://'))
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_rate_history_survives_identity_removal(connection):
    legacy_schema(connection)
    migrate(connection)
    connection.exec_driver_sql("INSERT INTO contributor_cost_rates (id, user_id, currency, effective_from, hourly_cost) VALUES (1, 1, 'USD', '2026-01-01', 40)")
    connection.exec_driver_sql("INSERT INTO time_entry_costs (time_entry_id, method, hourly_cost, currency, source_rate_id) VALUES (1, 'hourly', 40, 'USD', 1)")
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.exec_driver_sql("INSERT INTO contributor_cost_rates (id, user_id, currency, effective_from, hourly_cost) VALUES (2, 1, 'USD', '2026-01-01', 50)")
    connection.exec_driver_sql("UPDATE users SET is_active=false WHERE id=1")
    assert connection.exec_driver_sql("SELECT hourly_cost FROM time_entry_costs").scalar() == 40
    connection.exec_driver_sql("DELETE FROM users WHERE id=1")
    assert connection.exec_driver_sql("SELECT user_id, hourly_cost FROM contributor_cost_rates").one() == (None, 40)
    assert connection.exec_driver_sql("SELECT hourly_cost, source_rate_id FROM time_entry_costs").one() == (40, 1)
    connection.exec_driver_sql("DELETE FROM contributor_cost_rates WHERE id=1")
    assert connection.exec_driver_sql("SELECT hourly_cost, source_rate_id FROM time_entry_costs").one() == (40, None)


def test_migration_revision_graph_reaches_profitability():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["028_project_profitability"]
    assert [revision.revision for revision in scripts.iterate_revisions("heads", "027_add_net_worth_tables")] == ["028_project_profitability"]


def test_metadata_created_legacy_expenses_gain_mapping(connection):
    legacy_schema(connection, expense_mapping=False)
    migrate(connection)
    connection.exec_driver_sql("UPDATE expenses SET project_id=1, invoiced=false")
    assert connection.exec_driver_sql("SELECT project_id, invoiced FROM expenses").one() == (1, False)


def test_invalid_cost_methods_are_rejected(connection):
    legacy_schema(connection)
    migrate(connection)
    for values in ("'hourly', NULL", "'hourly', -1", "'supplier_expense', 40", "'unknown', 40"):
        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.exec_driver_sql(f"INSERT INTO time_entry_costs (time_entry_id, method, hourly_cost, currency) VALUES (1, {values}, 'USD')")
    connection.exec_driver_sql("INSERT INTO time_entry_costs (time_entry_id, method, hourly_cost, currency) VALUES (1, 'hourly', 0, 'USD')")
    assert connection.exec_driver_sql("SELECT hourly_cost FROM time_entry_costs").scalar() == 0
