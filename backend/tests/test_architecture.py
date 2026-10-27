"""Import rules that keep modules isolated.

* ``module_N`` may import ``core``, ``shared``, its own package, the standard library,
  third-party packages and ``module_M.public_api`` of other modules. Nothing else
  from another module, and never ``app`` (the composition root).
* ``core``, ``shared`` and ``scripts`` never import any ``module_*`` package.
* Relative imports that climb above a module's own package are forbidden.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
MODULE_RE = re.compile(r"^module_(\d+)$")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    imported: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} imports '{self.imported}': {self.reason}"


def _imported_names(node: ast.AST) -> list[tuple[str, int]]:
    """Fully qualified targets of an import statement (module plus names for 'from')."""
    if isinstance(node, ast.Import):
        return [(alias.name, node.lineno) for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [(f"{node.module}.{alias.name}", node.lineno) for alias in node.names] + [
            (node.module, node.lineno)
        ]
    return []


def _check_module_import(owner: str, target: str) -> str | None:
    parts = target.split(".")
    head = parts[0]
    if head == "app":
        return "modules must not import the composition root 'app'"
    match = MODULE_RE.match(head)
    if not match or head == owner:
        return None
    # Accept "module_M" (bare, from 'from module_M import public_api') and module_M.public_api.*
    if len(parts) == 1 or parts[1] == "public_api":
        return None
    return f"only {head}.public_api may be imported from another module"


def find_violations(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        top = rel.parts[0]
        if top in ("venv", "data", "storage", "migrations") or "site-packages" in rel.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        is_module = MODULE_RE.match(top) is not None
        for node in ast.walk(tree):
            # 'import module_M' on its own makes every submodule reachable as an
            # attribute (module_M.models...), so only 'module_M.public_api' may be named.
            if isinstance(node, ast.Import) and is_module:
                for alias in node.names:
                    head = alias.name.split(".")[0]
                    if MODULE_RE.match(head) and head != top and alias.name == head:
                        violations.append(
                            Violation(
                                str(rel),
                                node.lineno,
                                alias.name,
                                f"import {head}.public_api, not the bare package",
                            )
                        )
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                if is_module and node.level > len(rel.parts) - 1:
                    violations.append(
                        Violation(
                            str(rel),
                            node.lineno,
                            "." * node.level + (node.module or ""),
                            "relative import escapes the module package",
                        )
                    )
                continue
            if isinstance(node, ast.ImportFrom) and node.module and is_module:
                # 'from module_M import x' -> x must be public_api
                head = node.module.split(".")[0]
                if MODULE_RE.match(head) and head != top and node.module == head:
                    for alias in node.names:
                        if alias.name != "public_api":
                            violations.append(
                                Violation(
                                    str(rel),
                                    node.lineno,
                                    f"{head}.{alias.name}",
                                    f"only {head}.public_api may be imported from another module",
                                )
                            )
            for target, line in _imported_names(node):
                if is_module:
                    reason = _check_module_import(top, target)
                    if reason:
                        violations.append(Violation(str(rel), line, target, reason))
                elif top in ("core", "shared", "scripts") and MODULE_RE.match(target.split(".")[0]):
                    violations.append(
                        Violation(str(rel), line, target, f"'{top}' must not depend on modules")
                    )
    # De-duplicate (a 'from' import yields both the module and the name)
    return sorted(set(violations), key=lambda v: (v.path, v.line, v.imported))


def test_backend_respects_import_rules() -> None:
    violations = find_violations(BACKEND)
    assert not violations, "Architecture violations:\n" + "\n".join(map(str, violations))


def test_every_module_folder_exists_with_required_files() -> None:
    required = {
        "__init__.py",
        "meta.py",
        "router.py",
        "schemas.py",
        "models.py",
        "repository.py",
        "public_api.py",
        "events.py",
    }
    for number in range(1, 9):
        folder = BACKEND / f"module_{number}"
        assert folder.is_dir(), folder
        present = {p.name for p in folder.iterdir()}
        assert required <= present, f"module_{number} missing {required - present}"
        # A module's business logic is either services.py or a services/ package
        # (a built module may need several service files; see DECISIONS D-026).
        assert "services.py" in present or (folder / "services" / "__init__.py").is_file(), (
            f"module_{number} has neither services.py nor a services package"
        )
        assert (folder / "tests").is_dir()


def test_checker_detects_violations(tmp_path: Path) -> None:
    (tmp_path / "module_2").mkdir()
    (tmp_path / "module_3").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "module_2" / "ok.py").write_text(
        "import os\nfrom core.events import bus\nfrom module_3.public_api import get_x\n"
        "from module_3 import public_api\nimport module_3.public_api\n"
        "from module_2.models import A\n"
    )
    (tmp_path / "module_2" / "bad.py").write_text(
        "from module_3.models import Fieldbook\nimport module_3.repository\n"
        "from module_3 import services\nfrom app.main import app\nfrom ..module_3 import models\n"
    )
    (tmp_path / "core" / "bad.py").write_text("from module_2.public_api import x\n")
    (tmp_path / "module_2" / "bare.py").write_text("import module_3\nx = module_3.models\n")

    found = find_violations(tmp_path)
    assert not any(v.path.endswith("ok.py") for v in found), [str(v) for v in found]
    bad = {v.imported for v in found if v.path.endswith(str(Path("module_2", "bad.py")))}
    assert {"module_3.models", "module_3.repository", "module_3.services", "app.main"} <= bad
    assert any(v.imported.startswith("..") for v in found)
    assert any(v.path.startswith("core") for v in found)
    assert any(v.path.endswith("bare.py") and v.imported == "module_3" for v in found)
