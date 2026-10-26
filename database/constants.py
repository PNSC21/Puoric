ORDER_STATUS = (
    "Pending",
    "Confirmed",
    "Packed",
    "Shipped",
    "Delivered",
    "Cancelled"
)

ORDER_STATUS_TRANSITIONS = {
    "Pending": ("Confirmed", "Cancelled"),
    "Confirmed": ("Packed", "Cancelled"),
    "Packed": ("Shipped", "Cancelled"),
    "Shipped": ("Delivered", "Cancelled"),
    "Delivered": (),
    "Cancelled": (),
}

PAYMENT_STATUS = (
    "Pending",
    "Paid",
    "Failed",
    "Refunded"
)