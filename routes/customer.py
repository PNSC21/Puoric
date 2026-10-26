from decimal import Decimal
from secrets import token_hex

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    session, url_for
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db
from database.models import (
    Customer, CustomerAddress, Order, OrderItem, Payment, Product, ProductVariant
)
from services.auth import require_customer
from services.accounts import (
    change_email_reservation, email_is_in_use, reserve_email
)
from services.forms import form_value
from services.promotions import promotion_quote
from services.payments import upi_qr_data
from services.store_settings import get_setting
from services.site_data import site
from services.whatsapp import order_whatsapp_url

customer = Blueprint("customer", __name__, url_prefix="/client")


def safe_next(value, fallback):
    if (
        value
        and value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
    ):
        return value
    return url_for(fallback)


def cart_lines():
    cart = session.get("cart", {})
    lines = []
    for key, quantity in cart.items():
        product_id, separator, variant_id = key.partition(":")
        product = db.session.get(Product, int(product_id))
        if not product or not product.is_active:
            continue
        if not product.category.is_active:
            continue
        variant = db.session.get(ProductVariant, int(variant_id)) if separator else None
        if separator and (
            not variant or not variant.is_active or variant.product_id != product.id
        ):
            continue
        price = product.sale_price(
            variant.price if variant and variant.price is not None else product.price
        )
        lines.append({
            "key": key,
            "product": product,
            "variant": variant,
            "quantity": int(quantity),
            "stock_remaining": variant.stock if variant else product.stock,
            "low_stock": (
                0 < (variant.stock if variant else product.stock)
                <= product.low_stock_limit
            ),
            "price": Decimal(price),
            "subtotal": Decimal(price) * int(quantity),
        })
    return lines


def clear_unavailable_cart_lines(lines):
    valid_keys = {line["key"] for line in lines}
    cart_data = session.get("cart", {})
    if set(cart_data) != valid_keys:
        session["cart"] = {
            key: quantity for key, quantity in cart_data.items()
            if key in valid_keys
        }


def start_customer_session(account_id):
    cart_data = session.get("cart", {})
    session.clear()
    if cart_data:
        session["cart"] = cart_data
    session["customer_id"] = account_id


def forbid_admin_cart():
    if session.get("admin_id"):
        abort(403)


def profile_gender():
    gender = form_value("gender", maximum=30)
    if gender and gender not in {"Female", "Male", "Non-binary", "Other"}:
        raise ValueError("Choose a valid gender.")
    return gender or None


@customer.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            name = form_value("full_name", required=True, maximum=120)
            email = form_value("email", required=True, maximum=120).lower()
            if email_is_in_use(email):
                raise ValueError("An account already uses that email address.")
            phone = form_value("phone", required=True, maximum=15)
            password = request.form.get("password", "")
            if len(password) < 10:
                raise ValueError("Password must be at least 10 characters.")
            age_value = request.form.get("age", "").strip()
            try:
                age = int(age_value) if age_value else None
            except ValueError as error:
                raise ValueError("Enter a valid age.") from error
            if age is not None and not 13 <= age <= 120:
                raise ValueError("Age must be between 13 and 120.")
            address = form_value("address_line1", required=True)
            city = form_value("city", required=True, maximum=80)
            state = form_value("state", required=True, maximum=80)
            country = form_value("country", maximum=80) or "India"
            pincode = form_value("pincode", required=True, maximum=10)

            account = Customer(
                full_name=name,
                email=email,
                phone=phone,
                password_hash=generate_password_hash(password),
                age=age,
                gender=profile_gender(),
                skin_type=form_value("skin_type", maximum=80) or None,
                allergies=form_value("allergies", maximum=2000) or None,
                address=address,
                city=city,
                state=state,
                country=country,
                pincode=pincode,
                is_active=True,
            )
            db.session.add(account)
            db.session.flush()
            reserve_email(email, "client", account.id)
            db.session.add(CustomerAddress(
                customer_id=account.id,
                full_name=name,
                phone=phone,
                address_line1=address,
                city=city,
                state=state,
                country=country,
                pincode=pincode,
                is_default=True,
            ))
            db.session.commit()
            start_customer_session(account.id)
            flash("Your client account is ready.", "success")
            return redirect(url_for("customer.dashboard"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("An account already uses that email or phone number.", "error")
    return render_template("customer/signup.html")


@customer.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        account = Customer.query.filter(
            func.lower(Customer.email) == email,
            Customer.is_active.is_(True),
        ).first()
        if account and account.password_hash and check_password_hash(
            account.password_hash, password
        ):
            start_customer_session(account.id)
            return redirect(safe_next(request.args.get("next"), "customer.dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("customer/login.html")


@customer.route("/logout", methods=["POST"])
def logout():
    session.pop("customer_id", None)
    flash("You have been signed out.", "success")
    return redirect(url_for("home.index"))


@customer.route("/dashboard")
@require_customer
def dashboard():
    account = db.session.get(Customer, session["customer_id"])
    orders = Order.query.filter_by(customer_id=account.id).order_by(
        Order.created_at.desc()
    ).limit(5).all()
    return render_template("customer/dashboard.html", account=account, orders=orders)


@customer.route("/profile", methods=["GET", "POST"])
@require_customer
def profile():
    account = db.session.get(Customer, session["customer_id"])
    if request.method == "POST":
        try:
            email = form_value("email", required=True, maximum=120).lower()
            if (
                email.casefold() != account.email.casefold()
                and email_is_in_use(email, customer_id=account.id)
            ):
                raise ValueError("Another account already uses that email address.")
            age_value = request.form.get("age", "").strip()
            try:
                age = int(age_value) if age_value else None
            except ValueError as error:
                raise ValueError("Enter a valid age.") from error
            if age is not None and not 13 <= age <= 120:
                raise ValueError("Age must be between 13 and 120.")
            previous_email = account.email
            account.full_name = form_value("full_name", required=True, maximum=120)
            account.email = email
            account.phone = form_value("phone", required=True, maximum=15)
            account.age = age
            account.gender = profile_gender()
            account.skin_type = form_value("skin_type", maximum=80) or None
            account.allergies = form_value("allergies", maximum=2000) or None
            change_email_reservation(
                previous_email, email, "client", account.id
            )
            db.session.commit()
            flash("Your profile has been updated.", "success")
            return redirect(url_for("customer.profile"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("That email address is already in use.", "error")
    return render_template("customer/profile.html", account=account)


@customer.route("/addresses", methods=["GET", "POST"])
@require_customer
def addresses():
    account_id = session["customer_id"]
    if request.method == "POST":
        try:
            address = CustomerAddress(
                customer_id=account_id,
                full_name=form_value("full_name", required=True, maximum=120),
                phone=form_value("phone", required=True, maximum=20),
                address_line1=form_value("address_line1", required=True),
                address_line2=form_value("address_line2", maximum=255),
                city=form_value("city", required=True, maximum=80),
                state=form_value("state", required=True, maximum=80),
                country=form_value("country", maximum=80) or "India",
                pincode=form_value("pincode", required=True, maximum=10),
            )
            address.is_default = not CustomerAddress.query.filter_by(
                customer_id=account_id
            ).first()
            db.session.add(address)
            db.session.commit()
            flash("Address added.", "success")
            return redirect(url_for("customer.addresses"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
    address_list = CustomerAddress.query.filter_by(
        customer_id=account_id
    ).order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc()).all()
    return render_template("customer/addresses.html", addresses=address_list)


@customer.route("/addresses/<int:address_id>/default", methods=["POST"])
@require_customer
def set_default_address(address_id):
    address_list = CustomerAddress.query.filter_by(
        customer_id=session["customer_id"]
    ).all()
    if not any(address.id == address_id for address in address_list):
        abort(404)
    for address in address_list:
        address.is_default = address.id == address_id
    db.session.commit()
    flash("Default address updated.", "success")
    return redirect(url_for("customer.addresses"))


@customer.route("/addresses/<int:address_id>/delete", methods=["POST"])
@require_customer
def delete_address(address_id):
    address = CustomerAddress.query.filter_by(
        id=address_id, customer_id=session["customer_id"]
    ).first_or_404()
    was_default = address.is_default
    db.session.delete(address)
    db.session.flush()
    if was_default:
        replacement = CustomerAddress.query.filter_by(
            customer_id=session["customer_id"]
        ).first()
        if replacement:
            replacement.is_default = True
    db.session.commit()
    flash("Address removed.", "success")
    return redirect(url_for("customer.addresses"))


@customer.route("/cart")
def cart():
    forbid_admin_cart()
    lines = cart_lines()
    clear_unavailable_cart_lines(lines)
    subtotal = sum((line["subtotal"] for line in lines), Decimal("0.00"))
    account = db.session.get(Customer, session["customer_id"]) if session.get("customer_id") else None
    quote = promotion_quote(account, lines)
    return render_template(
        "customer/cart.html",
        lines=lines,
        total=subtotal,
        quote=quote,
    )


@customer.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    forbid_admin_cart()
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    if not product.category.is_active:
        abort(404)
    available_variants = [
        item for item in product.variants if item.is_active
    ]
    if product.variants and not available_variants:
        flash("No product options are currently available.", "error")
        return redirect(url_for("store.product_detail", slug=product.slug))
    variant_id = request.form.get("variant_id", "").strip()
    variant = None
    if product.variants and not variant_id:
        flash("Choose an available product option.", "error")
        return redirect(url_for("store.product_detail", slug=product.slug))
    if variant_id:
        variant = ProductVariant.query.filter_by(
            id=variant_id, product_id=product.id, is_active=True
        ).first()
        if not variant:
            flash("Choose an available product option.", "error")
            return redirect(url_for("store.product_detail", slug=product.slug))
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 0
    if quantity < 1:
        flash("Quantity must be at least one.", "error")
        return redirect(url_for("store.product_detail", slug=product.slug))
    stock = variant.stock if variant else product.stock
    key = f"{product.id}:{variant.id}" if variant else str(product.id)
    cart_data = session.get("cart", {})
    new_quantity = int(cart_data.get(key, 0)) + quantity
    if new_quantity > stock:
        flash(f"Only {stock} available.", "error")
        return redirect(url_for("store.product_detail", slug=product.slug))
    cart_data[key] = new_quantity
    session["cart"] = cart_data
    flash("Added to your cart.", "success")
    return redirect(url_for("customer.cart"))


@customer.route("/cart/update", methods=["POST"])
def update_cart():
    forbid_admin_cart()
    cart_data = session.get("cart", {})
    key = request.form.get("key", "")
    if key not in cart_data:
        abort(404)
    action = request.form.get("action")
    if action == "remove":
        cart_data.pop(key)
    else:
        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            flash("Enter a valid quantity.", "error")
            return redirect(url_for("customer.cart"))
        line = next((entry for entry in cart_lines() if entry["key"] == key), None)
        if not line or quantity < 1:
            flash("Quantity must be at least one.", "error")
            return redirect(url_for("customer.cart"))
        stock = line["variant"].stock if line["variant"] else line["product"].stock
        if quantity > stock:
            flash(f"Only {stock} available.", "error")
            return redirect(url_for("customer.cart"))
        cart_data[key] = quantity
    session["cart"] = cart_data
    return redirect(url_for("customer.cart"))


@customer.route("/checkout", methods=["GET", "POST"])
@require_customer
def checkout():
    lines = cart_lines()
    clear_unavailable_cart_lines(lines)
    if not lines:
        flash("Your cart is empty.", "error")
        return redirect(url_for("customer.cart"))
    account_id = session["customer_id"]
    address_list = CustomerAddress.query.filter_by(
        customer_id=account_id
    ).order_by(CustomerAddress.is_default.desc()).all()
    subtotal = sum((line["subtotal"] for line in lines), Decimal("0.00"))
    account = db.session.get(Customer, account_id)
    quote = promotion_quote(account, lines)
    upi_enabled = (
        bool(get_setting("upi_payee_id", "UPI_PAYEE_ID"))
        and quote["total"] > 0
    )
    upi_unavailable_reason = (
        "UPI QR is not available for a zero-value order."
        if quote["total"] <= 0
        else "UPI QR payment is not available until the store configures its UPI ID."
    )
    if request.method == "POST":
        payment_method = request.form.get("payment_method", "Cash on delivery")
        if payment_method not in {"Cash on delivery", "UPI QR"}:
            flash("Choose a valid payment method.", "error")
            return redirect(url_for("customer.checkout"))
        if payment_method == "UPI QR" and not upi_enabled:
            flash("UPI QR payments are not set up yet. Choose cash on delivery.", "error")
            return redirect(url_for("customer.checkout"))
        address = CustomerAddress.query.filter_by(
            id=request.form.get("address_id"), customer_id=account_id
        ).first()
        if not address:
            flash("Choose one of your saved addresses.", "error")
            return render_template(
                "customer/checkout.html", lines=lines, addresses=address_list,
                subtotal=subtotal, quote=quote, upi_enabled=upi_enabled,
                upi_unavailable_reason=upi_unavailable_reason,
            )
        order = Order(
            customer_id=account_id,
            order_number=f"PU-{token_hex(5).upper()}",
            subtotal_amount=subtotal,
            discount_amount=quote["discount"],
            total_amount=quote["total"],
            promotion_id=quote["promotion"].id if quote["promotion"] else None,
            promotion_name=quote["promotion"].name if quote["promotion"] else None,
            payment_method=payment_method,
            payment_status="Pending",
            order_status="Pending",
            shipping_status="Pending",
            customer_note=request.form.get("customer_note", "").strip()[:1000] or None,
            shipping_name=address.full_name,
            shipping_phone=address.phone,
            shipping_address=address.formatted,
        )
        try:
            db.session.add(order)
            db.session.flush()
            for line in lines:
                product = line["product"]
                stock_item = line["variant"] or product
                if stock_item.stock < line["quantity"]:
                    raise ValueError(f"Not enough stock for {product.name}.")
                stock_item.stock -= line["quantity"]
                db.session.add(OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    variant_id=line["variant"].id if line["variant"] else None,
                    quantity=line["quantity"],
                    unit_price=line["price"],
                    subtotal=line["subtotal"],
                ))
            db.session.add(Payment(
                order_id=order.id,
                amount=order.total_amount,
                payment_method=order.payment_method,
                payment_status="Pending",
            ))
            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
            return redirect(url_for("customer.cart"))
        session["cart"] = {}
        flash(
            "Order placed. You can send the complete order details to Puoric on "
            "WhatsApp from the order page.",
            "success",
        )
        if payment_method == "UPI QR":
            flash(
                "Complete the UPI payment using the QR code on your order page. "
                "Payment will remain pending until the store verifies it.",
                "info",
            )
        return redirect(url_for("customer.order_detail", order_id=order.id))
    return render_template(
        "customer/checkout.html", lines=lines, addresses=address_list,
        subtotal=subtotal, quote=quote, upi_enabled=upi_enabled,
        upi_unavailable_reason=upi_unavailable_reason,
    )


@customer.route("/orders")
@require_customer
def orders():
    order_list = Order.query.filter_by(customer_id=session["customer_id"]).order_by(
        Order.created_at.desc()
    ).all()
    return render_template("customer/orders.html", orders=order_list)


@customer.route("/orders/<int:order_id>")
@require_customer
def order_detail(order_id):
    order = Order.query.filter_by(
        id=order_id, customer_id=session["customer_id"]
    ).first_or_404()
    payment_qr = None
    if order.payment_method == "UPI QR" and order.payment_status != "Paid":
        payment_qr = upi_qr_data(
            order,
            get_setting("upi_payee_id", "UPI_PAYEE_ID"),
            current_app.config.get("UPI_PAYEE_NAME", "Puoric"),
        )
    return render_template(
        "customer/order_detail.html",
        order=order,
        payment_qr=payment_qr,
        whatsapp_order_url=order_whatsapp_url(
            order, current_app.config.get("STORE_WHATSAPP_NUMBER")
            or site["whatsapp"]
        ),
    )