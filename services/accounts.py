from sqlalchemy import func

from database.db import db
from database.models import AccountEmail, AdminUser, Customer


def email_is_in_use(email, customer_id=None, admin_id=None):
    normalized = email.strip().lower()
    customer_query = Customer.query.filter(func.lower(Customer.email) == normalized)
    admin_query = AdminUser.query.filter(func.lower(AdminUser.email) == normalized)
    if customer_id is not None:
        customer_query = customer_query.filter(Customer.id != customer_id)
    if admin_id is not None:
        admin_query = admin_query.filter(AdminUser.id != admin_id)
    return (
        customer_query.first() is not None
        or admin_query.first() is not None
        or AccountEmail.query.filter_by(email=normalized).first() is not None
    )


def reserve_email(email, account_type, account_id):
    db.session.add(AccountEmail(
        email=email.strip().lower(),
        account_type=account_type,
        account_id=account_id,
    ))


def change_email_reservation(previous_email, email, account_type, account_id):
    previous = previous_email.strip().lower()
    normalized = email.strip().lower()
    if previous == normalized:
        return
    reservation = AccountEmail.query.filter_by(email=previous).first()
    if (
        reservation
        and reservation.account_type == account_type
        and reservation.account_id == account_id
    ):
        other_type = "admin" if account_type == "client" else "client"
        if account_type == "client":
            other = AdminUser.query.filter(
                func.lower(AdminUser.email) == previous
            ).first()
        else:
            other = Customer.query.filter(
                func.lower(Customer.email) == previous
            ).first()
        if other:
            reservation.account_type = other_type
            reservation.account_id = other.id
        else:
            db.session.delete(reservation)
    reserve_email(normalized, account_type, account_id)
