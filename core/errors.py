"""One error format for the whole API.

Every error the API sends back has the same fields:
    status  - the HTTP status number, for example 403
    code    - a short word a frontend can check, for example "quota_exceeded"
    title   - a short human title
    detail  - a plain-English sentence explaining what happened

Our own expected errors are subclasses of AppError. Django REST framework's
errors (bad input, not logged in, too many requests) are converted into the
same shape by problem_details_handler.
"""

from http import HTTPStatus

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


class AppError(Exception):
    """An error we expect and can explain to the user in plain words."""

    status = 400
    code = "bad_request"
    title = "Bad request"

    def __init__(self, detail, extra=None):
        super().__init__(detail)
        self.detail = detail
        self.extra = extra or {}


def make_problem(status, code, title, detail):
    """Build the dictionary that every error response uses."""
    return {"status": status, "code": code, "title": title, "detail": detail}


def convert_app_error(error):
    """Turn one of our own AppErrors into a Response."""
    body = make_problem(error.status, error.code, error.title, error.detail)
    for name, value in error.extra.items():
        body[name] = value
    return Response(body, status=error.status)


def convert_framework_error(error, response):
    """Rewrite a Django REST framework error response into our format."""
    status = response.status_code
    title = HTTPStatus(status).phrase
    if isinstance(error, ValidationError):
        body = make_problem(
            status, "validation_error", title, "Some fields need fixing."
        )
        body["errors"] = response.data
    else:
        body = make_problem(status, error.default_code, title, str(error.detail))
    response.data = body
    return response


def problem_details_handler(error, context):
    """Turn any expected API error into our standard error format."""
    if isinstance(error, AppError):
        return convert_app_error(error)
    response = exception_handler(error, context)
    if response is None:
        return None
    return convert_framework_error(error, response)


class ProviderError(Exception):
    """An outside service (AI model, news source or social network) failed.

    Provider classes raise it with a message that is safe to show the user:
    it must never contain an API key or token.
    """
