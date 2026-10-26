from functools import wraps

from flask import redirect, session, url_for


def requested_path():
    from flask import request

    return request.full_path.rstrip("?")


def require_account(kind):
    session_key = f"{kind}_id"
    endpoint = "admin.login" if kind == "admin" else "customer.login"

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            account_id = session.get(session_key)
            if not account_id:
                return redirect(url_for(endpoint, next=requested_path()))
            from database.db import db
            from database.models import AdminUser, Customer

            model = AdminUser if kind == "admin" else Customer
            account = db.session.get(model, account_id)
            if not account or not account.is_active:
                session.pop(session_key, None)
                return redirect(url_for(endpoint, next=requested_path()))
            return view(*args, **kwargs)

        return wrapped

    return decorator


require_admin = require_account("admin")
require_customer = require_account("customer")