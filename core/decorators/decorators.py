from functools import wraps

from flask import abort
from flask_login import current_user


def pass_or_abort(condition):

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not condition(**kwargs):
                abort(404)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(f):
    """
    Decorator to restrict access to routes only for users with 'admin' role.
    Returns 403 Forbidden if the user is not authenticated or does not have admin role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        
        # Check if user has admin role
        if not any(role.name == 'admin' for role in current_user.roles):
            abort(403)
        
        return f(*args, **kwargs)
    
    return decorated_function
