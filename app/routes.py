import os
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import db
from .auth import send_message_notification_email, send_seller_approval_email
from .models import (
    CartItem,
    Category,
    Conversation,
    Order,
    OrderItem,
    Product,
    SmartMessage,
    User,
    WishlistItem,
)


routes_bp = Blueprint("routes", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ORDER_STATUSES = [
    "Pending",
    "Processing",
    "Ready for Delivery",
    "Delivered",
    "Cancelled",
]


def clean_int(value):
    if value is None:
        return None

    value = str(value).strip()

    if value.lower() in ["", "none", "null", "undefined"]:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_upload(file_storage, default_name="default.jpg"):
    if file_storage and file_storage.filename and allowed_file(file_storage.filename):
        filename = secure_filename(file_storage.filename)

        upload_folder = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
        )

        os.makedirs(upload_folder, exist_ok=True)

        file_storage.save(
            os.path.join(upload_folder, filename)
        )

        return filename

    return default_name


def role_required(role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please login first.", "warning")
                return redirect(url_for("auth.login"))

            if current_user.role != role:
                flash("Access denied.", "danger")
                return redirect(url_for("routes.index"))

            return func(*args, **kwargs)

        return wrapper

    return decorator


def seller_order_query(seller_id):
    return (
        Order.query
        .join(OrderItem)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(Product.seller_id == seller_id)
        .distinct()
        .order_by(Order.created_at.desc())
    )


@routes_bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    category_id_raw = request.args.get("category_id")
    category_id = clean_int(category_id_raw)

    products_query = Product.query.filter_by(is_active=True)

    if q:
        products_query = products_query.filter(
            Product.name.ilike(f"%{q}%")
        )

    if category_id:
        products_query = products_query.filter_by(
            category_id=category_id
        )

    featured_products = (
        products_query
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )

    hot_products = (
        Product.query
        .filter_by(is_active=True)
        .filter(Product.stock > 0)
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )

    categories = Category.query.order_by(Category.name).all()

    stats = {
        "products": Product.query.filter_by(is_active=True).count(),
        "sellers": User.query.filter_by(
            role="Seller",
            is_approved_seller=True,
        ).count(),
        "categories": Category.query.count(),
    }

    return render_template(
        "index.html",
        featured_products=featured_products,
        hot_products=hot_products,
        categories=categories,
        stats=stats,
        q=q,
        selected_category_id=category_id or "",
             )


@routes_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "Admin":
        return redirect(url_for("routes.admin_dashboard"))

    if current_user.role == "Seller":
        return redirect(url_for("routes.seller_dashboard"))

    return redirect(url_for("routes.buyer_dashboard"))


@routes_bp.route("/profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.full_name = (
            request.form.get("full_name", "").strip()
            or current_user.full_name
        )

        current_user.phone = request.form.get("phone", "").strip()
        current_user.address = request.form.get("address", "").strip()

        current_user.profile_picture = save_upload(
            request.files.get("profile_picture"),
            current_user.profile_picture,
        )

        db.session.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for("routes.edit_profile"))

    return render_template("profile.html")


# ==================================================
# Admin
# ==================================================

@routes_bp.route("/admin/dashboard")
@login_required
@role_required("Admin")
def admin_dashboard():
    pending_sellers = (
        User.query
        .filter_by(role="Seller", is_approved_seller=False)
        .order_by(User.created_at.desc())
        .all()
    )

    approved_sellers = (
        User.query
        .filter_by(role="Seller", is_approved_seller=True)
        .order_by(User.created_at.desc())
        .limit(10)
        .all()
    )

    latest_users = (
        User.query
        .order_by(User.last_login.desc(), User.created_at.desc())
        .limit(15)
        .all()
    )
    orders_by_status = {
    status: Order.query.filter_by(status=status).count()
    for status in ORDER_STATUSES
        }

    products_in_stock = Product.query.filter(Product.stock > 5).count()
    products_low_stock = Product.query.filter(
    Product.stock > 0,
    Product.stock <= 5
).count()
    products_out_stock = Product.query.filter(Product.stock <= 0).count()

    users_by_role = {
    "Buyers": User.query.filter_by(role="Buyer").count(),
    "Sellers": User.query.filter_by(role="Seller").count(),
    "Admins": User.query.filter_by(role="Admin").count(),
    }
    orders = (
        Order.query
        .order_by(Order.created_at.desc())
        .limit(12)
        .all()
    )

    stats = {
        "users": User.query.count(),
        "buyers": User.query.filter_by(role="Buyer").count(),
        "sellers": User.query.filter_by(role="Seller").count(),
        "pending_sellers": len(pending_sellers),
        "approved_sellers": User.query.filter_by(
            role="Seller",
            is_approved_seller=True,
        ).count(),
        "products": Product.query.count(),
        "active_products": Product.query.filter_by(is_active=True).count(),
        "orders": Order.query.count(),
        }

    return render_template(
        "dashboards/admin.html",
        pending_sellers=pending_sellers,
        approved_sellers=approved_sellers,
        latest_users=latest_users,
        orders=orders,
        stats=stats,
        order_statuses=ORDER_STATUSES,
        orders_by_status=orders_by_status,
        products_in_stock=products_in_stock,
        products_low_stock=products_low_stock,
        products_out_stock=products_out_stock,
        users_by_role=users_by_role,
    )


@routes_bp.post("/admin/sellers/<int:user_id>/approve")
@login_required
@role_required("Admin")
def approve_seller(user_id):
    seller = User.query.get_or_404(user_id)

    if seller.role != "Seller":
        flash("Selected user is not a seller.", "danger")
        return redirect(url_for("routes.admin_dashboard"))

    if seller.is_approved_seller:
        flash(f"{seller.full_name} is already approved.", "info")
        return redirect(url_for("routes.admin_dashboard"))

    seller.is_approved_seller = True
    db.session.commit()

    email_sent = send_seller_approval_email(seller)

    if email_sent:
        flash(
            f"{seller.full_name} has been approved and confirmation email was sent.",
            "success",
        )
    else:
        flash(
            f"{seller.full_name} has been approved, but email could not be sent.",
            "warning",
        )

    return redirect(url_for("routes.admin_dashboard"))


@routes_bp.post("/admin/sellers/<int:user_id>/reject")
@login_required
@role_required("Admin")
def reject_seller(user_id):
    seller = User.query.get_or_404(user_id)

    if seller.role != "Seller":
        flash("Selected user is not a seller.", "danger")
        return redirect(url_for("routes.admin_dashboard"))

    seller.role = "Buyer"
    seller.is_approved_seller = False

    db.session.commit()

    flash(f"{seller.full_name} was rejected and changed to Buyer.", "info")
    return redirect(url_for("routes.admin_dashboard"))


@routes_bp.post("/admin/orders/<int:order_id>/status")
@login_required
@role_required("Admin")
def admin_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status")

    if status not in ORDER_STATUSES:
        flash("Invalid order status.", "danger")
    else:
        order.status = status
        db.session.commit()
        flash("Order status updated.", "success")

    return redirect(url_for("routes.admin_dashboard"))


# ==================================================
# Seller
# ==================================================

@routes_bp.route("/seller/dashboard", methods=["GET", "POST"])
@login_required
@role_required("Seller")
def seller_dashboard():
    if not current_user.is_approved_seller:
        flash("Your seller account is still pending admin approval.", "warning")
        return redirect(url_for("routes.index"))

    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        currency = request.form.get("currency", "RWF")
        category_id = clean_int(request.form.get("category_id"))
        image_file = request.files.get("image")

        try:
            price = float(request.form.get("price", "0"))
            stock = int(request.form.get("stock", "0"))
        except ValueError:
            flash("Price and stock must be valid numbers.", "danger")
            return redirect(url_for("routes.seller_dashboard"))

        if not name or price <= 0 or stock < 0 or not category_id:
            flash(
                "Please complete all product fields correctly. Price must be positive.",
                "danger",
            )
            return redirect(url_for("routes.seller_dashboard"))

        if not image_file or image_file.filename == "":
            flash("Product image is required.", "danger")
            return redirect(url_for("routes.seller_dashboard"))

        product = Product(
            name=name,
            description=description,
            price=price,
            currency=currency,
            stock=stock,
            category_id=category_id,
            seller_id=current_user.id,
            image=save_upload(image_file, "product-default.jpg"),
            is_active=True,
        )

        db.session.add(product)
        db.session.commit()

        flash("Product added successfully.", "success")
        return redirect(url_for("routes.seller_dashboard"))

    products = (
        Product.query
        .filter_by(seller_id=current_user.id)
        .order_by(Product.created_at.desc())
        .all()
    )

    low_stock_count = (
        Product.query
        .filter(
            Product.seller_id == current_user.id,
            Product.stock <= 5,
        )
        .count()
    )

    return render_template(
        "dashboards/seller.html",
        products=products,
        categories=categories,
        low_stock_count=low_stock_count,
    )


@routes_bp.route("/seller/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("Seller")
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id != current_user.id:
        flash("You cannot edit this product.", "danger")
        return redirect(url_for("routes.seller_dashboard"))

    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        category_id = clean_int(request.form.get("category_id"))

        product.name = request.form.get("name", "").strip() or product.name
        product.description = request.form.get("description", "").strip()
        product.currency = request.form.get("currency", "RWF")

        try:
            product.price = float(request.form.get("price", product.price))
            product.stock = int(request.form.get("stock", product.stock))
        except ValueError:
            flash("Price and stock must be valid.", "danger")
            return redirect(url_for("routes.edit_product", product_id=product.id))

        if not category_id:
            flash("Category is required.", "danger")
            return redirect(url_for("routes.edit_product", product_id=product.id))

        if product.price <= 0 or product.stock < 0:
            flash("Price must be positive and stock cannot be negative.", "danger")
            return redirect(url_for("routes.edit_product", product_id=product.id))

        product.category_id = category_id
        product.is_active = True if request.form.get("is_active") else False
        product.image = save_upload(request.files.get("image"), product.image)

        db.session.commit()

        flash("Product updated successfully.", "success")
        return redirect(url_for("routes.seller_dashboard"))

    return render_template(
        "seller_product_edit.html",
        product=product,
        categories=categories,
    )


@routes_bp.post("/seller/products/<int:product_id>/delete")
@login_required
@role_required("Seller")
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id != current_user.id:
        flash("You cannot delete this product.", "danger")
    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted.", "success")

    return redirect(url_for("routes.seller_dashboard"))


@routes_bp.route("/seller/orders")
@login_required
@role_required("Seller")
def seller_orders():
    orders = seller_order_query(current_user.id).all()

    return render_template(
        "seller_orders.html",
        orders=orders,
        order_statuses=ORDER_STATUSES,
    )


@routes_bp.post("/seller/orders/<int:order_id>/status")
@login_required
@role_required("Seller")
def seller_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)

    owns_item = any(
        item.product and item.product.seller_id == current_user.id
        for item in order.items
    )

    if not owns_item:
        flash("Access denied.", "danger")
        return redirect(url_for("routes.seller_orders"))

    status = request.form.get("status")

    if status not in ORDER_STATUSES:
        flash("Invalid order status.", "danger")
    else:
        order.status = status
        db.session.commit()
        flash("Order status updated.", "success")

    return redirect(url_for("routes.seller_orders"))


# ==================================================
# Buyer
# ==================================================

@routes_bp.route("/buyer/dashboard")
@login_required
@role_required("Buyer")
def buyer_dashboard():
    q = request.args.get("q", "").strip()
    category_id = clean_int(request.args.get("category_id"))
    sort = request.args.get("sort", "newest")

    products_query = Product.query.filter_by(is_active=True)

    if q:
        products_query = products_query.filter(
            Product.name.ilike(f"%{q}%")
        )

    if category_id:
        products_query = products_query.filter_by(
            category_id=category_id
        )

    if sort == "price_low":
        products_query = products_query.order_by(Product.price.asc())
    elif sort == "price_high":
        products_query = products_query.order_by(Product.price.desc())
    elif sort == "name":
        products_query = products_query.order_by(Product.name.asc())
    else:
        products_query = products_query.order_by(Product.created_at.desc())

    products = products_query.all()
    categories = Category.query.order_by(Category.name).all()

    cart_items = CartItem.query.filter_by(
        buyer_id=current_user.id
    ).all()

    wishlist_items = WishlistItem.query.filter_by(
        buyer_id=current_user.id
    ).all()

    wishlist_product_ids = {
        item.product_id
        for item in wishlist_items
    }

    cart_total = sum(
        item.product.price * item.quantity
        for item in cart_items
    )

    return render_template(
        "dashboards/buyer.html",
        products=products,
        categories=categories,
        cart_items=cart_items,
        wishlist_items=wishlist_items,
        wishlist_product_ids=wishlist_product_ids,
        cart_total=cart_total,
        q=q,
        selected_category_id=category_id or "",
        sort=sort,
    )


@routes_bp.route("/products/<int:product_id>")
def product_details(product_id):
    product = Product.query.get_or_404(product_id)

    if not product.is_active:
        flash("Product is not available.", "warning")
        return redirect(url_for("routes.index"))

    return render_template("product_details.html", product=product)


@routes_bp.post("/buyer/cart/<int:product_id>/add")
@login_required
@role_required("Buyer")
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)

    if not product.is_active:
        flash("This product is not available.", "warning")
        return redirect(url_for("routes.buyer_dashboard"))

    if product.stock <= 0:
        flash("This product is out of stock.", "warning")
        return redirect(url_for("routes.buyer_dashboard"))

    item = CartItem.query.filter_by(
        buyer_id=current_user.id,
        product_id=product.id,
    ).first()

    if item:
        if item.quantity >= product.stock:
            flash("You cannot add more than available stock.", "warning")
            return redirect(url_for("routes.buyer_dashboard"))

        item.quantity += 1
    else:
        db.session.add(
            CartItem(
                buyer_id=current_user.id,
                product_id=product.id,
                quantity=1,
            )
        )

    db.session.commit()

    flash("Product added to cart.", "success")
    return redirect(url_for("routes.buyer_dashboard"))


@routes_bp.route("/buyer/cart")
@login_required
@role_required("Buyer")
def cart_view():
    cart_items = CartItem.query.filter_by(
        buyer_id=current_user.id
    ).all()

    cart_total = sum(
        item.product.price * item.quantity
        for item in cart_items
    )

    return render_template(
        "cart.html",
        cart_items=cart_items,
        cart_total=cart_total,
    )


@routes_bp.post("/buyer/cart/<int:item_id>/update")
@login_required
@role_required("Buyer")
def update_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)

    if item.buyer_id != current_user.id:
        flash("Access denied.", "danger")
        return redirect(url_for("routes.buyer_dashboard"))

    if item.product.stock <= 0:
        db.session.delete(item)
        db.session.commit()
        flash("Product is out of stock and was removed from your cart.", "warning")
        return redirect(url_for("routes.buyer_dashboard"))

    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1

    item.quantity = min(
        max(1, quantity),
        item.product.stock,
    )

    db.session.commit()

    flash("Cart quantity updated.", "success")
    return redirect(url_for("routes.buyer_dashboard"))


@routes_bp.post("/buyer/cart/<int:item_id>/ajax-update")
@login_required
@role_required("Buyer")
def ajax_update_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)

    if item.buyer_id != current_user.id:
        return jsonify({
            "success": False,
            "message": "Access denied.",
        }), 403

    data = request.get_json() or {}

    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    if item.product.stock <= 0:
        db.session.delete(item)
        db.session.commit()

        cart_items = CartItem.query.filter_by(
            buyer_id=current_user.id
        ).all()

        cart_total = sum(
            i.product.price * i.quantity
            for i in cart_items
        )

        return jsonify({
            "success": True,
            "removed": True,
            "cart_total": cart_total,
            "cart_count": len(cart_items),
        })

    quantity = min(
        max(1, quantity),
        item.product.stock,
    )

    item.quantity = quantity
    db.session.commit()

    cart_items = CartItem.query.filter_by(
        buyer_id=current_user.id
    ).all()

    cart_total = sum(
        i.product.price * i.quantity
        for i in cart_items
    )

    return jsonify({
        "success": True,
        "item_id": item.id,
        "quantity": item.quantity,
        "subtotal": item.product.price * item.quantity,
        "cart_total": cart_total,
        "cart_count": len(cart_items),
        "max_stock": item.product.stock,
    })


@routes_bp.post("/buyer/cart/<int:item_id>/remove")
@login_required
@role_required("Buyer")
def remove_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)

    if item.buyer_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash("Product removed from cart.", "success")

    return redirect(url_for("routes.buyer_dashboard"))


@routes_bp.post("/buyer/cart/<int:item_id>/ajax-remove")
@login_required
@role_required("Buyer")
def ajax_remove_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)

    if item.buyer_id != current_user.id:
        return jsonify({
            "success": False,
            "message": "Access denied.",
        }), 403

    db.session.delete(item)
    db.session.commit()

    cart_items = CartItem.query.filter_by(
        buyer_id=current_user.id
    ).all()

    cart_total = sum(
        i.product.price * i.quantity
        for i in cart_items
    )

    return jsonify({
        "success": True,
        "removed": True,
        "item_id": item_id,
        "cart_total": cart_total,
        "cart_count": len(cart_items),
    })


@routes_bp.post("/buyer/wishlist/<int:product_id>/add")
@login_required
@role_required("Buyer")
def add_to_wishlist(product_id):
    product = Product.query.get_or_404(product_id)

    exists = WishlistItem.query.filter_by(
        buyer_id=current_user.id,
        product_id=product.id,
    ).first()

    if not exists:
        db.session.add(
            WishlistItem(
                buyer_id=current_user.id,
                product_id=product.id,
            )
        )

        db.session.commit()

        flash("Product added to wishlist.", "success")
    else:
        flash("Product is already in your wishlist.", "info")

    return redirect(url_for("routes.buyer_dashboard"))


@routes_bp.post("/buyer/wishlist/<int:item_id>/remove")
@login_required
@role_required("Buyer")
def remove_wishlist_item(item_id):
    item = WishlistItem.query.get_or_404(item_id)

    if item.buyer_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash("Product removed from wishlist.", "success")

    return redirect(url_for("routes.buyer_dashboard"))


@routes_bp.route("/buyer/checkout", methods=["GET", "POST"])
@login_required
@role_required("Buyer")
def checkout():
    cart_items = CartItem.query.filter_by(
        buyer_id=current_user.id
    ).all()

    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("routes.buyer_dashboard"))

    cart_total = sum(
        item.product.price * item.quantity
        for item in cart_items
    )

    if request.method == "POST":
        delivery_full_name = request.form.get("delivery_full_name", "").strip()
        delivery_phone = request.form.get("delivery_phone", "").strip()
        delivery_address = request.form.get("delivery_address", "").strip()
        delivery_city = request.form.get("delivery_city", "").strip()
        delivery_notes = request.form.get("delivery_notes", "").strip()

        if (
            not delivery_full_name
            or not delivery_phone
            or not delivery_address
            or not delivery_city
        ):
            flash("Please complete all required delivery fields.", "danger")
            return redirect(url_for("routes.checkout"))

        order = Order(
            buyer_id=current_user.id,
            status="Pending",
            currency="RWF",
            total_amount=cart_total,
            delivery_full_name=delivery_full_name,
            delivery_phone=delivery_phone,
            delivery_address=delivery_address,
            delivery_city=delivery_city,
            delivery_notes=delivery_notes,
        )

        db.session.add(order)

        for item in cart_items:
            if item.quantity > item.product.stock:
                flash(f"Not enough stock for {item.product.name}.", "danger")
                db.session.rollback()
                return redirect(url_for("routes.buyer_dashboard"))

            
            item.product.stock -= item.quantity

            db.session.add(
                OrderItem(
                    order=order,
                    product_id=item.product_id,
                    product_name=item.product.name,
                    product_image=item.product.image,
                    quantity=item.quantity,
                    unit_price=item.product.price,
                    currency=item.product.currency,
                )
            )

            db.session.delete(item)

        db.session.commit()

        flash("Order created successfully with delivery address.", "success")
        return redirect(url_for("routes.buyer_orders"))

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        cart_total=cart_total,
    )


@routes_bp.route("/buyer/orders")
@login_required
@role_required("Buyer")
def buyer_orders():
    orders = (
        Order.query
        .filter_by(buyer_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    return render_template(
        "orders.html",
        orders=orders,
    )


# ==================================================
# Messaging
# ==================================================

@routes_bp.route("/messages")
@login_required
def messages():
    if current_user.role == "Buyer":
        conversations = (
            Conversation.query
            .filter_by(buyer_id=current_user.id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
    elif current_user.role == "Seller":
        conversations = (
            Conversation.query
            .filter_by(seller_id=current_user.id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
    else:
        flash("Messaging is available for buyers and sellers only.", "warning")
        return redirect(url_for("routes.dashboard"))

    return render_template(
        "messages/inbox.html",
        conversations=conversations,
    )


@routes_bp.route("/buyer/message/seller/<int:seller_id>", methods=["GET", "POST"])
@login_required
@role_required("Buyer")
def start_conversation(seller_id):
    seller = User.query.get_or_404(seller_id)

    product_id = clean_int(
        request.args.get("product_id")
        or request.form.get("product_id")
    )

    if seller.role != "Seller":
        flash("This user is not a seller.", "danger")
        return redirect(url_for("routes.buyer_dashboard"))

    conversation = Conversation.query.filter_by(
        buyer_id=current_user.id,
        seller_id=seller.id,
        product_id=product_id,
    ).first()

    if not conversation:
        conversation = Conversation(
            buyer_id=current_user.id,
            seller_id=seller.id,
            product_id=product_id,
        )

        db.session.add(conversation)
        db.session.commit()

    if request.method == "POST":
        body = request.form.get("body", "").strip()

        if body:
            msg = SmartMessage(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                body=body,
            )

            conversation.updated_at = datetime.utcnow()

            db.session.add(msg)
            db.session.commit()

            send_message_notification_email(seller, current_user.full_name)

            flash("Message sent to seller.", "success")
            return redirect(
                url_for(
                    "routes.conversation",
                    conversation_id=conversation.id,
                )
            )

        flash("Message cannot be empty.", "danger")

    return render_template(
        "messages/conversation.html",
        conversation=conversation,
    )


@routes_bp.route("/messages/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def conversation(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)

    if current_user.id not in [conversation.buyer_id, conversation.seller_id]:
        flash("Access denied.", "danger")
        return redirect(url_for("routes.dashboard"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()

        if body:
            msg = SmartMessage(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                body=body,
            )

            conversation.updated_at = datetime.utcnow()

            db.session.add(msg)
            db.session.commit()

            recipient = (
                conversation.seller
                if current_user.id == conversation.buyer_id
                else conversation.buyer
            )

            send_message_notification_email(
                recipient,
                current_user.full_name,
            )

            flash("Message sent.", "success")
            return redirect(
                url_for(
                    "routes.conversation",
                    conversation_id=conversation.id,
                )
            )

        flash("Message cannot be empty.", "danger")

    SmartMessage.query.filter(
        SmartMessage.conversation_id == conversation.id,
        SmartMessage.sender_id != current_user.id,
        SmartMessage.is_read.is_(False),
    ).update({"is_read": True})

    db.session.commit()

    return render_template(
        "messages/conversation.html",
        conversation=conversation,
    )