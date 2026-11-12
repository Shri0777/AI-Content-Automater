"""Tests for scripts/check_readability.py, the beginner-readability checker."""

from pathlib import Path

from scripts.check_readability import check_file, find_python_files

PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def write_sample(folder, text):
    """Save some Python code to a file and return the file's path."""
    path = folder / "sample.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_clean_file_has_no_problems(tmp_path):
    path = write_sample(
        tmp_path, '"""A tidy module."""\n\n\ndef add(a, b):\n    return a + b\n'
    )

    problems = check_file(path, "sample.py")

    assert problems == []


def test_missing_module_docstring_is_reported(tmp_path):
    path = write_sample(tmp_path, "x = 1\n")

    problems = check_file(path, "sample.py")

    assert len(problems) == 1
    assert "docstring" in problems[0]


def test_empty_file_is_allowed(tmp_path):
    path = write_sample(tmp_path, "")

    problems = check_file(path, "sample.py")

    assert problems == []


def test_lambda_is_reported(tmp_path):
    path = write_sample(tmp_path, '"""Doc."""\n\ndouble = lambda n: n * 2\n')

    problems = check_file(path, "sample.py")

    assert "lambda" in problems[0]


def test_async_function_is_reported(tmp_path):
    path = write_sample(tmp_path, '"""Doc."""\n\n\nasync def fetch():\n    return 1\n')

    problems = check_file(path, "sample.py")

    assert "async" in problems[0]


def test_generator_is_reported(tmp_path):
    path = write_sample(tmp_path, '"""Doc."""\n\n\ndef numbers():\n    yield 1\n')

    problems = check_file(path, "sample.py")

    assert "yield" in problems[0]


def test_star_arguments_are_reported(tmp_path):
    path = write_sample(
        tmp_path, '"""Doc."""\n\n\ndef show(*args, **kwargs):\n    return args\n'
    )

    problems = check_file(path, "sample.py")

    assert "*args" in problems[0]


def test_django_command_handle_may_use_star_arguments(tmp_path):
    code = '"""Doc."""\n\n\ndef handle(self, *args, **options):\n    return None\n'
    path = write_sample(tmp_path, code)

    problems = check_file(path, "sample.py")

    assert problems == []


def test_long_function_is_reported(tmp_path):
    body = ""
    for number in range(31):
        body = body + f"    value_{number} = {number}\n"
    path = write_sample(tmp_path, '"""Doc."""\n\n\ndef long_function():\n' + body)

    problems = check_file(path, "sample.py")

    assert "long_function" in problems[0]


def test_long_file_is_reported(tmp_path):
    path = write_sample(tmp_path, '"""Doc."""\n' + "x = 1\n" * 250)

    problems = check_file(path, "sample.py")

    assert "251 lines" in problems[0]


def test_migrations_and_virtual_environments_are_skipped(tmp_path):
    (tmp_path / "app" / "migrations").mkdir(parents=True)
    (tmp_path / "app" / "migrations" / "0001_initial.py").write_text("x = 1\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "library.py").write_text("x = 1\n")
    (tmp_path / "app" / "models.py").write_text('"""Doc."""\n')

    files = find_python_files(tmp_path)

    assert files == [tmp_path / "app" / "models.py"]


def test_the_whole_project_follows_the_readability_rules():
    all_problems = []
    for path in find_python_files(PROJECT_FOLDER):
        all_problems = all_problems + check_file(path, str(path))

    assert all_problems == []
