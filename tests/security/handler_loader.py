"""Load selected real handlers without application startup or shared DB fixtures.

Only dependency wiring is substituted by each test. Handler bodies come directly
from source, so assertions exercise behavior rather than matching source strings.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_functions(relative_path, names, namespace):
    tree = ast.parse((ROOT / relative_path).read_text())
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            selected.append(node)
    found = {node.name for node in selected}
    if found != set(names):
        raise ValueError(f"Missing handlers: {set(names) - found}")
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(ROOT / relative_path), "exec"), namespace)
    return namespace
