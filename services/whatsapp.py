from urllib.parse import quote


def whatsapp_chat_url(phone, message, country="India"):
    original_number = phone.strip()
    number = "".join(character for character in phone if character.isdigit())
    if not number:
        return None
    if number.startswith("00"):
        number = number[2:]
    elif (country or "").strip().casefold() == "india":
        if len(number) == 10:
            number = f"91{number}"
        elif len(number) == 11 and number.startswith("0"):
            number = f"91{number[1:]}"
    elif not original_number.startswith("+") and len(number) == 10:
        return None
    if not 8 <= len(number) <= 15:
        return None
    return f"https://wa.me/{number}?text={quote(message)}"


def order_whatsapp_url(order, store_number):
    if not store_number:
        return None

    lines = [
        "Hello Puoric, I am confirming my order:",
        f"Order: {order.order_number}",
        f"Placed: {order.created_at}",
        f"Client: {order.customer.full_name}",
        f"Client email: {order.customer.email}",
        f"Phone: {order.customer.phone}",
        f"Delivery to: {order.shipping_name}",
        f"Delivery phone: {order.shipping_phone}",
        f"Address: {order.shipping_address}",
        "",
        "Items:",
    ]
    for item in order.order_items:
        option = ""
        if item.variant:
            option = f" ({item.variant.name}: {item.variant.value}"
            if item.variant.name.casefold() == "weight" and item.variant.unit:
                option += f" {item.variant.unit}"
            option += ")"
        lines.append(
            f"- {item.product.name}{option} x {item.quantity}: "
            f"INR {item.subtotal:.2f}"
        )

    lines.extend([
        "",
        f"Subtotal: INR {order.subtotal_amount:.2f}",
        f"Offer: {order.promotion_name or 'None'}",
        f"Discount: INR {order.discount_amount:.2f}",
        f"Shipping: INR {order.shipping_amount:.2f}",
        f"Total: INR {order.total_amount:.2f}",
        f"Payment method: {order.payment_method}",
        f"Payment status: {order.payment_status}",
        f"Order note: {order.customer_note or 'None'}",
    ])
    return whatsapp_chat_url(store_number, "\n".join(lines))


def shipping_update_whatsapp_url(order):
    items = ", ".join(
        f"{item.product.name} x {item.quantity}"
        for item in order.order_items
    )
    message = "\n".join([
        f"Hello {order.shipping_name},",
        f"Your Puoric order {order.order_number} has been shipped.",
        f"Items: {items}",
        "Please check that these items arrived correctly, then confirm receipt "
        "from your order page.",
        f"Order total: INR {order.total_amount:.2f}",
    ])
    return whatsapp_chat_url(
        order.shipping_phone,
        message,
        order.shipping_country or "India",
    )
