from sqlalchemy import Index, inspect

from database.db import db
from database.models import AdminUser


def run_migrations():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    columns_to_add = {
        "customers": {
            "password_hash": "VARCHAR(255)",
            "age": "INTEGER",
            "gender": "VARCHAR(30)",
            "skin_type": "VARCHAR(80)",
            "allergies": "TEXT",
        },
        "orders": {
            "shipping_name": "VARCHAR(120) NOT NULL DEFAULT ''",
            "shipping_phone": "VARCHAR(20) NOT NULL DEFAULT ''",
            "shipping_state": "VARCHAR(80) NOT NULL DEFAULT ''",
            "shipping_country": "VARCHAR(80) NOT NULL DEFAULT ''",
            "shipping_address": "TEXT NOT NULL DEFAULT ''",
            "subtotal_amount": "NUMERIC(10, 2) NOT NULL DEFAULT 0",
            "discount_amount": "NUMERIC(10, 2) NOT NULL DEFAULT 0",
            "shipping_amount": "NUMERIC(10, 2) NOT NULL DEFAULT 0",
            "promotion_id": "INTEGER REFERENCES promotions(id)",
            "promotion_name": "VARCHAR(120)",
        },
        "promotions": {
            "target_scope": "VARCHAR(12) NOT NULL DEFAULT 'all'",
            "applies_to_all_categories": "BOOLEAN NOT NULL DEFAULT 1",
            "festival_name": "VARCHAR(80)",
            "minimum_order_amount": "NUMERIC(10, 2)",
        },
        "order_items": {
            "variant_id": "INTEGER REFERENCES product_variants(id)",
        },
        "products": {
            "discount_type": "VARCHAR(12) NOT NULL DEFAULT 'none'",
            "discount_value": "NUMERIC(10, 2)",
        },
        "product_variants": {
            "unit": "VARCHAR(20)",
        },
    }
    with db.engine.begin() as connection:
        for table, additions in columns_to_add.items():
            if table not in table_names:
                continue
            present = {
                column["name"] for column in inspect(connection).get_columns(table)
            }
            for name, definition in additions.items():
                if name not in present:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                    )
        if "orders" in table_names:
            connection.exec_driver_sql(
                "UPDATE orders SET subtotal_amount = total_amount "
                "WHERE subtotal_amount = 0 AND discount_amount = 0"
            )
        if "promotions" in table_names:
            connection.exec_driver_sql(
                "UPDATE promotions SET target_scope = 'categories' "
                "WHERE applies_to_all_categories = 0 "
                "AND target_scope = 'all'"
            )
        if "account_emails" in table_names:
            if "customers" in table_names:
                connection.exec_driver_sql(
                    """
                    INSERT OR IGNORE INTO account_emails
                        (email, account_type, account_id, created_at, updated_at)
                    SELECT lower(trim(email)), 'client', id, CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    FROM customers
                    WHERE email IS NOT NULL AND trim(email) != ''
                    """
                )
            if "admin_users" in table_names:
                connection.exec_driver_sql(
                    """
                    INSERT OR IGNORE INTO account_emails
                        (email, account_type, account_id, created_at, updated_at)
                    SELECT lower(trim(email)), 'admin', id, CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    FROM admin_users
                    WHERE email IS NOT NULL AND trim(email) != ''
                    """
                )

        if {"product_characteristics", "category_characteristics"} <= table_names:
            connection.exec_driver_sql(
                """
                INSERT OR IGNORE INTO category_characteristics
                    (category_id, name, created_at, updated_at)
                SELECT DISTINCT p.category_id, pc.name, CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM product_characteristics pc
                JOIN products p ON p.id = pc.product_id
                """
            )
        if {
            "product_characteristics",
            "products",
            "category_characteristics",
            "category_characteristic_values",
        } <= table_names:
            connection.exec_driver_sql(
                """
                INSERT OR IGNORE INTO category_characteristic_values
                    (characteristic_id, value, created_at, updated_at)
                SELECT DISTINCT cc.id, pc.value, CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM product_characteristics pc
                JOIN products p ON p.id = pc.product_id
                JOIN category_characteristics cc
                    ON cc.category_id = p.category_id
                    AND lower(cc.name) = lower(pc.name)
                """
            )
        if "products" in table_names and {
            "discount_price", "discount_type", "discount_value"
        } <= {
            column["name"] for column in inspect(connection).get_columns("products")
        }:
            connection.exec_driver_sql(
                """
                UPDATE products
                SET discount_type = 'amount',
                    discount_value = price - discount_price
                WHERE discount_price IS NOT NULL
                    AND discount_type = 'none'
                    AND price > discount_price
                """
            )
        if "products" in table_names and "brand" in {
            column["name"] for column in inspect(connection).get_columns("products")
        }:
            connection.exec_driver_sql(
                "UPDATE products SET brand = 'Puoric' WHERE brand != 'Puoric'"
            )

    if "admin_users" in table_names:
        index_name = "uq_admin_users_email"
        indexes = {
            index["name"] for index in inspect(db.engine).get_indexes("admin_users")
        }
        if index_name not in indexes:
            if db.engine.dialect.name == "sqlite":
                with db.engine.begin() as connection:
                    connection.exec_driver_sql(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "uq_admin_users_email ON admin_users (email)"
                    )
            else:
                Index(index_name, AdminUser.email, unique=True).create(
                    bind=db.engine, checkfirst=True
                )

    if db.engine.dialect.name == "sqlite" and "categories" in table_names:
        with db.engine.connect() as connection:
            definition = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'categories'"
            ).scalar()
        if definition and "UNIQUE (name)" in definition:
            raw = db.engine.raw_connection()
            try:
                cursor = raw.cursor()
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    """
                    CREATE TABLE categories_replacement (
                        name VARCHAR(100) NOT NULL,
                        slug VARCHAR(120) NOT NULL UNIQUE,
                        description TEXT,
                        image VARCHAR(255),
                        is_active BOOLEAN NOT NULL,
                        id INTEGER NOT NULL PRIMARY KEY,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO categories_replacement (
                        name, slug, description, image, is_active, id,
                        created_at, updated_at
                    )
                    SELECT name, slug, description, image, is_active, id,
                        created_at, updated_at
                    FROM categories
                    """
                )
                cursor.execute("DROP TABLE categories")
                cursor.execute(
                    "ALTER TABLE categories_replacement RENAME TO categories"
                )
                cursor.execute("COMMIT")
                cursor.execute("PRAGMA foreign_keys=ON")
            except Exception:
                raw.rollback()
                raise
            finally:
                raw.cursor().execute("PRAGMA foreign_keys=ON")
                raw.close()