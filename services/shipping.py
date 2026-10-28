from decimal import Decimal

from flask import current_app

from services.store_settings import get_setting


ZERO = Decimal("0.00")


def _amount(key):
    value = get_setting(key, "")
    return Decimal(value).quantize(Decimal("0.01")) if value else ZERO


def shipping_quote(address, merchandise_subtotal):
    country = " ".join((address.country or "").split()).casefold()
    state = " ".join((address.state or "").split()).casefold()
    store_country = " ".join(
        get_setting(
            "store_country",
            "STORE_COUNTRY",
        ).split()
    ).casefold() or "india"
    store_state = " ".join(
        get_setting(
            "store_state",
            "STORE_STATE",
        ).split()
    ).casefold() or "maharashtra"

    if country == store_country:
        region = "within_state" if state == store_state else "within_country"
    else:
        region = "out_of_country"

    threshold_value = get_setting("free_shipping_threshold", "")
    free_threshold = Decimal(threshold_value) if threshold_value else None
    free_shipping = (
        free_threshold is not None
        and Decimal(merchandise_subtotal) >= free_threshold
    )
    amount = ZERO if free_shipping else _amount(f"shipping_{region}")
    return {
        "region": region,
        "amount": amount,
        "free_shipping": free_shipping,
        "free_threshold": free_threshold,
    }


def shipping_settings():
    threshold = get_setting("free_shipping_threshold", "")
    return {
        "state": get_setting("store_state", "STORE_STATE") or "Maharashtra",
        "country": get_setting("store_country", "STORE_COUNTRY") or "India",
        "within_state": _amount("shipping_within_state"),
        "within_country": _amount("shipping_within_country"),
        "out_of_country": _amount("shipping_out_of_country"),
        "free_shipping_threshold": Decimal(threshold) if threshold else None,
    }
