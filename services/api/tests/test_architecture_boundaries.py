"""Import rules from docs/architecture/backend-boundaries.md, checked statically."""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "ai_knowledge_platform"
PACKAGE_NAME = "ai_knowledge_platform"

DOMAIN_MODULES = (
    "documents/domain.py",
    "retrieval/domain.py",
    "retrieval/chunking.py",
    "answers/domain.py",
    "answers/prompt.py",
)

# Each infrastructure library may be imported by exactly one adapter module.
SINGLE_OWNER_LIBRARIES = {
    "openai": "answers/openai_generator.py",
    "sqlite3": "retrieval/repository.py",
    "pypdf": "documents/extraction.py",
}


def _imported_roots(path: Path) -> set[str]:
    """Return imported top-level names; package imports keep their module path."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        else:
            continue
        for name in names:
            roots.add(name if name.startswith(f"{PACKAGE_NAME}.") else name.split(".")[0])
    return roots


def _module_name(relative_path: str) -> str:
    return f"{PACKAGE_NAME}." + relative_path.removesuffix(".py").replace("/", ".")


def _source_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


@pytest.mark.parametrize("relative_path", DOMAIN_MODULES)
def test_domain_modules_import_only_stdlib_and_domain(relative_path: str) -> None:
    allowed_internal = {_module_name(path) for path in DOMAIN_MODULES}
    roots = _imported_roots(PACKAGE_ROOT / relative_path)

    internal = {name for name in roots if name.startswith(f"{PACKAGE_NAME}.")}
    external = roots - internal

    assert internal <= allowed_internal, f"{relative_path} imports non-domain code"
    third_party = external - sys.stdlib_module_names
    assert not third_party, f"{relative_path} imports third-party code: {third_party}"


@pytest.mark.parametrize(("library", "owner"), sorted(SINGLE_OWNER_LIBRARIES.items()))
def test_infrastructure_library_has_a_single_owner(library: str, owner: str) -> None:
    importers = {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in _source_files()
        if library in _imported_roots(path)
    }

    assert importers == {owner}


def test_domain_module_list_matches_files() -> None:
    for relative_path in DOMAIN_MODULES:
        assert (PACKAGE_ROOT / relative_path).is_file(), relative_path
