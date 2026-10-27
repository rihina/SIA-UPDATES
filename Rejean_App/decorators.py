from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff_role:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


def member_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_staff_role:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped
