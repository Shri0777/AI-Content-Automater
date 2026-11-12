"""The guide documents must keep up with the code (design/code-standard.md §11).

Every app has a README.md that lists each of its Python files, and
docs/CODE-TOUR.md mentions every app. Adding a file without documenting it
makes this test fail.
"""

from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
APPS = ["core", "accounts", "quotas", "notifications"]


def files_that_need_describing(app_folder):
    """Return the app's Python file paths (relative), except tests and migrations."""
    names = []
    for path in sorted(app_folder.rglob("*.py")):
        relative_path = path.relative_to(app_folder)
        first_folder = relative_path.parts[0]
        if first_folder in ["tests", "migrations"] or path.name == "__init__.py":
            continue
        names.append(relative_path.as_posix())
    return names


def test_every_app_has_a_readme():
    for app in APPS:
        assert (PROJECT_FOLDER / app / "README.md").exists(), f"{app} needs README.md"


def test_every_app_readme_lists_each_of_its_files():
    missing = []
    for app in APPS:
        app_folder = PROJECT_FOLDER / app
        readme = (app_folder / "README.md").read_text(encoding="utf-8")
        for file_name in files_that_need_describing(app_folder):
            if file_name not in readme:
                missing.append(f"{app}/{file_name}")

    assert missing == [], f"Describe these files in their app README: {missing}"


def test_the_code_tour_mentions_every_app():
    tour = (PROJECT_FOLDER / "docs" / "CODE-TOUR.md").read_text(encoding="utf-8")

    for app in APPS:
        assert f"{app}/" in tour, f"docs/CODE-TOUR.md should introduce {app}/"
