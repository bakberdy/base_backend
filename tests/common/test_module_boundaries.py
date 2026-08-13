import ast
from pathlib import Path


def test_business_modules_do_not_import_each_other() -> None:
    modules_root = Path("app/modules")
    violations: list[str] = []

    for source_path in modules_root.glob("*/**/*.py"):
        owner = source_path.relative_to(modules_root).parts[0]
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            parts = node.module.split(".")
            if len(parts) < 3 or parts[:2] != ["app", "modules"]:
                continue
            imported_module = parts[2]
            if imported_module != owner:
                violations.append(f"{source_path}:{node.lineno} imports {node.module}")

    assert violations == []
