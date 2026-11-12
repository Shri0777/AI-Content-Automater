"""The API contract with the frontend must never change by accident.

schema/openapi.yaml is a saved copy of the API description. If the code
changes the API, this test fails until the saved copy is updated on purpose:

    uv run python manage.py spectacular --file schema/openapi.yaml
"""

from pathlib import Path

from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.renderers import OpenApiYamlRenderer

SAVED_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "openapi.yaml"


def test_the_saved_api_description_matches_the_code():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    current = OpenApiYamlRenderer().render(schema, renderer_context={}).decode()

    saved = SAVED_SCHEMA.read_text(encoding="utf-8")

    assert current == saved, (
        "The API changed. If this was on purpose, run: "
        "uv run python manage.py spectacular --file schema/openapi.yaml"
    )
