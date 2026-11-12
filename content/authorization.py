from functools import wraps
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden


def user_owns_content(view_func):
    """
    Decorator to enforce content ownership authorization.
    Ensures that the logged-in user owns the content they're trying to access.

    Usage:
        @login_required
        @user_owns_content
        def my_view(request, pk):
            content = get_object_or_404(Content, pk=pk)
            ...
    """
    @wraps(view_func)
    def wrapper(request, pk, *args, **kwargs):
        from content.models import Content

        content = get_object_or_404(Content, pk=pk)

        if content.owner != request.user:
            # A full HTML document (with a doctype) keeps the browser out of
            # Quirks Mode; a bare string body would trigger standards warnings.
            return HttpResponseForbidden(
                "<!DOCTYPE html>"
                '<html lang="en"><head><title>403 Forbidden</title></head>'
                "<body><p>You do not have permission to access this content."
                "</p></body></html>"
            )

        return view_func(request, pk, *args, **kwargs)

    return wrapper
