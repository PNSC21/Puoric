import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from services.whatsapp import delivery_code_whatsapp_url

DELIVERY_CODE_TTL = timedelta(hours=24)
MAX_DELIVERY_CODE_ATTEMPTS = 5


def issue_delivery_code(order):
    code = f"{secrets.randbelow(1_000_000):06d}"
    whatsapp_url = delivery_code_whatsapp_url(order, code)
    if not whatsapp_url:
        order.delivery_code_hash = None
        order.delivery_code_sent_at = None
        order.delivery_code_attempts = 0
        return None

    order.delivery_code_hash = generate_password_hash(code)
    order.delivery_code_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    order.delivery_code_attempts = 0
    return whatsapp_url


def check_delivery_code(order, code):
    if order.delivery_code_attempts >= MAX_DELIVERY_CODE_ATTEMPTS:
        return "locked"
    if not order.delivery_code_hash or not order.delivery_code_sent_at:
        return "missing"
    sent_at = order.delivery_code_sent_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - sent_at > DELIVERY_CODE_TTL:
        return "expired"
    if not check_password_hash(order.delivery_code_hash, code):
        order.delivery_code_attempts += 1
        return "invalid"
    return "valid"
