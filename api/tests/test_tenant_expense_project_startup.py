"""Exercise the startup reconciler on an existing DB without importing app startup."""
import ast
import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def startup_reconciler():
    tree = ast.parse((Path(__file__).parents[1] / 'db_init.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'ensure_tenant_required_columns')
    namespace = dict(create_engine=create_engine, inspect=inspect, text=text, logger=logging.getLogger(__name__))
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-startup-reconciler>', 'exec'), namespace)
    return namespace['ensure_tenant_required_columns']


def test_existing_expenses_gain_project_mapping_without_losing_data(tmp_path):
    url = f'sqlite:///{tmp_path}/tenant.db'
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE expenses (id INTEGER PRIMARY KEY, amount FLOAT)'))
        conn.execute(text('INSERT INTO expenses (id, amount) VALUES (1, 125.5)'))
    ensure = startup_reconciler()
    assert ensure(url, 1)
    assert ensure(url, 1)
    with engine.connect() as conn:
        assert {'project_id', 'invoiced'} <= {c['name'] for c in inspect(conn).get_columns('expenses')}
        assert conn.execute(text('SELECT amount, project_id, invoiced FROM expenses')).one() == (125.5, None, False)
        assert 'ix_expenses_project_id' in {i['name'] for i in inspect(conn).get_indexes('expenses')}
    engine.dispose()


def test_existing_project_assignments_and_billed_flags_are_preserved(tmp_path):
    url = f'sqlite:///{tmp_path}/existing.db'
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE expenses (id INTEGER PRIMARY KEY, project_id INTEGER, invoiced BOOLEAN)'))
        conn.execute(text('INSERT INTO expenses VALUES (1, 41, TRUE)'))
    assert startup_reconciler()(url, 1)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT project_id, invoiced FROM expenses')).one() == (41, True)
    engine.dispose()
