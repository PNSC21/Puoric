from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, session

load_dotenv()
from config import Config
from database.db import db


def create_app(config_object=Config):
    app = Flask(__name__)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_object(config_object)
    db.init_app(app)

    from database.migrations import run_migrations
    from routes.admin import admin
    from routes.customer import customer
    from routes.home import home
    from routes.store import store
    from services.site_data import site

    app.register_blueprint(home)
    app.register_blueprint(customer)
    app.register_blueprint(admin)
    app.register_blueprint(store)

    @app.context_processor
    def inject_site():
        return {
            "site": site,
            "customer_id": session.get("customer_id"),
            "admin_id": session.get("admin_id"),
            "cart_count": sum(session.get("cart", {}).values()),
        }

    @app.template_filter("currency")
    def currency(value):
        return f"₹{float(value):,.2f}"

    with app.app_context():
        db.create_all()
        run_migrations()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
