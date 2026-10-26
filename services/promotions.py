from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from database.models import Order, Promotion


CENT = Decimal("0.01")


def client_metrics(customer_id):
    orders = Order.query.filter(
        Order.customer_id == customer_id,
        Order.order_status != "Cancelled",
    ).all()
    return len(orders), sum(
        (Decimal(order.total_amount) for order in orders), Decimal("0.00")
    )


def promotion_quote(customer, lines, now=None):
    category_subtotals = {}
    for line in lines:
        category_id = line["product"].category_id
        category_subtotals[category_id] = (
            category_subtotals.get(category_id, Decimal("0.00"))
            + Decimal(line["subtotal"])
        )
    subtotal = sum(category_subtotals.values(), Decimal("0.00")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    if not customer or subtotal <= 0:
        return {"promotion": None, "discount": Decimal("0.00"), "total": subtotal}

    order_count, lifetime_spend = client_metrics(customer.id)
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    eligible = Promotion.query.filter(
        Promotion.is_active.is_(True),
        Promotion.starts_at <= now,
        Promotion.ends_at >= now,
    ).all()
    candidates = []
    for promotion in eligible:
        if promotion.minimum_age is not None and (
            customer.age is None or customer.age < promotion.minimum_age
        ):
            continue
        if promotion.maximum_age is not None and (
            customer.age is None or customer.age > promotion.maximum_age
        ):
            continue
        if promotion.gender and (
            not customer.gender
            or customer.gender.casefold() != promotion.gender.casefold()
        ):
            continue
        if promotion.new_clients_only and order_count:
            continue
        if promotion.minimum_orders is not None and order_count < promotion.minimum_orders:
            continue
        if promotion.maximum_orders is not None and order_count > promotion.maximum_orders:
            continue
        if promotion.minimum_spend is not None and lifetime_spend < Decimal(promotion.minimum_spend):
            continue
        if promotion.maximum_spend is not None and lifetime_spend > Decimal(promotion.maximum_spend):
            continue
        applicable_subtotal = (
            subtotal
            if promotion.applies_to_all_categories
            else sum(
                (
                    amount for category_id, amount in category_subtotals.items()
                    if any(category.id == category_id for category in promotion.categories)
                ),
                Decimal("0.00"),
            )
        )
        if applicable_subtotal <= 0:
            continue
        if promotion.discount_type == "percent":
            discount = applicable_subtotal * Decimal(promotion.discount_value) / Decimal("100")
        else:
            discount = Decimal(promotion.discount_value)
        discount = min(
            applicable_subtotal,
            discount.quantize(CENT, rounding=ROUND_HALF_UP),
        )
        candidates.append((discount, promotion))

    if not candidates:
        return {"promotion": None, "discount": Decimal("0.00"), "total": subtotal}
    discount, promotion = max(
        candidates,
        key=lambda candidate: (candidate[0], candidate[1].id),
    )
    return {
        "promotion": promotion,
        "discount": discount,
        "total": subtotal - discount,
    }
