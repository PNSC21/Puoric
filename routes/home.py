from flask import Blueprint, render_template

from services.site_data import site

home = Blueprint("home", __name__)

@home.route("/")
def index():
    return render_template(
        "home.html",
        site=site
    )