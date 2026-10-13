"""Storage convergence contract without importing live runtime modules."""

import ast
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]

STORAGE_CASES = (
    ("backend/main.py", "MISSION_STORAGE_PATH"),
    ("backend/main.py", "MISSION_RECORD_STORAGE_PATH"),
    ("backend/main.py", "MISSION_EVIDENCE_STORAGE_PATH"),
    ("backend/main.py", "MISSION_DELIVERY_LEASE_STORAGE_PATH"),
    ("backend/main.py", "CONTROL_MISSION_STORAGE_PATH"),
    ("backend/main.py", "CONTROL_MISSION_RECORD_STORAGE_PATH"),
    ("backend/main.py", "CONTROL_MISSION_DELIVERY_LEASE_STORAGE_PATH"),
    ("backend/main.py", "EXECUTION_SECURITY_SEQUENCE_STORAGE_PATH"),
    ("backend/main.py", "EXECUTION_SECURITY_SEQUENCE_BINDING_STORAGE_PATH"),
    ("backend/main.py", "CONTROL_SECURITY_SEQUENCE_STORAGE_PATH"),
    ("backend/main.py", "CONTROL_SECURITY_SEQUENCE_BINDING_STORAGE_PATH"),
    (
        "backend/integrations/telegram_listener.py",
        "TELEGRAM_DISPATCH_PROGRESS_STORAGE_PATH",
    ),
)


def _assignment_value(module: ast.Module, name: str) -> ast.expr:
    matches = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                matches.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                matches.append(node.value)

    assert len(matches) == 1, f"{name}: expected one top-level assignment"
    return matches[0]


def _leftmost_root(expression: ast.expr) -> ast.expr:
    current = expression
    while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
        current = current.left
    return current


@pytest.mark.parametrize(
    ("source", "declaration"),
    STORAGE_CASES,
    ids=[name for _, name in STORAGE_CASES],
)
def test_durable_storage_uses_shared_authority(
    source: str,
    declaration: str,
) -> None:
    """All durable stores must use the configured shared root."""
    syntax = ast.parse(
        (REPO / source).read_text(encoding="utf-8"),
        filename=source,
    )
    expression = _assignment_value(syntax, declaration)
    root = _leftmost_root(expression)

    assert isinstance(root, ast.Name), (
        f"{source}: {declaration} has no shared root name"
    )
    assert root.id == "TODOBA_CONTROL_PLANE_DATA_ROOT", (
        f"{source}: {declaration} uses {root.id}, not shared authority"
    )


def test_shared_root_preserves_default_data_contract() -> None:
    """Without an override, the established relative data root remains."""
    source = REPO / "backend/config.py"
    syntax = ast.parse(source.read_text(encoding="utf-8"))
    expression = _assignment_value(
        syntax,
        "TODOBA_CONTROL_PLANE_DATA_ROOT",
    )
    text = ast.unparse(expression)

    assert "TODOBA_CONTROL_PLANE_DATA_ROOT" in text
    assert "'data'" in text or '"data"' in text
