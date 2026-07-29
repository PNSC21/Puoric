from flask import Flask
from config import Config
from database.db import db
from database.models import *
from routes.home import home

app = Flask(__name__)

app.config.from_object(Config)

db.init_app(app)

app.register_blueprint(home)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)