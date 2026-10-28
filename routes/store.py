from flask import Blueprint, render_template, request

from database.models import Category, Product

store = Blueprint("store", __name__, url_prefix="/products")


@store.route("/")
def catalog():
    category_slug = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()
    query = Product.query.join(Category).filter(
        Product.is_active.is_(True),
        Category.is_active.is_(True),
    )
    if category_slug:
        query = query.filter(
            Category.slug == category_slug,
            Category.is_active.is_(True),
        )
    if search:
        term = f"%{search}%"
        query = query.filter(
            Product.name.ilike(term) | Product.description.ilike(term)
        )
    products = query.order_by(Product.is_featured.desc(), Product.name.asc()).all()
    categories = Category.query.filter_by(is_active=True).order_by(
        Category.name
    ).all()
    return render_template(
        "store/catalog.html",
        products=products,
        categories=categories,
        selected_category=category_slug,
        search=search,
    )


@store.route("/<slug>")
def product_detail(slug):
    product = Product.query.join(Category).filter(
        Product.slug == slug,
        Product.is_active.is_(True),
        Category.is_active.is_(True),
    ).first_or_404()
    variants = [
        variant for variant in product.variants
        if variant.is_active
    ]
    return render_template(
        "store/product_detail.html",
        product=product,
        variants=variants,
        has_options=bool(product.variants),
    )