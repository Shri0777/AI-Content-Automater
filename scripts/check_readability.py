"""Check that our Python files follow the beginner-readable code standard.

Run it with:   uv run python scripts/check_readability.py

It reads every Python file we wrote (it skips migrations and virtual
environments) and reports each rule a file breaks. It exits with code 1 when
anything is wrong, so CI fails. The rules come from design/code-standard.md.
Ruff checks the remaining rules (complexity, argument counts, imports).
"""

import ast
import sys
from pathlib import Path

MAX_FILE_LINES = 250
MAX_FUNCTION_LINES = 30

# Folders that hold code we did not write by hand.
SKIPPED_FOLDERS = [
    ".git",
    ".venv",
    ".venv-legacy-v3",
    "venv",
    "migrations",
    "__pycache__",
    "frontend",
    "frontend_ui",
]

# Django requires management commands to define handle(self, *args, **options),
# so that one function name may use *args and **kwargs.
STAR_ARGUMENTS_ALLOWED_IN = ["handle"]


def find_python_files(folder):
    """Return every Python file under folder that we wrote ourselves.

    Skipped folders (such as virtual environments, with thousands of files)
    are never opened. For each sub-folder, the function calls itself to
    collect that folder's files too.
    """
    python_files = []
    for path in sorted(folder.iterdir()):
        if path.name in SKIPPED_FOLDERS:
            continue
        if path.is_dir():
            python_files = python_files + find_python_files(path)
        elif path.suffix == ".py":
            python_files.append(path)
    return python_files


def check_function(node):
    """Return a problem with one function definition, or None if it is fine."""
    uses_star_arguments = node.args.vararg is not None or node.args.kwarg is not None
    if uses_star_arguments and node.name not in STAR_ARGUMENTS_ALLOWED_IN:
        return f"function '{node.name}' uses *args or **kwargs; use named parameters"
    line_count = node.end_lineno - node.lineno + 1
    if line_count > MAX_FUNCTION_LINES:
        return f"function '{node.name}' has {line_count} lines (limit 30)"
    return None


def check_node(node):
    """Return the rule this piece of code breaks, or None if it is fine."""
    if isinstance(node, ast.AsyncFunctionDef):
        return "async functions are not allowed; use a normal function"
    if isinstance(node, ast.Lambda):
        return "lambda is not allowed; write a small named function"
    if isinstance(node, ast.Yield) or isinstance(node, ast.YieldFrom):
        return "generators (yield) are not allowed; build and return a list"
    if isinstance(node, ast.FunctionDef):
        return check_function(node)
    return None


def check_file(path, display_name):
    """Return a list of readable problem messages for one file."""
    text = path.read_text(encoding="utf-8")
    problems = []
    line_count = len(text.splitlines())
    if line_count > MAX_FILE_LINES:
        problems.append(f"{display_name}: file has {line_count} lines (limit 250)")
    if text.strip() == "":
        return problems
    tree = ast.parse(text, filename=display_name)
    if ast.get_docstring(tree) is None:
        problems.append(f"{display_name}: add a docstring at the top of the file")
    for node in ast.walk(tree):
        problem = check_node(node)
        if problem is not None:
            problems.append(f"{display_name}:{node.lineno}: {problem}")
    return problems


def main():
    """Check the whole project and print every problem found."""
    root_folder = Path(__file__).resolve().parent.parent
    all_problems = []
    for path in find_python_files(root_folder):
        display_name = str(path.relative_to(root_folder))
        all_problems = all_problems + check_file(path, display_name)
    for problem in all_problems:
        print(problem)
    if all_problems:
        print(f"\n{len(all_problems)} readability problem(s) found.")
        sys.exit(1)
    print("All files follow the readability rules.")


if __name__ == "__main__":
    main()
