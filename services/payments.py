import base64
from io import BytesIO
from urllib.parse import urlencode

import qrcode
from qrcode.image.svg import SvgPathImage


def upi_payment_uri(order, payee_id, payee_name):
    if not payee_id:
        return None
    return "upi://pay?" + urlencode({
        "pa": payee_id,
        "pn": payee_name,
        "am": f"{order.total_amount:.2f}",
        "cu": "INR",
        "tr": order.order_number,
        "tn": f"Puoric order {order.order_number}",
    })


def upi_qr_data(order, payee_id, payee_name):
    payment_uri = upi_payment_uri(order, payee_id, payee_name)
    if not payment_uri:
        return None
    qr_code = qrcode.QRCode(box_size=6, border=4)
    qr_code.add_data(payment_uri)
    qr_code.make(fit=True)
    image = qr_code.make_image(image_factory=SvgPathImage)
    output = BytesIO()
    image.save(output)
    encoded_image = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded_image}"
