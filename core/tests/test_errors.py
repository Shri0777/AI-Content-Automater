"""Tests for the error format every API error uses.

Every error looks the same: a status number, a short title, a plain-English
detail and a machine-readable code that a frontend can check.
"""

import pytest
from rest_framework.exceptions import NotAuthenticated, ValidationError

from core.errors import AppError, problem_details_handler


class PlanLimitReached(AppError):
    """An example of one of our own errors, used only in these tests."""

    status = 403
    code = "plan_limit_reached"
    title = "Plan limit reached"


@pytest.mark.django_db
def test_validation_errors_list_each_field_problem():
    error = ValidationError({"email": ["Enter a valid email address."]})

    response = problem_details_handler(error, {})

    assert response.status_code == 400
    assert response.data["code"] == "validation_error"
    assert response.data["errors"] == {"email": ["Enter a valid email address."]}


@pytest.mark.django_db
def test_framework_errors_use_the_same_shape():
    response = problem_details_handler(NotAuthenticated(), {})

    assert response.status_code == 401
    assert response.data["status"] == 401
    assert response.data["code"] == "not_authenticated"
    assert response.data["title"] == "Unauthorized"
    assert "detail" in response.data


def test_our_own_errors_carry_their_code_title_and_extra_fields():
    error = PlanLimitReached("You can have 3 active plans.", extra={"limit": 3})

    response = problem_details_handler(error, {})

    assert response.status_code == 403
    assert response.data == {
        "status": 403,
        "code": "plan_limit_reached",
        "title": "Plan limit reached",
        "detail": "You can have 3 active plans.",
        "limit": 3,
    }


def test_unexpected_python_errors_are_left_for_django_to_handle():
    response = problem_details_handler(ValueError("bug"), {})

    assert response is None
