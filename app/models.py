from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="Buyer")
    profile_picture = db.Column(db.String(255), default="default.jpg")
    phone = db.Column(db.String(30), default="")
    address = db.Column(db.String(255), default="")
    auth_provider = db.Column(db.String(30), default="local")
    google_sub = db.Column(db.String(120), unique=True, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_approved_seller = db.Column(db.Boolean, default=False)
    password_reset_required = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    last_active = db.Column(db.DateTime)
    password_last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", back_populates="seller", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", back_populates="buyer", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="buyer", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="buyer", cascade="all, delete-orphan")

    sent_messages = db.relationship("SmartMessage", foreign_keys="SmartMessage.sender_id", back_populates="sender")
    buyer_conversations = db.relationship("Conversation", foreign_keys="Conversation.buyer_id", back_populates="buyer", cascade="all, delete-orphan")
    seller_conversations = db.relationship("Conversation", foreign_keys="Conversation.seller_id", back_populates="seller", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_last_updated = datetime.utcnow()
        self.password_reset_required = False

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def dashboard_endpoint(self):
        if self.role == "Admin":
            return "routes.admin_dashboard"
        if self.role == "Seller":
            return "routes.seller_dashboard"
        return "routes.buyer_dashboard"

    def password_days_remaining(self):
        if not self.password_last_updated:
            return 0
        used = (datetime.utcnow() - self.password_last_updated).days
        return max(0, 30 - used)

    def inactive_days(self):
        if not self.last_login:
            return None
        return (datetime.utcnow() - self.last_login).days


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="RWF")
    image = db.Column(db.String(255), default="product-default.jpg")
    stock = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)

    seller = db.relationship("User", back_populates="products")
    category = db.relationship("Category", back_populates="products")
    cart_items = db.relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan")
    order_items = db.relationship("OrderItem", back_populates="product")


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship("User", back_populates="cart_items")
    product = db.relationship("Product", back_populates="cart_items")

    __table_args__ = (db.UniqueConstraint("buyer_id", "product_id", name="unique_buyer_product_cart"),)


class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship("User", back_populates="wishlist_items")
    product = db.relationship("Product", back_populates="wishlist_items")

    __table_args__ = (db.UniqueConstraint("buyer_id", "product_id", name="unique_buyer_product_wishlist"),)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    total_amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default="RWF")
    delivery_full_name = db.Column(db.String(120))
    delivery_phone = db.Column(db.String(30))
    delivery_address = db.Column(db.Text)
    delivery_city = db.Column(db.String(100))
    delivery_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    buyer = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    product_name = db.Column(db.String(100))
    product_image = db.Column(db.String(255))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="RWF")

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    buyer = db.relationship("User", foreign_keys=[buyer_id], back_populates="buyer_conversations")
    seller = db.relationship("User", foreign_keys=[seller_id], back_populates="seller_conversations")
    product = db.relationship("Product")
    messages = db.relationship("SmartMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="SmartMessage.created_at")

    __table_args__ = (db.UniqueConstraint("buyer_id", "seller_id", "product_id", name="unique_conversation_product"),)


class SmartMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
