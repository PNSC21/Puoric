import unittest
import re
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from app import create_app
from database.db import db
from database.models import (
    AccountEmail, AdminUser, Category, Customer, CustomerAddress, Order,
    OrderItem, Product, ProductVariant, Promotion
)
from services.payments import upi_payment_uri


class TestConfig:
    SECRET_KEY = "dashboard-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_SIGNUP_KEY = None
    UPI_PAYEE_ID = "puoric@upi"
    UPI_PAYEE_NAME = "Puoric"
    TESTING = True


class DashboardFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.upload_directory = TemporaryDirectory()
        self.app.static_folder = self.upload_directory.name
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        category = Category(name="Skin care", slug="skin-care", is_active=True)
        db.session.add(category)
        db.session.flush()
        db.session.add(Product(
            category_id=category.id,
            name="Daily cream",
            slug="daily-cream-test",
            sku="CREAM-TEST",
            price=Decimal("250.00"),
            stock=5,
            low_stock_limit=1,
            is_active=True,
        ))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()
        self.upload_directory.cleanup()

    def test_client_order_and_admin_tracking_flow(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn(b"Feel good in the skin", self.client.get("/").data)
        home = self.client.get("/")
        for option in (
            b"Client sign in", b"Admin sign in",
            b"Client sign up", b"Admin sign up",
        ):
            self.assertIn(option, home.data)
        self.assertEqual(self.client.get("/client/signup").status_code, 200)
        self.assertEqual(self.client.get("/client/login").status_code, 200)
        response = self.client.get("/products/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Daily cream", response.data)

        response = self.client.post("/client/cart/add/1", data={"quantity": "2"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/client/signup", data={
            "full_name": "Test Client",
            "email": "client@example.test",
            "phone": "9876543210",
            "password": "client-password-123",
            "address_line1": "10 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/client/dashboard", response.headers["Location"])
        signed_in_page = self.client.get("/client/dashboard")
        self.assertNotIn(b"Client sign in", signed_in_page.data)
        self.assertNotIn(b"Admin sign in", signed_in_page.data)
        self.assertNotIn(b"Client sign up", signed_in_page.data)
        self.assertNotIn(b"Admin sign up", signed_in_page.data)
        for path in ("/client/dashboard", "/client/addresses", "/client/orders"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertIn(b"Daily cream", self.client.get("/client/cart").data)
        response = self.client.post("/client/addresses", data={
            "full_name": "Test Client",
            "phone": "9876543210",
            "address_line1": "20 New Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400602",
        })
        self.assertEqual(response.status_code, 302)
        new_address = CustomerAddress.query.filter_by(address_line1="20 New Road").one()
        self.client.post(f"/client/addresses/{new_address.id}/default")
        self.client.post("/client/addresses/1/delete")
        self.assertEqual(CustomerAddress.query.count(), 1)
        self.assertEqual(self.client.get("/client/checkout").status_code, 200)
        response = self.client.post(
            "/client/checkout", data={"address_id": str(new_address.id)}
        )
        self.assertEqual(response.status_code, 302)
        order_id = response.headers["Location"].rsplit("/", 1)[-1]
        response = self.client.get(f"/client/orders/{order_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pending", response.data)
        self.client.post("/client/logout")
        signed_out_home = self.client.get("/")
        self.assertIn(b"Client sign in", signed_out_home.data)
        self.assertIn(b"Admin sign in", signed_out_home.data)
        self.assertIn(b"Client sign up", signed_out_home.data)
        self.assertIn(b"Admin sign up", signed_out_home.data)
        response = self.client.post("/client/login", data={
            "email": "client@example.test",
            "password": "client-password-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/client/dashboard", response.headers["Location"])
        self.assertEqual(self.client.get(f"/client/orders/{order_id}").status_code, 200)

        admin_client = self.app.test_client()
        response = admin_client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(admin_client.get("/admin/login").status_code, 200)
        self.assertEqual(admin_client.get("/admin/signup").status_code, 200)
        response = admin_client.post("/admin/signup", data={
            "full_name": "Test Admin",
            "email": "admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard", response.headers["Location"])
        for path in ("/admin/products", "/admin/categories", "/admin/orders"):
            self.assertEqual(admin_client.get(path).status_code, 200)
        signed_in_admin_page = admin_client.get("/admin/dashboard")
        self.assertNotIn(b"Client sign in", signed_in_admin_page.data)
        self.assertNotIn(b"Admin sign in", signed_in_admin_page.data)
        self.assertNotIn(b"Client sign up", signed_in_admin_page.data)
        self.assertNotIn(b"Admin sign up", signed_in_admin_page.data)
        self.assertEqual(
            admin_client.get(f"/admin/orders/{order_id}").status_code, 200
        )
        response = admin_client.post(f"/admin/orders/{order_id}", data={
            "order_status": "Confirmed",
            "payment_status": "Pending",
            "admin_note": "On the way",
        })
        self.assertEqual(response.status_code, 302)
        admin_client.post("/admin/logout")
        response = admin_client.post("/admin/login", data={
            "email": "admin@example.test",
            "password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        admin_client.post("/admin/logout")
        signed_out = admin_client.get("/")
        self.assertIn(b"Client sign in", signed_out.data)
        self.assertIn(b"Admin sign in", signed_out.data)
        self.assertIn(b"Client sign up", signed_out.data)
        self.assertIn(b"Admin sign up", signed_out.data)
        response = self.client.get(f"/client/orders/{order_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Shipped", response.data)

    def test_first_admin_can_register_and_later_signup_explains_admin_gate(self):
        response = self.app.test_client().post("/admin/signup", data={
            "full_name": "First Admin",
            "email": "first-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AdminUser.query.count(), 1)
        closed_page = self.app.test_client().get("/admin/signup")
        self.assertEqual(closed_page.status_code, 200)
        self.assertIn(b"Public admin registration is closed", closed_page.data)
        admin = self.app.test_client()
        admin.post("/admin/login", data={
            "email": "first-admin@example.test",
            "password": "admin-password-123",
        })
        response = admin.post("/admin/signup", data={
            "full_name": "Second Admin",
            "email": "second-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AdminUser.query.count(), 2)

    def test_additional_admin_requires_configured_invitation_key(self):
        first_admin = AdminUser(
            full_name="First Admin",
            email="first-admin@example.test",
            password_hash="test-hash",
            is_active=True,
        )
        db.session.add(first_admin)
        db.session.commit()
        self.app.config["ADMIN_SIGNUP_KEY"] = "second-admin-key"
        client = self.app.test_client()

        response = client.post("/admin/signup", data={
            "full_name": "Second Admin",
            "email": "second-admin@example.test",
            "signup_key": "wrong",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AdminUser.query.count(), 1)

        response = client.post("/admin/signup", data={
            "full_name": "Second Admin",
            "email": "second-admin@example.test",
            "signup_key": "second-admin-key",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AdminUser.query.count(), 2)

    def test_admin_can_manage_categories_and_variant_products(self):
        response = self.client.post("/admin/signup", data={
            "full_name": "Test Admin",
            "email": "admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 200)

        response = self.client.post("/admin/categories/new", data={
            "name": "Body care",
            "description": "Body care products",
            "display_order": "2",
            "image": (BytesIO(b"\x89PNG\r\n\x1a\ncategory image"), "body-care.png"),
        })
        self.assertEqual(response.status_code, 302)
        category = Category.query.filter_by(slug="body-care").one()
        self.assertTrue(Path(self.app.static_folder, category.image).is_file())
        response = self.client.post(
            f"/admin/categories/{category.id}/toggle"
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(category.is_active)
        self.client.post(f"/admin/categories/{category.id}/toggle")
        self.assertTrue(category.is_active)
        self.assertEqual(self.client.get("/admin/categories/new").status_code, 200)
        self.assertEqual(
            {tag.name for tag in category.characteristic_tags},
            set(),
        )
        self.assertEqual(
            self.client.get(f"/admin/categories/{category.id}/edit").status_code,
            200,
        )
        product_form = self.client.get("/admin/products/new")
        self.assertEqual(product_form.status_code, 200)
        self.assertNotIn(b'name="sku"', product_form.data)
        self.assertNotIn(b'name="short_description"', product_form.data)
        self.assertNotIn(b'name="benefits"', product_form.data)
        self.assertNotIn(b'name="suitable_for"', product_form.data)
        self.assertNotIn(b"Skin type", product_form.data)
        self.assertIn(b"type=\"file\"", product_form.data)

        response = self.client.post("/admin/products/new", data={
            "name": "Body lotion",
            "category_id": str(category.id),
            "price": "300",
            "discount_type": "percent",
            "discount_value": "15",
            "stock": "0",
            "low_stock_limit": "2",
            "description": "A gentle lotion.",
            "ingredients": "Aloe",
            "how_to_use": "Apply daily",
            "characteristic_tag_id": ["__new__", "__new__"],
            "characteristic_new_tag": ["Skin type", "Finish"],
            "characteristic_value_id": ["__new__", "__new__"],
            "characteristic_new_value": ["Dry", "Dewy"],
            "variant_name": ["__new__"],
            "variant_new_type": ["Weight"],
            "variant_value": ["50"],
            "variant_unit": ["__new__"],
            "variant_new_unit": ["g"],
            "variant_price": ["250"],
            "variant_stock": ["8"],
            "image": (BytesIO(b"\x89PNG\r\n\x1a\nproduct image"), "body-lotion.png"),
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        product = Product.query.filter_by(name="Body lotion").one()
        self.assertEqual(product.brand, "Puoric")
        self.assertTrue(Path(self.app.static_folder, product.image).is_file())
        self.assertEqual(
            {tag.name for tag in category.characteristic_tags},
            {"Skin type", "Finish"},
        )
        saved_values = {
            tag.name: {item.value for item in tag.values}
            for tag in category.characteristic_tags
        }
        self.assertEqual(saved_values, {"Skin type": {"Dry"}, "Finish": {"Dewy"}})
        self.assertIn(
            b"Finish",
            self.client.get("/admin/products/new").data,
        )
        self.assertIn(b"Dry", self.client.get("/admin/products/new").data)
        self.assertNotIn(b"Company / brand", product_form.data)
        variant = product.variants[0]
        self.assertEqual(variant.stock, 8)
        self.assertEqual(variant.name, "Weight")
        self.assertEqual(variant.value, "50")
        self.assertEqual(variant.unit, "g")
        saved_variant_type = next(
            item for item in category.variant_types if item.name == "Weight"
        )
        self.assertEqual(
            {unit.name for unit in saved_variant_type.units},
            {"g"},
        )
        next_product_form = self.client.get("/admin/products/new")
        self.assertIn(b'"name": "Weight"', next_product_form.data)
        self.assertIn(b'"g"', next_product_form.data)
        self.assertEqual(len(product.characteristics), 2)
        self.assertEqual(product.sale_price(), Decimal("255.00"))

        skin_type = next(
            tag for tag in category.characteristic_tags if tag.name == "Skin type"
        )
        dry_value = next(item for item in skin_type.values if item.value == "Dry")
        response = self.client.post("/admin/products/new", data={
            "name": "Body lotion refill",
            "category_id": str(category.id),
            "price": "200",
            "discount_type": "none",
            "stock": "3",
            "low_stock_limit": "1",
            "characteristic_tag_id": [str(skin_type.id)],
            "characteristic_new_tag": [""],
            "characteristic_value_id": [str(dry_value.id)],
            "characteristic_new_value": [""],
            "variant_name": ["Weight"],
            "variant_new_type": [""],
            "variant_value": ["30"],
            "variant_unit": ["g"],
            "variant_new_unit": [""],
            "variant_price": [""],
            "variant_stock": ["2"],
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        refill = Product.query.filter_by(name="Body lotion refill").one()
        self.assertEqual(refill.characteristics[0].name, "Skin type")
        self.assertEqual(refill.characteristics[0].value, "Dry")
        self.assertEqual(refill.variants[0].unit, "g")

        response = self.client.get("/products/?category=body-care")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Body lotion", response.data)
        response = self.client.get(f"/products/{product.slug}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Skin type", response.data)
        edit_page = self.client.get(f"/admin/products/{product.id}/edit")
        self.assertIn(b"Dry", edit_page.data)
        self.assertIn(b"Dewy", edit_page.data)
        product_page = self.client.get(f"/products/{product.slug}")
        self.assertNotIn(b"Add to cart", product_page.data)
        response = self.client.post(
            f"/client/cart/add/{product.id}",
            data={"variant_id": str(variant.id), "quantity": "2"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/client/cart").status_code, 403)
        shopper = self.app.test_client()
        shopper.post("/client/signup", data={
            "full_name": "Shopper",
            "email": "shopper@example.test",
            "phone": "9876500001",
            "password": "shopper-password",
            "address_line1": "10 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        response = shopper.post(
            f"/client/cart/add/{product.id}",
            data={"variant_id": str(variant.id), "quantity": "2"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(shopper.get("/client/cart").status_code, 200)

        response = self.client.post(f"/admin/products/{product.id}/edit", data={
            "name": "Body lotion",
            "category_id": str(category.id),
            "price": "300",
            "discount_type": "amount",
            "discount_value": "30",
            "stock": "0",
            "low_stock_limit": "2",
            "description": "A gentle lotion.",
            "ingredients": "Aloe",
            "how_to_use": "Apply daily",
            "characteristic_tag_id": [str(next(
                tag.id for tag in category.characteristic_tags
                if tag.name == "Skin type"
            ))],
            "characteristic_new_tag": [""],
            "characteristic_value_id": ["__new__"],
            "characteristic_new_value": ["All"],
            "variant_id": [str(variant.id)],
            "variant_name": ["Weight"],
            "variant_new_type": [""],
            "variant_value": ["50"],
            "variant_unit": ["g"],
            "variant_new_unit": [""],
            "variant_price": ["250"],
            "variant_stock": ["6"],
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(variant.stock, 6)
        self.assertEqual(product.sale_price(), Decimal("270.00"))
        self.assertEqual(product.sale_price(variant.price), Decimal("220.00"))
        response = self.client.post(f"/admin/products/{product.id}/toggle")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(product.is_active)
        self.client.post(f"/admin/products/{product.id}/toggle")
        self.assertTrue(product.is_active)
        response = self.client.post(
            f"/admin/products/{product.id}/variants/{variant.id}/toggle"
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(variant.is_active)
        self.assertNotIn(b"Add to cart", shopper.get(
            f"/products/{product.slug}"
        ).data)
        response = shopper.post(
            f"/client/cart/add/{product.id}", data={"quantity": "1"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(b"No product options are currently available", shopper.get(
            f"/products/{product.slug}"
        ).data)
        self.client.post(
            f"/admin/products/{product.id}/variants/{variant.id}/toggle"
        )
        self.assertTrue(variant.is_active)

    def test_unique_category_names_profiles_and_targeted_offer_checkout(self):
        admin = self.app.test_client()
        response = admin.post("/admin/signup", data={
            "full_name": "Admin One",
            "email": "admin-one@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        self.assertEqual(response.status_code, 302)
        duplicate_account = self.app.test_client()
        response = duplicate_account.post("/client/signup", data={
            "full_name": "Duplicate Email",
            "email": "admin-one@example.test",
            "phone": "9876500003",
            "password": "client-password-123",
            "address_line1": "10 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(Customer.query.filter_by(email="admin-one@example.test").first())
        self.assertEqual(AccountEmail.query.filter_by(
            email="admin-one@example.test"
        ).count(), 1)
        response = admin.post("/admin/categories/new", data={
            "name": "Repeated category",
            "display_order": "1",
        })
        self.assertEqual(response.status_code, 302)
        response = admin.post("/admin/categories/new", data={
            "name": " repeated   CATEGORY ",
            "display_order": "1",
        })
        self.assertEqual(response.status_code, 200)
        duplicates = Category.query.filter_by(name="Repeated category").all()
        self.assertEqual(len(duplicates), 1)
        category_form = admin.get("/admin/products/new")
        self.assertIn(b"Repeated category", category_form.data)
        self.assertNotIn(b"(repeated-category-2)", category_form.data)

        client = self.app.test_client()
        response = client.post("/client/signup", data={
            "full_name": "Profile Client",
            "email": "profile-client@example.test",
            "phone": "9876500002",
            "password": "client-password-123",
            "age": "28",
            "gender": "Female",
            "skin_type": "Sensitive",
            "allergies": "Fragrance",
            "address_line1": "10 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        self.assertEqual(response.status_code, 302)
        customer = Customer.query.filter_by(email="profile-client@example.test").one()
        self.assertEqual(customer.age, 28)
        filtered_clients = admin.get(
            "/admin/customers?filter_by=gender&gender=Female&age_min=99"
        )
        self.assertEqual(filtered_clients.status_code, 200)
        self.assertIn(b"profile-client@example.test", filtered_clients.data)
        self.assertIn(b"data-customer-filter=\"age\" hidden", filtered_clients.data)
        response = client.post("/client/profile", data={
            "full_name": "Updated Client",
            "email": "profile-client@example.test",
            "phone": "9876500002",
            "age": "29",
            "gender": "Female",
            "skin_type": "Dry",
            "allergies": "None",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(customer.full_name, "Updated Client")
        self.assertEqual(client.get("/client/profile").status_code, 200)
        response = client.post("/client/profile", data={
            "full_name": "Updated Client",
            "email": "profile-updated@example.test",
            "phone": "9876500002",
            "age": "29",
            "gender": "Female",
            "skin_type": "Dry",
            "allergies": "None",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(AccountEmail.query.filter_by(
            email="profile-client@example.test"
        ).first())
        self.assertIsNotNone(AccountEmail.query.filter_by(
            email="profile-updated@example.test"
        ).first())

        admin.post("/admin/profile", data={
            "full_name": "Updated Admin",
            "email": "admin-one@example.test",
        })
        self.assertEqual(admin.get("/admin/profile").status_code, 200)
        self.assertEqual(admin.get("/admin/customers?group=gender").status_code, 200)

        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        response = admin.post("/admin/promotions/new", data={
            "name": "Sensitive skin offer",
            "discount_type": "percent",
            "discount_value": "20",
            "category_scope": "specific",
            "category_ids": ["1"],
            "features": ["age", "gender", "festival", "new_clients"],
            "festival_name": "Diwali",
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "minimum_age": "25",
            "maximum_age": "35",
            "gender": "Female",
            "new_clients_only": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(admin.get("/admin/promotions").status_code, 200)
        self.assertEqual(admin.get("/admin/promotions/1/edit").status_code, 200)
        offer_form = admin.get("/admin/promotions/1/edit")
        self.assertIn(b"Specific categories", offer_form.data)
        self.assertIn(b"Skin care", offer_form.data)
        self.assertIn(b"Diwali", offer_form.data)
        client.post("/client/cart/add/1", data={"quantity": "1"})
        cart = client.get("/client/cart")
        self.assertIn(b"Sensitive skin offer", cart.data)
        response = client.post("/client/checkout", data={"address_id": "1"})
        self.assertEqual(response.status_code, 302)
        order = Order.query.one()
        self.assertEqual(order.subtotal_amount, Decimal("250.00"))
        self.assertEqual(order.discount_amount, Decimal("50.00"))
        self.assertEqual(order.total_amount, Decimal("200.00"))
        self.assertEqual(order.promotion_name, "Sensitive skin offer")
        self.assertEqual(order.payment.amount, Decimal("200.00"))

        response = admin.post("/admin/promotions/1/edit", data={
            "name": "Sensitive skin offer",
            "discount_type": "amount",
            "discount_value": "30",
            "category_scope": "specific",
            "category_ids": ["1"],
            "features": ["age", "gender", "festival", "new_clients"],
            "festival_name": "Diwali",
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "minimum_age": "25",
            "maximum_age": "35",
            "gender": "Female",
            "new_clients_only": "on",
        })
        self.assertEqual(response.status_code, 302)
        second_client = self.app.test_client()
        response = admin.post("/admin/promotions/new", data={
            "name": "All-category new client offer",
            "discount_type": "amount",
            "discount_value": "10",
            "category_scope": "all",
            "features": ["new_clients"],
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "new_clients_only": "on",
        })
        self.assertEqual(response.status_code, 302)
        second_client.post("/client/signup", data={
            "full_name": "Second Client",
            "email": "second-client@example.test",
            "phone": "9876500004",
            "password": "client-password-123",
            "age": "32",
            "gender": "Female",
            "address_line1": "20 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        outside_category = Category.query.filter_by(slug="repeated-category").first()
        other_product = Product(
            category_id=outside_category.id,
            name="Other category product",
            slug="other-category-product",
            sku="OTHER-PRODUCT",
            price=Decimal("100.00"),
            stock=2,
            low_stock_limit=1,
            is_active=True,
        )
        db.session.add(other_product)
        db.session.commit()
        second_client.post(
            f"/client/cart/add/{other_product.id}", data={"quantity": "1"}
        )
        response = second_client.post("/client/checkout", data={"address_id": "2"})
        self.assertEqual(response.status_code, 302)
        second_order = Order.query.order_by(Order.id.desc()).first()
        self.assertEqual(second_order.discount_amount, Decimal("10.00"))
        self.assertEqual(second_order.total_amount, Decimal("90.00"))

        third_client = self.app.test_client()
        third_client.post("/client/signup", data={
            "full_name": "Third Client",
            "email": "third-client@example.test",
            "phone": "9876500005",
            "password": "client-password-123",
            "age": "30",
            "gender": "Female",
            "address_line1": "30 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        third_client.post("/client/cart/add/1", data={"quantity": "1"})
        response = third_client.post("/client/checkout", data={"address_id": "3"})
        self.assertEqual(response.status_code, 302)
        third_order = Order.query.order_by(Order.id.desc()).first()
        self.assertEqual(third_order.discount_amount, Decimal("30.00"))
        self.assertEqual(third_order.total_amount, Decimal("220.00"))

        invalid_offer = admin.post("/admin/promotions/new", data={
            "name": "Incomplete age offer",
            "discount_type": "percent",
            "discount_value": "15",
            "category_scope": "all",
            "features": ["age"],
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(invalid_offer.status_code, 200)
        self.assertIn(b"Enter a minimum or maximum age", invalid_offer.data)

    def test_delete_archive_ban_and_whole_number_money_rules(self):
        admin = self.app.test_client()
        admin.post("/admin/signup", data={
            "full_name": "Admin",
            "email": "delete-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })

        invalid_product = admin.post("/admin/products/new", data={
            "name": "Fractional entry",
            "category_id": "1",
            "price": "100.50",
            "discount_type": "none",
            "stock": "2",
            "low_stock_limit": "1",
        })
        self.assertEqual(invalid_product.status_code, 200)
        self.assertIn(b"Price must be a whole number", invalid_product.data)
        self.assertIsNone(Product.query.filter_by(name="Fractional entry").first())

        client = self.app.test_client()
        client.post("/client/signup", data={
            "full_name": "Order Client",
            "email": "order-client@example.test",
            "phone": "9876500006",
            "password": "client-password-123",
            "address_line1": "10 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        client.post("/client/cart/add/1", data={"quantity": "1"})
        response = client.post("/client/checkout", data={"address_id": "1"})
        self.assertEqual(response.status_code, 302)
        order = Order.query.one()

        variant = ProductVariant(
            product_id=1,
            name="Size",
            value="30",
            unit=None,
            sku="DELETE-TEST-VARIANT",
            stock=2,
            is_active=True,
        )
        db.session.add(variant)
        db.session.flush()
        order.order_items.append(OrderItem(
            product_id=1,
            variant_id=variant.id,
            quantity=1,
            unit_price=Decimal("250.00"),
            subtotal=Decimal("250.00"),
        ))
        offer = Promotion(
            name="History offer",
            discount_type="amount",
            discount_value=Decimal("10.00"),
            starts_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
            ends_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
            is_active=True,
        )
        db.session.add(offer)
        db.session.flush()
        order.promotion_id = offer.id
        order.promotion_name = offer.name
        order.discount_amount = Decimal("10.00")
        db.session.commit()

        response = admin.post(
            f"/admin/products/1/variants/{variant.id}/delete"
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(variant.is_active)
        self.assertIsNotNone(db.session.get(OrderItem, order.order_items[-1].id))

        response = admin.post("/admin/products/1/delete")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(db.session.get(Product, 1).is_active)
        response = admin.post("/admin/categories/1/delete")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(db.session.get(Category, 1).is_active)

        response = admin.post(f"/admin/promotions/{offer.id}/delete")
        self.assertEqual(response.status_code, 302)
        db.session.refresh(order)
        self.assertIsNone(order.promotion_id)
        self.assertEqual(order.promotion_name, "History offer")
        self.assertEqual(order.discount_amount, Decimal("10.00"))

        unused_category = Category(name="Unused", slug="unused", is_active=True)
        db.session.add(unused_category)
        db.session.flush()
        unused_category_id = unused_category.id
        self.assertEqual(
            admin.post(f"/admin/categories/{unused_category_id}/delete").status_code,
            302,
        )
        self.assertIsNone(db.session.get(Category, unused_category_id))

        self.assertEqual(
            admin.post("/admin/customers/1/toggle-ban").status_code, 302
        )
        customer = db.session.get(Customer, 1)
        self.assertFalse(customer.is_active)
        client.post("/client/logout")
        response = client.post("/client/login", data={
            "email": "order-client@example.test",
            "password": "client-password-123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email or password is incorrect", response.data)
        self.assertEqual(admin.get("/admin/customers?account_status=banned").status_code, 200)
        admin.post("/admin/customers/1/toggle-ban")
        self.assertTrue(customer.is_active)

    def test_upi_qr_checkout_and_prefilled_whatsapp_order_message(self):
        client = self.app.test_client()
        client.post("/client/signup", data={
            "full_name": "UPI Client",
            "email": "upi-client@example.test",
            "phone": "9876500010",
            "password": "client-password-123",
            "address_line1": "10 UPI Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        client.post("/client/cart/add/1", data={"quantity": "2"})

        response = client.post("/client/checkout", data={
            "address_id": "1",
            "payment_method": "UPI QR",
            "customer_note": "Please call on arrival.",
        })
        self.assertEqual(response.status_code, 302)
        order = Order.query.one()
        self.assertEqual(order.payment_method, "UPI QR")
        self.assertEqual(order.payment_status, "Pending")
        self.assertEqual(order.total_amount, Decimal("500.00"))
        payment_uri = upi_payment_uri(order, "puoric@upi", "Puoric")
        self.assertTrue(payment_uri.startswith("upi://pay?"))
        self.assertIn("pa=puoric%40upi", payment_uri)
        self.assertIn("pn=Puoric", payment_uri)
        self.assertIn("am=500.00", payment_uri)
        self.assertIn(f"tr={order.order_number}", payment_uri)
        self.assertIn("cu=INR", payment_uri)
        response = client.get(f"/client/orders/{order.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data:image/svg+xml;base64,", response.data)
        self.assertIn(b"Payment will remain pending", response.data)
        self.assertIn(b"Complete your UPI payment", response.data)
        self.assertIn(b"Open WhatsApp and send order", response.data)
        self.assertIn(b"wa.me/918422994021", response.data)
        whatsapp_href = re.search(
            rb'href="(https://wa\.me/[^"]+)"', response.data
        ).group(1).decode()
        message = parse_qs(urlparse(whatsapp_href).query)["text"][0]
        for expected in (
            order.order_number,
            "UPI Client",
            "upi-client@example.test",
            "Daily cream x 2",
            "INR 500.00",
            "Please call on arrival.",
        ):
            self.assertIn(expected, message)

        for field, updated_status in (
            ("order_status", "Confirmed"),
            ("shipping_status", "Shipped"),
            ("payment_status", "Paid"),
        ):
            setattr(order, field, updated_status)
            db.session.commit()
            response = client.get(f"/client/orders/{order.id}")
            self.assertNotIn(b"Send order details", response.data)
            self.assertNotIn(b"Open WhatsApp and send order", response.data)
            setattr(order, field, "Pending")
            db.session.commit()

    def test_upi_checkout_is_unavailable_without_store_upi_id(self):
        self.app.config["UPI_PAYEE_ID"] = ""
        client = self.app.test_client()
        client.post("/client/signup", data={
            "full_name": "No UPI Client",
            "email": "no-upi@example.test",
            "phone": "9876500011",
            "password": "client-password-123",
            "address_line1": "10 Test Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        client.post("/client/cart/add/1", data={"quantity": "1"})
        checkout = client.get("/client/checkout")
        self.assertEqual(checkout.status_code, 200)
        self.assertIn(b"UPI QR payment is not available", checkout.data)
        response = client.post("/client/checkout", data={
            "address_id": "1",
            "payment_method": "UPI QR",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.query.count(), 0)

    def test_admin_can_record_upi_payment_and_keep_statuses_simple(self):
        admin = self.app.test_client()
        admin.post("/admin/signup", data={
            "full_name": "Payment Admin",
            "email": "payment-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        client = self.app.test_client()
        client.post("/client/signup", data={
            "full_name": "Paid Order Client",
            "email": "paid-order-client@example.test",
            "phone": "9876500013",
            "password": "client-password-123",
            "address_line1": "11 Payment Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        client.post("/client/cart/add/1", data={"quantity": "1"})

        response = client.post("/client/checkout", data={
            "address_id": "1",
            "payment_method": "UPI QR",
        })
        self.assertEqual(response.status_code, 302)
        order = Order.query.one()
        response = admin.post(f"/admin/orders/{order.id}", data={
            "order_status": "Shipped",
            "payment_status": "Pending",
            "admin_note": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.order_status, "Pending")

        response = admin.post(f"/admin/orders/{order.id}", data={
            "order_status": "Confirmed",
            "payment_status": "Pending",
            "admin_note": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.payment_status, "Pending")
        self.assertEqual(order.order_status, "Confirmed")
        self.assertEqual(order.shipping_status, "Pending")
        detail = admin.get(f"/admin/orders/{order.id}")
        self.assertIn(b"Order status", detail.data)
        self.assertNotIn(b"Shipping status", detail.data)
        order_list = admin.get("/admin/orders")
        self.assertNotIn(b"<th>Shipping</th>", order_list.data)
        for status in ("Packed", "Shipped"):
            response = admin.post(f"/admin/orders/{order.id}", data={
                "order_status": status,
                "payment_status": "Pending",
                "admin_note": "",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Open WhatsApp and send receipt code", response.data)
        whatsapp_href = re.search(
            rb'href="(https://wa\.me/[^"]+)"', response.data
        ).group(1).decode()
        code_message = parse_qs(urlparse(whatsapp_href).query)["text"][0]
        code = re.search(r"Delivery code: (\d{6})", code_message).group(1)
        self.assertIn("Payment status is handled separately.", code_message)
        response = admin.post(f"/admin/orders/{order.id}", data={
            "action": "verify_delivery",
            "delivery_code": code,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.order_status, "Delivered")
        self.assertEqual(order.payment_status, "Pending")
        self.assertEqual(order.payment.payment_status, "Pending")
        response = admin.post(f"/admin/orders/{order.id}", data={
            "order_status": "Delivered",
            "payment_status": "Paid",
            "admin_note": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.payment_status, "Paid")
        self.assertEqual(order.payment.payment_status, "Paid")

    def test_cod_delivery_code_verifies_payment_for_admin_and_client(self):
        admin = self.app.test_client()
        admin.post("/admin/signup", data={
            "full_name": "COD Admin",
            "email": "cod-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        client = self.app.test_client()
        client.post("/client/signup", data={
            "full_name": "COD Client",
            "email": "cod-client@example.test",
            "phone": "9876500014",
            "password": "client-password-123",
            "address_line1": "12 Delivery Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        client.post("/client/cart/add/1", data={"quantity": "1"})

        response = client.post("/client/checkout", data={
            "address_id": "1",
            "payment_method": "Cash on delivery",
        })
        self.assertEqual(response.status_code, 302)
        order = Order.query.one()
        response = admin.post(f"/admin/orders/{order.id}", data={
            "order_status": "Delivered",
            "payment_status": "Pending",
            "admin_note": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.payment_status, "Pending")
        self.assertNotEqual(order.shipping_status, "Delivered")

        for status in ("Confirmed", "Packed"):
            response = admin.post(f"/admin/orders/{order.id}", data={
                "order_status": status,
                "payment_status": "Pending",
                "admin_note": "",
            })
            self.assertEqual(response.status_code, 302)

        response = admin.post(f"/admin/orders/{order.id}", data={
            "order_status": "Shipped",
            "payment_status": "Pending",
            "admin_note": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.payment_status, "Pending")
        self.assertEqual(order.shipping_status, "Shipped")
        self.assertIn(b"Open WhatsApp and send receipt code", response.data)
        whatsapp_href = re.search(
            rb'href="(https://wa\.me/[^"]+)"', response.data
        ).group(1).decode()
        self.assertIn("wa.me/919876500014", whatsapp_href)
        code_message = parse_qs(urlparse(whatsapp_href).query)["text"][0]
        code = re.search(r"Delivery code: (\d{6})", code_message).group(1)
        self.assertIn(order.order_number, code_message)
        self.assertIn("INR 250.00", code_message)

        response = admin.post(f"/admin/orders/{order.id}", data={
            "action": "verify_delivery",
            "delivery_code": "000000" if code != "000000" else "000001",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.payment_status, "Pending")

        response = admin.post(f"/admin/orders/{order.id}", data={
            "action": "verify_delivery",
            "delivery_code": code,
        })
        self.assertEqual(response.status_code, 302)

        self.assertEqual(order.payment_status, "Paid")
        self.assertEqual(order.order_status, "Delivered")
        self.assertEqual(order.shipping_status, "Delivered")
        self.assertIsNotNone(order.payment.paid_at)

    def test_admin_can_save_store_upi_id_and_checkout_uses_it(self):
        admin = self.app.test_client()
        admin.post("/admin/signup", data={
            "full_name": "Payment Admin",
            "email": "payment-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })
        dashboard = admin.get("/admin/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Store settings", dashboard.data)
        settings = admin.get("/admin/settings")
        self.assertEqual(settings.status_code, 200)
        self.assertIn(b'value="puoric@upi"', settings.data)

        saved = admin.post("/admin/settings", data={
            "upi_id": "puoric.store@bank",
        })
        self.assertEqual(saved.status_code, 302)
        settings = admin.get("/admin/settings")
        self.assertIn(b'value="puoric.store@bank"', settings.data)

        client = self.app.test_client()
        client.post("/client/signup", data={
            "full_name": "UPI Settings Client",
            "email": "upi-settings-client@example.test",
            "phone": "9876500012",
            "password": "client-password-123",
            "address_line1": "10 Payment Road",
            "city": "Thane",
            "state": "Maharashtra",
            "country": "India",
            "pincode": "400601",
        })
        client.post("/client/cart/add/1", data={"quantity": "1"})
        checkout = client.get("/client/checkout")
        self.assertIn(b"Pay by UPI QR", checkout.data)
        response = client.post("/client/checkout", data={
            "address_id": "1",
            "payment_method": "UPI QR",
        })
        self.assertEqual(response.status_code, 302)
        order = Order.query.one()
        self.assertIn(
            "pa=puoric.store%40bank",
            upi_payment_uri(order, "puoric.store@bank", "Puoric"),
        )
        order_page = client.get(f"/client/orders/{order.id}")
        self.assertIn(b"data:image/svg+xml;base64,", order_page.data)

        invalid = admin.post("/admin/settings", data={"upi_id": "not a vpa"})
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Enter a valid UPI ID", invalid.data)
        self.assertIn(b'value="puoric.store@bank"', invalid.data)

    def test_duplicate_product_and_variant_combinations_are_rejected(self):
        admin = self.app.test_client()
        admin.post("/admin/signup", data={
            "full_name": "Catalogue Admin",
            "email": "catalogue-admin@example.test",
            "password": "admin-password-123",
            "confirm_password": "admin-password-123",
        })

        duplicate_product = admin.post("/admin/products/new", data={
            "name": " daily   CREAM ",
            "category_id": "1",
            "price": "300",
            "discount_type": "none",
            "stock": "1",
            "low_stock_limit": "1",
        })
        self.assertEqual(duplicate_product.status_code, 200)
        self.assertIn(b"A product with that name already exists", duplicate_product.data)
        self.assertEqual(Product.query.filter(
            db.func.lower(Product.name) == "daily cream"
        ).count(), 1)

        duplicate_variant = admin.post("/admin/products/new", data={
            "name": "Option uniqueness test",
            "category_id": "1",
            "price": "300",
            "discount_type": "none",
            "stock": "0",
            "low_stock_limit": "2",
            "variant_name": ["__new__", "__new__"],
            "variant_new_type": ["Weight", "weight"],
            "variant_value": ["75", "75"],
            "variant_unit": ["__new__", "__new__"],
            "variant_new_unit": ["g", "kg"],
            "variant_price": ["", ""],
            "variant_stock": ["3", "3"],
            "is_active": "on",
        })
        self.assertEqual(duplicate_variant.status_code, 200)
        self.assertIn(
            b"Each product option type and value must be unique",
            duplicate_variant.data,
        )
        self.assertIsNone(
            Product.query.filter_by(name="Option uniqueness test").first()
        )

        invalid_unit = admin.post("/admin/products/new", data={
            "name": "Color unit test",
            "category_id": "1",
            "price": "300",
            "discount_type": "none",
            "stock": "0",
            "low_stock_limit": "2",
            "variant_name": ["__new__"],
            "variant_new_type": ["Color"],
            "variant_value": ["Blue"],
            "variant_unit": ["__new__"],
            "variant_new_unit": ["g"],
            "variant_price": [""],
            "variant_stock": ["3"],
            "is_active": "on",
        })
        self.assertEqual(invalid_unit.status_code, 200)
        self.assertIn(
            b"A measuring unit can only be selected for Weight options",
            invalid_unit.data,
        )

    def test_low_stock_is_visible_in_catalog_product_and_cart(self):
        category = db.session.get(Category, 1)
        product = Product(
            category_id=category.id,
            name="Almost gone cream",
            slug="almost-gone-cream",
            sku="LOW-STOCK-CREAM",
            price=Decimal("200.00"),
            stock=0,
            low_stock_limit=3,
            is_active=True,
        )
        product.variants.append(ProductVariant(
            name="Weight",
            value="50",
            unit="g",
            sku="LOW-STOCK-CREAM-50G",
            stock=2,
            is_active=True,
        ))
        db.session.add(product)
        db.session.commit()

        client = self.app.test_client()
        catalog = client.get("/products/")
        self.assertIn(b"Only 2 left across options", catalog.data)
        detail = client.get(f"/products/{product.slug}")
        self.assertIn(b"Only 2 left", detail.data)
        response = client.post(
            f"/client/cart/add/{product.id}",
            data={"variant_id": str(product.variants[0].id), "quantity": "1"},
        )
        self.assertEqual(response.status_code, 302)
        cart = client.get("/client/cart")
        self.assertIn(b"Only 2 left in stock", cart.data)


if __name__ == "__main__":
    unittest.main()