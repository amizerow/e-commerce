from datetime import datetime, timedelta

from flask import Flask, flash, redirect, request, session, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.security import generate_password_hash

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
oauth = OAuth()

login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.permanent_session_lifetime = timedelta(minutes=10)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)

    print("GOOGLE_CLIENT_ID:", app.config.get("GOOGLE_CLIENT_ID"))
    print("GOOGLE_CLIENT_SECRET:", "SET" if app.config.get("GOOGLE_CLIENT_SECRET") else None)

    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config.get("GOOGLE_CLIENT_ID"),
            client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile"
            },
        )
        print("Google OAuth registered successfully.")
    else:
        print("WARNING: Google OAuth is not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")

    from app.models import User, CartItem, SmartMessage

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def auto_logout_after_inactivity():
        session.permanent = True

        public_endpoints = {
            "auth.login",
            "auth.register",
            "auth.logout",
            "auth.login_google",
            "auth.google_callback",
            "auth.verify_email",
            "auth.resend_verification",
            "auth.forgot_password",
            "auth.reset_password",
            "routes.index",
            "static",
        }

        if request.endpoint in public_endpoints or not current_user.is_authenticated:
            return

        now = datetime.utcnow()
        last_activity = session.get("last_activity")

        if last_activity:
            last_activity_time = datetime.fromisoformat(last_activity)
            inactive_minutes = (now - last_activity_time).total_seconds() / 60

            if inactive_minutes >= 10:
                logout_user()
                session.clear()
                flash("You were logged out after 10 minutes of inactivity.", "warning")
                return redirect(url_for("auth.login"))

        session["last_activity"] = now.isoformat()

        if hasattr(current_user, "last_active"):
            current_user.last_active = now
            db.session.commit()

    @app.context_processor
    def inject_global_variables():
        cart_count = 0
        unread_messages = 0

        if current_user.is_authenticated:
            if current_user.role == "Buyer":
                cart_count = CartItem.query.filter_by(
                    buyer_id=current_user.id
                ).count()

            if current_user.role in ["Buyer", "Seller"]:
                unread_messages = (
                    SmartMessage.query
                    .join(SmartMessage.conversation)
                    .filter(SmartMessage.sender_id != current_user.id)
                    .filter(SmartMessage.is_read.is_(False))
                    .filter(
                        (SmartMessage.conversation.has(buyer_id=current_user.id)) |
                        (SmartMessage.conversation.has(seller_id=current_user.id))
                    )
                    .count()
                )

        return {
            "cart_count": cart_count,
            "unread_messages": unread_messages,
            "current_year": datetime.utcnow().year,
        }

    from app.auth import auth_bp
    from app.routes import routes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(routes_bp)

    with app.app_context():
        db.create_all()

        admin = User.query.filter_by(role="Admin").first()

        if not admin:
            admin = User(
                full_name="System Administrator",
                email=app.config.get("ADMIN_EMAIL") or "amizerow@gmail.com",
                password_hash=generate_password_hash(
                    app.config.get("ADMIN_PASSWORD") or "Admin@123"
                ),
                role="Admin",
                is_verified=True,
                is_approved_seller=True,
                profile_picture="default.jpg",
                password_last_updated=datetime.utcnow(),
                last_login=None,
            )

            db.session.add(admin)
            db.session.commit()

            print("=" * 60)
            print("DEFAULT ADMIN ACCOUNT CREATED")
            print("Email:", admin.email)
            print("Password:", app.config.get("ADMIN_PASSWORD") or "Admin@123")
            print("=" * 60)

    return app