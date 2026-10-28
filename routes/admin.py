from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hmac
from secrets import token_hex

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from database.constants import (
    ORDER_STATUS,
    ORDER_STATUS_TRANSITIONS,
    PAYMENT_STATUS,
)
from database.db import db
from database.models import (
    AdminUser, Category, CategoryCharacteristic, CategoryCharacteristicValue,
    CategoryVariantType, CategoryVariantUnit, Customer, Order, OrderItem, Product,
    ProductCharacteristic, ProductVariant, Promotion
)
from services.auth import require_admin
from services.accounts import (
    change_email_reservation, email_is_in_use, reserve_email
)
from services.forms import form_value, positive_int, slugify
from services.uploads import save_uploaded_image
from services.store_settings import get_setting, save_setting
from services.shipping import shipping_settings
from services.whatsapp import shipping_update_whatsapp_url

admin = Blueprint("admin", __name__, url_prefix="/admin")
OPEN_ENDED_PROMOTION_DATE = datetime(9999, 12, 31, 23, 59)

def category_characteristic_data(categories):
    return {
        str(category.id): [
            {
                "id": tag.id,
                "name": tag.name,
                "values": [
                    {"id": value.id, "value": value.value}
                    for value in tag.values
                ],
            }
            for tag in category.characteristic_tags
        ]
        for category in categories
    }


def category_variant_data(categories, product=None):
    data = {}
    for category in categories:
        types = {
            variant_type.name: {
                "name": variant_type.name,
                "units": [unit.name for unit in variant_type.units],
            }
            for variant_type in category.variant_types
        }
        if product and product.category_id == category.id:
            for variant in product.variants:
                option = types.setdefault(
                    variant.name, {"name": variant.name, "units": []}
                )
                if (
                    variant.name.casefold() == "weight"
                    and variant.unit
                    and variant.unit not in option["units"]
                ):
                    option["units"].append(variant.unit)
        data[str(category.id)] = list(types.values())
    return data


def password_error(password, confirmation):
    if len(password) < 12:
        return "Password must be at least 12 characters."
    if password != confirmation:
        return "Passwords do not match."
    return None


def category_slug(name, exclude_id=None):
    base = slugify(name)
    if not base:
        raise ValueError("Category name must contain letters or numbers.")
    candidate = base
    suffix = 2
    while True:
        query = Category.query.filter_by(slug=candidate)
        if exclude_id is not None:
            query = query.filter(Category.id != exclude_id)
        if query.first() is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def normalized_name(value):
    return " ".join(value.split()).casefold()


def category_name_exists(name, exclude_id=None):
    key = normalized_name(name)
    return any(
        category.id != exclude_id and normalized_name(category.name) == key
        for category in Category.query.all()
    )


def product_name_exists(name, exclude_id=None):
    key = normalized_name(name)
    return any(
        product.id != exclude_id and normalized_name(product.name) == key
        for product in Product.query.all()
    )


def optional_int(name, label, minimum=0, maximum=None):
    value = request.form.get(name, "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"Enter a valid {label}.") from error
    if parsed < minimum or (maximum is not None and parsed > maximum):
        raise ValueError(f"{label} is outside the allowed range.")
    return parsed


def whole_money(name, label, required=True):
    raw_value = form_value(name, required=required)
    if not raw_value:
        return None
    try:
        amount = Decimal(raw_value)
    except InvalidOperation as error:
        raise ValueError(f"Enter a valid whole-number {label}.") from error
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise ValueError(f"{label.capitalize()} must be a whole number.")
    if amount < 0:
        raise ValueError(f"{label.capitalize()} cannot be negative.")
    return amount.quantize(Decimal("0.01"))


def promotion_form_data():
    name = form_value("name", required=True, maximum=120)
    discount_type = request.form.get("discount_type", "")
    if discount_type not in {"percent", "amount"}:
        raise ValueError("Choose a percentage or fixed-amount discount.")
    try:
        discount_value = Decimal(request.form.get("discount_value", "").strip())
    except InvalidOperation as error:
        raise ValueError("Enter a valid discount value.") from error
    if not discount_value.is_finite() or discount_value <= 0:
        raise ValueError("Discount value must be greater than zero.")
    if discount_value != discount_value.to_integral_value():
        raise ValueError("Discount value must be a whole number.")
    if discount_type == "percent" and discount_value > 100:
        raise ValueError("Percentage discount cannot exceed 100.")
    target_scope = request.form.get(
        "target_scope",
        "categories" if request.form.get("category_scope") == "specific" else "all",
    )
    if target_scope not in {"all", "categories", "products"}:
        raise ValueError("Choose all products, specific categories, or specific products.")
    applies_to_all = target_scope == "all"
    category_ids = []
    product_ids = []
    if target_scope == "categories":
        try:
            category_ids = list({
                int(category_id)
                for category_id in request.form.getlist("category_ids")
            })
        except ValueError as error:
            raise ValueError("Choose valid categories for this offer.") from error
        if not category_ids:
            raise ValueError("Select at least one category for this offer.")
        categories = Category.query.filter(Category.id.in_(category_ids)).all()
        if len(categories) != len(category_ids):
            raise ValueError("Choose categories that still exist.")
    else:
        categories = []
    if target_scope == "products":
        try:
            product_ids = list({
                int(product_id)
                for product_id in request.form.getlist("product_ids")
            })
        except ValueError as error:
            raise ValueError("Choose valid products for this offer.") from error
        if not product_ids:
            raise ValueError("Select at least one product for this offer.")
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        if len(products) != len(product_ids):
            raise ValueError("Choose products that still exist.")
    else:
        products = []
    features = set(request.form.getlist("features"))
    allowed_features = {
        "age", "gender", "festival", "new_clients", "orders", "spend",
        "order_amount",
    }
    if not features <= allowed_features:
        raise ValueError("Choose valid offer audience features.")
    try:
        starts_at = datetime.fromisoformat(request.form.get("starts_at", ""))
    except ValueError as error:
        raise ValueError("Enter a valid offer start time.") from error
    raw_ends_at = request.form.get("ends_at", "").strip()
    if raw_ends_at:
        try:
            ends_at = datetime.fromisoformat(raw_ends_at)
        except ValueError as error:
            raise ValueError("Enter a valid offer end time.") from error
    else:
        ends_at = OPEN_ENDED_PROMOTION_DATE
    if starts_at >= ends_at:
        raise ValueError("Offer end time must be after its start time.")
    minimum_age = optional_int("minimum_age", "minimum age", 13, 120) if "age" in features else None
    if "age" in features and minimum_age is None:
        raise ValueError("Enter the minimum age for this audience.")
    gender = request.form.get("gender", "").strip() if "gender" in features else ""
    if gender not in {"", "Female", "Male", "Non-binary", "Other"}:
        raise ValueError("Choose a valid gender audience.")
    if "gender" in features and not gender:
        raise ValueError("Choose a gender for this audience.")
    festival_name = (
        form_value("festival_name", maximum=80)
        if "festival" in features else None
    )
    if "festival" in features and not festival_name:
        raise ValueError("Enter the festival name for this offer.")
    minimum_orders = optional_int("minimum_orders", "minimum order count") if "orders" in features else None
    if "orders" in features and minimum_orders is None:
        raise ValueError("Enter the minimum completed order count.")
    minimum_spend = whole_money("minimum_spend", "minimum spend", required=False) if "spend" in features else None
    if "spend" in features and minimum_spend is None:
        raise ValueError("Enter the minimum lifetime spend.")
    minimum_order_amount = (
        whole_money("minimum_order_amount", "minimum order amount")
        if "order_amount" in features else None
    )
    if "order_amount" in features and minimum_order_amount <= 0:
        raise ValueError("Minimum order amount must be greater than zero.")
    return {
        "name": name,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "minimum_order_amount": minimum_order_amount,
        "target_scope": target_scope,
        "applies_to_all_categories": applies_to_all,
        "categories": categories,
        "products": products,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "minimum_age": minimum_age,
        "maximum_age": None,
        "gender": gender or None,
        "festival_name": festival_name,
        "new_clients_only": "new_clients" in features,
        "minimum_orders": minimum_orders,
        "maximum_orders": None,
        "minimum_spend": minimum_spend,
        "maximum_spend": None,
    }


@admin.route("/")
def index():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.login"))


@admin.route("/signup", methods=["GET", "POST"])
def signup():
    signup_key = current_app.config.get("ADMIN_SIGNUP_KEY")
    first_admin = AdminUser.query.count() == 0
    signed_in_admin_id = session.get("admin_id")
    signed_in_admin = (
        db.session.get(AdminUser, signed_in_admin_id)
        if signed_in_admin_id else None
    )
    signed_in_admin = bool(signed_in_admin and signed_in_admin.is_active)
    if not first_admin and not signup_key and not signed_in_admin:
        return render_template("admin/signup.html", closed=True)
    if request.method == "POST":
        try:
            if first_admin:
                if AdminUser.query.count() > 0:
                    abort(404)
            elif not signed_in_admin and (not signup_key or not hmac.compare_digest(
                request.form.get("signup_key", ""), signup_key
            )):
                raise ValueError("Admin invitation key is invalid.")
            full_name = form_value("full_name", required=True, maximum=120)
            email = form_value("email", required=True, maximum=120).lower()
            if email_is_in_use(email):
                raise ValueError("An account already uses that email address.")
            password = request.form.get("password", "")
            error = password_error(password, request.form.get("confirm_password", ""))
            if error:
                raise ValueError(error)
            account = AdminUser(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                is_active=True,
            )
            db.session.add(account)
            db.session.flush()
            reserve_email(email, "admin", account.id)
            db.session.commit()
            session.clear()
            session["admin_id"] = account.id
            flash("Admin account created.", "success")
            return redirect(url_for("admin.dashboard"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("An admin account already uses that email.", "error")
    return render_template(
        "admin/signup.html",
        first_admin=first_admin,
        signed_in_admin=signed_in_admin,
        require_invitation=(
            not first_admin and bool(signup_key) and not signed_in_admin
        ),
    )


@admin.route("/login", methods=["GET", "POST"])
def login():
    first_admin = AdminUser.query.count() == 0
    signup_enabled = first_admin or bool(
        current_app.config.get("ADMIN_SIGNUP_KEY")
    )
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        account = AdminUser.query.filter_by(email=email, is_active=True).first()
        if account and check_password_hash(account.password_hash, password):
            session.clear()
            session["admin_id"] = account.id
            target = request.args.get("next", "")
            if (
                target.startswith("/")
                and not target.startswith("//")
                and "\\" not in target
            ):
                return redirect(target)
            return redirect(url_for("admin.dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template(
        "admin/login.html",
        signup_enabled=signup_enabled,
    )


@admin.route("/logout", methods=["POST"])
def logout():
    session.pop("admin_id", None)
    flash("You have been signed out.", "success")
    return redirect(url_for("home.index"))


@admin.route("/dashboard")
@require_admin
def dashboard():
    return render_template(
        "admin/dashboard.html",
        product_count=Product.query.filter_by(is_active=True).count(),
        category_count=Category.query.filter_by(is_active=True).count(),
        order_count=Order.query.count(),
        customer_count=Customer.query.filter_by(is_active=True).count(),
        pending_count=Order.query.filter_by(order_status="Pending").count(),
        recent_orders=Order.query.order_by(Order.created_at.desc()).limit(8).all(),
    )


@admin.route("/profile", methods=["GET", "POST"])
@require_admin
def profile():
    account = db.session.get(AdminUser, session["admin_id"])
    if request.method == "POST":
        try:
            email = form_value("email", required=True, maximum=120).lower()
            if (
                email.casefold() != account.email.casefold()
                and email_is_in_use(email, admin_id=account.id)
            ):
                raise ValueError("Another account already uses that email address.")
            previous_email = account.email
            account.full_name = form_value("full_name", required=True, maximum=120)
            account.email = email
            change_email_reservation(
                previous_email, email, "admin", account.id
            )
            db.session.commit()
            flash("Your admin profile has been updated.", "success")
            return redirect(url_for("admin.profile"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("That email address is already in use.", "error")
    return render_template("admin/profile.html", account=account)


@admin.route("/settings", methods=["GET", "POST"])
@require_admin
def settings():
    if request.method == "POST":
        try:
            upi_id = form_value("upi_id", maximum=255) or ""
            if upi_id and (
                "@" not in upi_id
                or upi_id.count("@") != 1
                or any(character.isspace() for character in upi_id)
            ):
                raise ValueError("Enter a valid UPI ID, such as yourname@bank.")
            store_state = form_value("store_state", required=True, maximum=80)
            store_country = form_value("store_country", required=True, maximum=80)
            charges = {
                key: whole_money(key, label)
                for key, label in (
                    ("shipping_within_state", "within-state shipping charge"),
                    ("shipping_within_country", "within-country shipping charge"),
                    ("shipping_out_of_country", "international shipping charge"),
                )
            }
            free_shipping_threshold = whole_money(
                "free_shipping_threshold",
                "free-shipping threshold",
                required=False,
            )
            save_setting("upi_payee_id", upi_id)
            save_setting("store_state", store_state)
            save_setting("store_country", store_country)
            for key, amount in charges.items():
                save_setting(key, str(amount))
            save_setting(
                "free_shipping_threshold",
                str(free_shipping_threshold)
                if free_shipping_threshold is not None else "",
            )
            db.session.commit()
            flash("Payment and shipping settings saved.", "success")
            return redirect(url_for("admin.settings"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
    return render_template(
        "admin/settings.html",
        upi_id=get_setting("upi_payee_id", "UPI_PAYEE_ID"),
        shipping=shipping_settings(),
    )


@admin.route("/customers")
@require_admin
def customers():
    customers = Customer.query.all()
    stats = db.session.query(
        Order.customer_id,
        func.count(Order.id),
        func.coalesce(func.sum(Order.total_amount), 0),
    ).filter(
        Order.order_status != "Cancelled"
    ).group_by(Order.customer_id).all()
    metrics = {
        customer_id: (int(count), Decimal(spend))
        for customer_id, count, spend in stats
    }
    try:
        filter_by = request.args.get("filter_by", "")
        if not filter_by:
            if request.args.get("gender"):
                filter_by = "gender"
            elif request.args.get("client_type"):
                filter_by = "client_type"
            elif request.args.get("age_min") or request.args.get("age_max"):
                filter_by = "age"
            elif request.args.get("orders_min") or request.args.get("orders_max"):
                filter_by = "orders"
            elif request.args.get("spend_min") or request.args.get("spend_max"):
                filter_by = "spend"
        allowed_filters = {"", "age", "gender", "client_type", "orders", "spend"}
        if filter_by not in allowed_filters:
            abort(400, description="Choose a valid client filter.")
        legacy_filter = not filter_by
        age_min_value = request.args.get("age_min") if legacy_filter or filter_by == "age" else None
        age_max_value = request.args.get("age_max") if legacy_filter or filter_by == "age" else None
        orders_min_value = request.args.get("orders_min") if legacy_filter or filter_by == "orders" else None
        orders_max_value = request.args.get("orders_max") if legacy_filter or filter_by == "orders" else None
        spend_min_value = request.args.get("spend_min") if legacy_filter or filter_by == "spend" else None
        spend_max_value = request.args.get("spend_max") if legacy_filter or filter_by == "spend" else None
        age_min = int(age_min_value) if age_min_value else None
        age_max = int(age_max_value) if age_max_value else None
        orders_min = int(orders_min_value) if orders_min_value else None
        orders_max = int(orders_max_value) if orders_max_value else None
        spend_min = Decimal(spend_min_value) if spend_min_value else None
        spend_max = Decimal(spend_max_value) if spend_max_value else None
    except (ValueError, InvalidOperation) as error:
        abort(400, description="Customer filters must be valid numbers.")
    if (
        (age_min is not None and not 13 <= age_min <= 120)
        or (age_max is not None and not 13 <= age_max <= 120)
        or (orders_min is not None and orders_min < 0)
        or (orders_max is not None and orders_max < 0)
        or (
            spend_min is not None
            and (not spend_min.is_finite() or spend_min < 0)
        )
        or (
            spend_max is not None
            and (not spend_max.is_finite() or spend_max < 0)
        )
        or (age_min is not None and age_max is not None and age_min > age_max)
        or (
            orders_min is not None and orders_max is not None
            and orders_min > orders_max
        )
        or (
            spend_min is not None and spend_max is not None
            and spend_min > spend_max
        )
    ):
        abort(400, description="Client filter ranges must be valid.")
    if (
        (filter_by == "age" and age_min is None and age_max is None)
        or (filter_by == "gender" and not request.args.get("gender"))
        or (
            filter_by == "client_type"
            and not request.args.get("client_type")
        )
        or (filter_by == "orders" and orders_min is None and orders_max is None)
        or (filter_by == "spend" and spend_min is None and spend_max is None)
    ):
        abort(400, description="Enter a value for the selected client filter.")
    filtered = []
    gender_filter = request.args.get("gender", "") if filter_by in {"", "gender"} else ""
    client_type = request.args.get("client_type", "") if filter_by in {"", "client_type"} else ""
    if gender_filter and gender_filter not in {"Female", "Male", "Non-binary", "Other"}:
        abort(400, description="Choose a valid client gender.")
    if client_type not in {"", "new", "returning"}:
        abort(400, description="Choose a valid client type.")
    account_status = request.args.get("account_status", "")
    if account_status not in {"", "active", "banned"}:
        abort(400, description="Choose a valid client account status.")
    for customer in customers:
        count, spend = metrics.get(customer.id, (0, Decimal("0.00")))
        if account_status == "active" and not customer.is_active:
            continue
        if account_status == "banned" and customer.is_active:
            continue
        if age_min is not None and (customer.age is None or customer.age < age_min):
            continue
        if age_max is not None and (customer.age is None or customer.age > age_max):
            continue
        if gender_filter and (customer.gender or "").casefold() != gender_filter.casefold():
            continue
        if client_type == "new" and count:
            continue
        if client_type == "returning" and not count:
            continue
        if orders_min is not None and count < orders_min:
            continue
        if orders_max is not None and count > orders_max:
            continue
        if spend_min is not None and spend < spend_min:
            continue
        if spend_max is not None and spend > spend_max:
            continue
        filtered.append({
            "customer": customer,
            "order_count": count,
            "spend": spend,
        })
    sort_by = request.args.get("sort", "name")
    sort_fields = {
        "name": lambda row: row["customer"].full_name.casefold(),
        "age": lambda row: row["customer"].age if row["customer"].age is not None else -1,
        "orders": lambda row: row["order_count"],
        "spend": lambda row: row["spend"],
    }
    if sort_by not in sort_fields:
        abort(400, description="Choose a valid customer sort order.")
    filtered.sort(key=sort_fields[sort_by], reverse=sort_by in {"orders", "spend", "age"})
    group_by = request.args.get("group", "none")
    if group_by not in {"none", "gender", "age", "client_type", "order_count"}:
        abort(400, description="Choose a valid customer grouping.")
    groups = {}
    for row in filtered:
        customer = row["customer"]
        if group_by == "gender":
            label = customer.gender or "Not specified"
        elif group_by == "age":
            label = (
                "Not specified" if customer.age is None
                else "13-17" if customer.age < 18
                else "18-24" if customer.age < 25
                else "25-34" if customer.age < 35
                else "35-49" if customer.age < 50
                else "50+"
            )
        elif group_by == "client_type":
            label = "New" if row["order_count"] == 0 else "Returning"
        elif group_by == "order_count":
            count = row["order_count"]
            label = "0" if count == 0 else "1-2" if count < 3 else "3-5" if count < 6 else "6+"
        else:
            label = "All clients"
        groups.setdefault(label, []).append(row)
    return render_template(
        "admin/customers.html", groups=groups, group_by=group_by,
        result_count=len(filtered), filters=request.args, filter_by=filter_by,
    )


@admin.route("/customers/<int:customer_id>/toggle-ban", methods=["POST"])
@require_admin
def customer_toggle_ban(customer_id):
    customer = db.session.get(Customer, customer_id) or abort(404)
    customer.is_active = not customer.is_active
    db.session.commit()
    flash(
        "Client access restored." if customer.is_active else "Client access suspended.",
        "success",
    )
    return redirect(url_for("admin.customers", **request.args))


@admin.route("/promotions")
@require_admin
def promotions():
    promotion_list = Promotion.query.order_by(Promotion.starts_at.desc()).all()
    return render_template("admin/promotions.html", promotions=promotion_list)


@admin.route("/promotions/new", methods=["GET", "POST"])
@admin.route("/promotions/<int:promotion_id>/edit", methods=["GET", "POST"])
@require_admin
def promotion_edit(promotion_id=None):
    promotion = db.session.get(Promotion, promotion_id) if promotion_id else None
    if promotion_id and promotion is None:
        abort(404)
    if request.method == "POST":
        try:
            form_data = promotion_form_data()
            if promotion is None:
                promotion = Promotion(**form_data)
                db.session.add(promotion)
            else:
                for key, value in form_data.items():
                    if key in {"categories", "products"}:
                        setattr(promotion, key, value)
                    else:
                        setattr(promotion, key, value)
            db.session.commit()
            flash("Offer saved.", "success")
            return redirect(url_for("admin.promotions"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
    categories_list = Category.query.order_by(Category.name).all()
    selected_category_ids = (
        {category.id for category in promotion.categories}
        if promotion else set()
    )
    selected_product_ids = (
        {product.id for product in promotion.products}
        if promotion else set()
    )
    selected_features = set()
    if promotion:
        if promotion.minimum_age is not None:
            selected_features.add("age")
        if promotion.gender:
            selected_features.add("gender")
        if promotion.festival_name:
            selected_features.add("festival")
        if promotion.new_clients_only:
            selected_features.add("new_clients")
        if promotion.minimum_orders is not None:
            selected_features.add("orders")
        if promotion.minimum_spend is not None:
            selected_features.add("spend")
        if promotion.minimum_order_amount is not None:
            selected_features.add("order_amount")
    if request.method == "POST":
        try:
            selected_category_ids = {
                int(category_id)
                for category_id in request.form.getlist("category_ids")
            }
        except ValueError:
            selected_category_ids = set()
        try:
            selected_product_ids = {
                int(product_id)
                for product_id in request.form.getlist("product_ids")
            }
        except ValueError:
            selected_product_ids = set()
        selected_features = set(request.form.getlist("features"))
    selected_scope = request.form.get(
        "target_scope",
        (
            "categories"
            if request.form.get("category_scope") == "specific"
            else (
                "all" if not promotion or promotion.target_scope == "all"
                else promotion.target_scope
            )
        ),
    )
    return render_template(
        "admin/promotion_form.html",
        promotion=promotion,
        categories=categories_list,
        products=Product.query.order_by(Product.name).all(),
        selected_category_ids=selected_category_ids,
        selected_product_ids=selected_product_ids,
        selected_features=selected_features,
        selected_scope=selected_scope,
    )


@admin.route("/promotions/<int:promotion_id>/toggle", methods=["POST"])
@require_admin
def promotion_toggle(promotion_id):
    promotion = db.session.get(Promotion, promotion_id) or abort(404)
    promotion.is_active = not promotion.is_active
    db.session.commit()
    flash("Offer status updated.", "success")
    return redirect(url_for("admin.promotions"))


@admin.route("/promotions/<int:promotion_id>/delete", methods=["POST"])
@require_admin
def promotion_delete(promotion_id):
    promotion = db.session.get(Promotion, promotion_id) or abort(404)
    Order.query.filter_by(promotion_id=promotion.id).update(
        {Order.promotion_id: None},
        synchronize_session=False,
    )
    db.session.delete(promotion)
    db.session.commit()
    flash("Offer deleted. Existing order discounts remain in order history.", "success")
    return redirect(url_for("admin.promotions"))


@admin.route("/categories")
@require_admin
def categories():
    category_list = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=category_list)


@admin.route("/categories/new", methods=["GET", "POST"])
@require_admin
def category_new():
    if request.method == "POST":
        try:
            name = " ".join(form_value(
                "name", required=True, maximum=100
            ).split())
            if category_name_exists(name):
                raise ValueError("A category with that name already exists.")
            slug = category_slug(name)
            category = Category(
                name=name,
                slug=slug,
                description=form_value("description"),
                is_active=True,
            )
            category.image = save_uploaded_image("image", "categories")
            db.session.add(category)
            db.session.commit()
            flash("Category created.", "success")
            return redirect(url_for("admin.categories"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("Could not create the category. Check the name and image.", "error")
    return render_template("admin/category_form.html", category=None)


@admin.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@require_admin
def category_edit(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    if request.method == "POST":
        try:
            name = " ".join(form_value(
                "name", required=True, maximum=100
            ).split())
            if (
                normalized_name(name) != normalized_name(category.name)
                and category_name_exists(name, exclude_id=category.id)
            ):
                raise ValueError("A category with that name already exists.")
            slug = category.slug if name == category.name else category_slug(name, category.id)
            category.name = name
            category.slug = slug
            category.description = form_value("description")
            category.image = save_uploaded_image(
                "image", "categories", category.image
            )
            db.session.commit()
            flash("Category updated.", "success")
            return redirect(url_for("admin.categories"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("Could not update the category. Check the name and image.", "error")
    return render_template("admin/category_form.html", category=category)


@admin.route("/categories/<int:category_id>/toggle", methods=["POST"])
@require_admin
def category_toggle(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    category.is_active = not category.is_active
    db.session.commit()
    flash("Category visibility updated.", "success")
    return redirect(url_for("admin.categories"))


@admin.route("/categories/<int:category_id>/delete", methods=["POST"])
@require_admin
def category_delete(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    if category.products:
        category.is_active = False
        db.session.commit()
        flash(
            "Category has products, so it was deactivated to preserve catalogue and order history.",
            "success",
        )
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted.", "success")
    return redirect(url_for("admin.categories"))


def product_values(product):
    previous_category_id = product.category_id
    previous_name = product.name if product.id else None
    product.name = " ".join(form_value(
        "name", required=True, maximum=150
    ).split())
    if (
        (previous_name is None or normalized_name(product.name) != normalized_name(previous_name))
        and product_name_exists(product.name, exclude_id=product.id)
    ):
        raise ValueError("A product with that name already exists.")
    if not product.sku:
        product.sku = f"P-{token_hex(8)}"
    product.category_id = positive_int("category_id")
    product.brand = "Puoric"
    product.description = form_value("description")
    product.ingredients = form_value("ingredients")
    product.how_to_use = form_value("how_to_use")
    try:
        product.price = whole_money("price", "price")
        product.discount_type = form_value("discount_type") or "none"
        product.discount_value = whole_money(
            "discount_value", "discount value", required=False
        )
    except InvalidOperation as error:
        raise ValueError("Enter a valid price and discount value.") from error
    if not product.price.is_finite() or product.price <= 0:
        raise ValueError("Product price must be positive.")
    if product.discount_type not in {"none", "percent", "amount"}:
        raise ValueError("Choose a valid discount type.")
    if product.discount_type == "none":
        product.discount_value = None
        product.discount_price = None
    else:
        if (
            product.discount_value is None
            or not product.discount_value.is_finite()
            or product.discount_value <= 0
        ):
            raise ValueError("Enter a discount greater than zero.")
        if product.discount_type == "percent" and product.discount_value >= 100:
            raise ValueError("Percentage discount must be below 100%.")
        if product.discount_type == "amount" and product.discount_value >= product.price:
            raise ValueError("Fixed discount must be lower than product price.")
        product.discount_price = product.sale_price()
    product.stock = positive_int("stock")
    product.low_stock_limit = positive_int("low_stock_limit", default=5)
    product.is_featured = request.form.get("is_featured") == "on"
    product.is_active = request.form.get("is_active") == "on"
    product.slug = slugify(product.name)
    if not product.slug:
        raise ValueError("Product name must contain letters or numbers.")
    category = db.session.get(Category, product.category_id)
    if not category or (
        not category.is_active and category.id != previous_category_id
    ):
        raise ValueError("Choose an active category.")
    tag_ids = request.form.getlist("characteristic_tag_id")
    new_names = request.form.getlist("characteristic_new_tag")
    value_ids = request.form.getlist("characteristic_value_id")
    new_values = request.form.getlist("characteristic_new_value")
    row_count = max(map(len, (tag_ids, new_names, value_ids, new_values)), default=0)
    if any(len(fields) != row_count for fields in (tag_ids, new_names, value_ids, new_values)):
        raise ValueError("Each characteristic needs both a tag and a value.")
    characteristics = []
    tags_by_id = {tag.id: tag for tag in category.characteristic_tags}
    seen_names = set()
    for index in range(row_count):
        tag_id = tag_ids[index].strip()
        new_name = new_names[index].strip()
        value_id = value_ids[index].strip()
        new_value = new_values[index].strip()
        if not any((tag_id, new_name, value_id, new_value)):
            continue
        if tag_id == "__new__":
            if not new_name or len(new_name) > 80:
                raise ValueError("Enter a characteristic tag up to 80 characters.")
            tag = next(
                (item for item in category.characteristic_tags
                 if item.name.casefold() == new_name.casefold()),
                None,
            )
            if tag is None:
                tag = CategoryCharacteristic(name=new_name)
                category.characteristic_tags.append(tag)
        else:
            try:
                tag = tags_by_id.get(int(tag_id))
            except ValueError:
                tag = None
            if tag is None:
                raise ValueError("Choose a characteristic tag for this category.")
        if not value_id or value_id == "__new__":
            value = new_value
            if not value or len(value) > 255:
                raise ValueError("Enter a characteristic value up to 255 characters.")
            existing_value = next(
                (item for item in tag.values
                 if item.value.casefold() == value.casefold()),
                None,
            )
            if existing_value:
                value = existing_value.value
            else:
                tag.values.append(CategoryCharacteristicValue(value=value))
        else:
            try:
                selected_value = next(
                    (item for item in tag.values if item.id == int(value_id)),
                    None,
                )
            except ValueError:
                selected_value = None
            if selected_value is None:
                raise ValueError("Choose a saved value for the selected tag.")
            value = selected_value.value
        if tag.name.casefold() in seen_names:
            raise ValueError("Use each characteristic tag only once per product.")
        seen_names.add(tag.name.casefold())
        if not tag.name or len(tag.name) > 80:
            raise ValueError("Characteristic tags must be between 1 and 80 characters.")
        characteristics.append((tag, value))
    return characteristics


def variant_rows(product=None):
    rows = []
    ids = request.form.getlist("variant_id")
    names = request.form.getlist("variant_name")
    new_names = request.form.getlist("variant_new_type")
    values = request.form.getlist("variant_value")
    units = request.form.getlist("variant_unit")
    new_units = request.form.getlist("variant_new_unit")
    prices = request.form.getlist("variant_price")
    stocks = request.form.getlist("variant_stock")
    existing_ids = {variant.id for variant in product.variants} if product else set()
    seen_combinations = set()
    row_count = max(
        map(len, (ids, names, new_names, values, units, new_units, prices, stocks)),
        default=0,
    )
    for index in range(row_count):
        row = [fields[index] if index < len(fields) else "" for fields in
               (ids, names, new_names, values, units, new_units, prices, stocks)]
        variant_id, selected_name, new_name, value, selected_unit, new_unit, raw_price, raw_stock = (
            part.strip() for part in row
        )
        if not any((variant_id, selected_name, new_name, value, selected_unit, new_unit, raw_price, raw_stock)):
            continue
        try:
            variant_id = int(variant_id) if variant_id else None
        except ValueError as error:
            raise ValueError("Invalid product option.") from error
        if variant_id is not None and variant_id not in existing_ids:
            raise ValueError("Product option does not belong to this product.")
        category_id = product.category_id if product else positive_int("category_id")
        category = db.session.get(Category, category_id)
        if not category:
            raise ValueError("Choose an active category before adding options.")
        if selected_name == "__new__":
            name = " ".join(new_name.split())
            if not name or len(name) > 80:
                raise ValueError("Enter a variant type up to 80 characters.")
            variant_type = next(
                (item for item in category.variant_types
                 if normalized_name(item.name) == normalized_name(name)),
                None,
            )
            if variant_type is None:
                variant_type = CategoryVariantType(name=name)
                category.variant_types.append(variant_type)
            else:
                name = variant_type.name
        else:
            name = " ".join(selected_name.split())
            variant_type = next(
                (item for item in category.variant_types
                 if normalized_name(item.name) == normalized_name(name)),
                None,
            )
            if variant_type is None and variant_id is not None:
                variant_type = CategoryVariantType(name=name)
                category.variant_types.append(variant_type)
            if variant_type is None or not name:
                raise ValueError("Choose a variant type or add a new one.")
            name = variant_type.name
        value = " ".join(value.split())
        if not value or len(value) > 120:
            raise ValueError("Enter a value for the product option.")
        is_weight = name.casefold() == "weight"
        if not is_weight and (selected_unit or new_unit):
            raise ValueError("A measuring unit can only be selected for Weight options.")
        if is_weight and not (selected_unit or new_unit):
            raise ValueError("Choose or add a measuring unit for Weight options.")
        if selected_unit == "__new__":
            unit = new_unit
            if not unit or len(unit) > 20:
                raise ValueError("Enter a measuring unit up to 20 characters.")
            existing_unit = next(
                (item for item in variant_type.units
                 if item.name.casefold() == unit.casefold()),
                None,
            )
            if existing_unit is None:
                variant_type.units.append(CategoryVariantUnit(name=unit))
            else:
                unit = existing_unit.name
        elif selected_unit:
            unit = next(
                (item.name for item in variant_type.units
                 if item.name.casefold() == selected_unit.casefold()),
                None,
            )
            if unit is None and variant_id is not None and product:
                existing_variant = next(
                    (item for item in product.variants if item.id == variant_id),
                    None,
                )
                if existing_variant and existing_variant.unit == selected_unit:
                    variant_type.units.append(CategoryVariantUnit(name=selected_unit))
                    unit = selected_unit
            if unit is None:
                raise ValueError("Choose a unit for this type or add a new one.")
        else:
            unit = None
        if is_weight:
            try:
                number = Decimal(value)
            except InvalidOperation as error:
                raise ValueError("Weight values must be positive numbers.") from error
            if not number.is_finite() or number <= 0:
                raise ValueError("Weight values must be positive numbers.")
        else:
            unit = None
        combination = (normalized_name(name), normalized_name(value))
        if combination in seen_combinations:
            raise ValueError("Each product option type and value must be unique.")
        seen_combinations.add(combination)
        if product and any(
            variant.id != variant_id
            and (
                normalized_name(variant.name),
                normalized_name(variant.value),
            ) == combination
            for variant in product.variants
        ):
            raise ValueError("That product option type and value already exists.")
        try:
            stock = int(raw_stock)
            price = Decimal(raw_price) if raw_price else None
        except (ValueError, InvalidOperation) as error:
            raise ValueError("Option stock and price must be valid numbers.") from error
        if price is not None:
            if price != price.to_integral_value():
                raise ValueError("Option price must be a whole number.")
            price = price.quantize(Decimal("0.01"))
        if stock < 0 or (
            price is not None and (not price.is_finite() or price <= 0)
        ):
            raise ValueError("Option stock cannot be negative and price must be positive.")
        rows.append((variant_id, name, value, unit, stock, price))
    return rows


@admin.route("/products")
@require_admin
def products():
    product_list = Product.query.order_by(Product.name).all()
    return render_template("admin/products.html", products=product_list)


@admin.route("/products/<int:product_id>/toggle", methods=["POST"])
@require_admin
def product_toggle(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    product.is_active = not product.is_active
    db.session.commit()
    flash("Product visibility updated.", "success")
    return redirect(url_for("admin.products"))


@admin.route("/products/<int:product_id>/delete", methods=["POST"])
@require_admin
def product_delete(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.order_items:
        product.is_active = False
        for variant in product.variants:
            variant.is_active = False
        db.session.commit()
        flash(
            "Product has order history, so it and its options were deactivated instead of deleted.",
            "success",
        )
    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted.", "success")
    return redirect(url_for("admin.products"))


@admin.route(
    "/products/<int:product_id>/variants/<int:variant_id>/toggle",
    methods=["POST"],
)
@require_admin
def product_variant_toggle(product_id, variant_id):
    variant = ProductVariant.query.filter_by(
        id=variant_id, product_id=product_id
    ).first_or_404()
    variant.is_active = not variant.is_active
    db.session.commit()
    flash("Product option visibility updated.", "success")
    return redirect(url_for("admin.products"))


@admin.route(
    "/products/<int:product_id>/variants/<int:variant_id>/delete",
    methods=["POST"],
)
@require_admin
def product_variant_delete(product_id, variant_id):
    variant = ProductVariant.query.filter_by(
        id=variant_id, product_id=product_id
    ).first_or_404()
    if OrderItem.query.filter_by(variant_id=variant.id).first():
        variant.is_active = False
        db.session.commit()
        flash(
            "Option appears in order history, so it was deactivated instead of deleted.",
            "success",
        )
    else:
        db.session.delete(variant)
        db.session.commit()
        flash("Product option deleted.", "success")
    return redirect(url_for("admin.products"))


@admin.route("/products/new", methods=["GET", "POST"])
@require_admin
def product_new():
    categories_list = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    if request.method == "POST":
        product = Product()
        try:
            characteristics = product_values(product)
            variants = variant_rows(product)
            product.image = save_uploaded_image("image", "products")
            db.session.add(product)
            db.session.flush()
            product.slug = f"{product.slug}-{product.id}"
            for tag, value in characteristics:
                product.characteristics.append(
                    ProductCharacteristic(name=tag.name, value=value)
                )
            for _, name, value, unit, stock, price in variants:
                product.variants.append(ProductVariant(
                    name=name, value=value, unit=unit,
                    sku=f"V-{token_hex(8)}", stock=stock,
                    price=price, is_active=True,
                ))
            db.session.commit()
            flash("Product created.", "success")
            return redirect(url_for("admin.products"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("A product with those details already exists.", "error")
    return render_template(
        "admin/product_form.html", product=None, categories=categories_list,
        category_characteristics=category_characteristic_data(categories_list),
        category_variant_types=category_variant_data(categories_list),
    )


@admin.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@require_admin
def product_edit(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    categories_list = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    if not product.category.is_active:
        categories_list.append(product.category)
    if request.method == "POST":
        try:
            characteristics = product_values(product)
            variants = variant_rows(product)
            product.image = save_uploaded_image("image", "products", product.image)
            product.slug = f"{slugify(product.name)}-{product.id}"
            product.characteristics.clear()
            for tag, value in characteristics:
                product.characteristics.append(
                    ProductCharacteristic(name=tag.name, value=value)
                )
            variants_by_id = {variant.id: variant for variant in product.variants}
            submitted_ids = {row[0] for row in variants if row[0] is not None}
            for existing in product.variants:
                existing.is_active = existing.id in submitted_ids
            for variant_id, name, value, unit, stock, price in variants:
                existing = variants_by_id.get(variant_id)
                if existing:
                    existing.name = name
                    existing.value = value
                    existing.unit = unit
                    existing.stock = stock
                    existing.price = price
                    existing.is_active = (
                        request.form.get(f"variant_active_{existing.id}") == "on"
                        if f"variant_active_{existing.id}" in request.form
                        else True
                    )
                else:
                    product.variants.append(ProductVariant(
                        name=name, value=value, unit=unit,
                        sku=f"V-{token_hex(8)}", stock=stock,
                        price=price,
                        is_active=request.form.get("variant_active_new") == "on"
                        if "variant_active_new" in request.form else True,
                    ))
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("admin.products"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("A product with those details already exists.", "error")
    return render_template(
        "admin/product_form.html", product=product, categories=categories_list,
        category_characteristics=category_characteristic_data(categories_list),
        category_variant_types=category_variant_data(categories_list, product),
    )


@admin.route("/orders")
@require_admin
def orders():
    status = request.args.get("status")
    query = Order.query
    if status in ORDER_STATUS:
        query = query.filter_by(order_status=status)
    order_list = query.order_by(Order.created_at.desc()).all()
    return render_template(
        "admin/orders.html",
        orders=order_list,
        order_statuses=ORDER_STATUS,
    )


@admin.route("/orders/<int:order_id>", methods=["GET", "POST"])
@require_admin
def order_detail(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    if request.method == "POST":
        order_status = request.form.get("order_status")
        payment_status = request.form.get("payment_status", order.payment_status)
        allowed_order_statuses = (
            order.order_status,
        ) + tuple(
            status for status in ORDER_STATUS_TRANSITIONS.get(order.order_status, ())
            if status != "Delivered"
        )
        if order_status == "Delivered" and order.order_status != "Delivered":
            flash(
                "The client marks the parcel received from their order page.",
                "error",
            )
        elif (
            order_status not in allowed_order_statuses
            or payment_status not in PAYMENT_STATUS
        ):
            flash("Choose the current status or the next available status.", "error")
        elif order_status in {"Confirmed", "Packed", "Shipped"} and payment_status != "Paid":
            flash(
                "Verify the prepaid UPI transaction before confirming or shipping "
                "the order.",
                "error",
            )
        elif payment_status == "Refunded" and order.payment_status not in {"Paid", "Refunded"}:
            flash("Record a refund only after the prepaid payment was verified.", "error")
        else:
            payment_was_pending = order.payment_status != "Paid"
            was_shipped = order.shipping_status == "Shipped"
            was_cancelled = order.order_status == "Cancelled"
            order.order_status = order_status
            if order_status in {"Packed", "Shipped", "Delivered"}:
                order.shipping_status = order_status
            elif order_status in {"Pending", "Confirmed"}:
                order.shipping_status = "Pending"
            if order_status == "Cancelled":
                if not was_shipped:
                    order.shipping_amount = Decimal("0.00")
                    order.total_amount = max(
                        Decimal(order.subtotal_amount) - Decimal(order.discount_amount),
                        Decimal("0.00"),
                    )
                    if not was_cancelled:
                        for item in order.order_items:
                            stock_item = item.variant or item.product
                            stock_item.stock += item.quantity
            order.payment_status = payment_status
            order.admin_note = request.form.get("admin_note", "").strip()[:1000] or None
            if order.payment:
                order.payment.payment_status = payment_status
                if payment_status == "Paid" and payment_was_pending:
                    order.payment.paid_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
            db.session.commit()
            if payment_status == "Paid" and payment_was_pending:
                flash("Payment marked Paid.", "success")
            elif order_status == "Cancelled" and payment_status == "Paid":
                flash(
                    "Order cancelled. If a refund is due, process it through the "
                    "payment account and then record the refund status here.",
                    "success",
                )
            else:
                flash("Order updated.", "success")
            return redirect(url_for("admin.order_detail", order_id=order.id))
    order_statuses = (order.order_status,) + tuple(
        status for status in ORDER_STATUS_TRANSITIONS.get(order.order_status, ())
        if status != "Delivered"
    )
    refund_due = Decimal("0.00")
    if (
        order.payment
        and order.payment_status == "Paid"
        and order.order_status == "Cancelled"
        and order.shipping_status != "Shipped"
        and order.payment.amount > order.total_amount
    ):
        refund_due = Decimal(order.payment.amount) - Decimal(order.total_amount)
    return render_template(
        "admin/order_detail.html",
        order=order,
        order_statuses=order_statuses,
        payment_statuses=PAYMENT_STATUS,
        refund_due=refund_due,
        shipping_update_whatsapp_url=(
            shipping_update_whatsapp_url(order)
            if order.order_status == "Shipped" else None
        ),
    )