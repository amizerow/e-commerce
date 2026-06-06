import os
import re
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from . import db, mail, oauth
from .models import User


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
PASSWORD_VALID_DAYS = 30


def validate_password(password):
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%&*]", password):
        return False
    return True


def redirect_by_role(user):
    if user.role == "Admin":
        return redirect(url_for("routes.admin_dashboard"))
    if user.role == "Seller":
        return redirect(url_for("routes.seller_dashboard"))
    return redirect(url_for("routes.buyer_dashboard"))


def save_profile_picture(file):
    if not file or file.filename == "":
        return "default.jpg"
    filename = secure_filename(file.filename)
    upload_folder = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))
    return filename


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(value, salt):
    return _serializer().dumps(value, salt=salt)


def confirm_token(token, salt, max_age=3600):
    return _serializer().loads(token, salt=salt, max_age=max_age)


def send_email(subject, recipients, body, html=None):
    #msg = Message(subject=subject, recipients=recipients)
    msg = Message(
    subject=subject,
    sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
    recipients=recipients
        )
    msg.body = body
    if html:
        msg.html = html
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print("Email sending failed:", e)
        return False


def send_verification_email(user):
    token = generate_token(user.email, "email-confirm-salt")
    verify_url = url_for("auth.verify_email", token=token, _external=True)
    body = f"""Hello {user.full_name},\n\nPlease verify your SmartMarket account:\n{verify_url}\n\nThis link expires in 1 hour."""
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6">
      <h2>Welcome to SmartMarket</h2>
      <p>Hello {user.full_name},</p>
      <p>Please click below to verify your email address.</p>
      <p><a href="{verify_url}" style="background:#2563eb;color:white;padding:12px 20px;text-decoration:none;border-radius:6px;display:inline-block;">Verify My Email</a></p>
      <p>{verify_url}</p>
    </div>
    """
    ok = send_email("Verify your SmartMarket account", [user.email], body, html)
    if not ok:
        print("Verification link:", verify_url)
    return ok


def send_seller_approval_email(user):
    login_url = url_for("auth.login", _external=True)
    body = f"""Hello {user.full_name},\n\nGood news! Your seller account on SmartMarket has been approved.\n\nLogin here: {login_url}"""
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6">
      <h2>Seller Account Approved</h2>
      <p>Hello {user.full_name},</p>
      <p>Your seller account has been approved. You can now login and add products.</p>
      <p><a href="{login_url}" style="background:#16a34a;color:white;padding:12px 20px;text-decoration:none;border-radius:6px;display:inline-block;">Login</a></p>
    </div>
    """
    return send_email("Your Seller Account Has Been Approved", [user.email], body, html)


def send_password_reset_email(user):
    token = generate_token(user.email, "password-reset-salt")
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    body = f"""Hello {user.full_name},\n\nReset your SmartMarket password using this link:\n{reset_url}\n\nThis link expires in 1 hour."""
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6">
      <h2>Password Reset Request</h2>
      <p>Hello {user.full_name},</p>
      <p>Click below to reset your password.</p>
      <p><a href="{reset_url}" style="background:#2563eb;color:white;padding:12px 20px;text-decoration:none;border-radius:6px;display:inline-block;">Reset Password</a></p>
      <p>{reset_url}</p>
    </div>
    """
    ok = send_email("Reset Your SmartMarket Password", [user.email], body, html)
    if not ok:
        print("Reset link:", reset_url)
    return ok


def send_message_notification_email(user, sender_name):
    inbox_url = url_for("routes.messages", _external=True)
    body = f"""Hello {user.full_name},\n\nYou have a new SmartMarket message from {sender_name}.\n\nOpen inbox: {inbox_url}"""
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6">
      <h2>New SmartMarket Message</h2>
      <p>Hello {user.full_name},</p>
      <p>You have a new message from <strong>{sender_name}</strong>.</p>
      <p><a href="{inbox_url}" style="background:#2563eb;color:white;padding:12px 20px;text-decoration:none;border-radius:6px;display:inline-block;">Open Inbox</a></p>
    </div>
    """
    return send_email("New SmartMarket Message", [user.email], body, html)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "Buyer")
        profile_picture = request.files.get("profile_picture")

        if role not in ["Buyer", "Seller"]:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("auth.register"))
        if not full_name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("auth.register"))
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))
        if not validate_password(password):
            flash("Password must be at least 8 characters with uppercase, lowercase, number and special character.", "danger")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(email=email).first():
            flash("This email is already registered. Please login.", "warning")
            return redirect(url_for("auth.login"))

        user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            profile_picture=save_profile_picture(profile_picture),
            is_verified=False,
            is_approved_seller=False if role == "Seller" else True,
            password_last_updated=datetime.utcnow(),
        )
        db.session.add(user)
        db.session.commit()
        send_verification_email(user)
        flash("Registration successful. Please check your email to verify your account.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))
        if not user.is_verified:
            flash("Please verify your email before logging in.", "warning")
            return redirect(url_for("auth.login"))
        if user.role == "Seller" and not user.is_approved_seller:
            flash("Your seller account is pending admin approval.", "warning")
            return redirect(url_for("auth.login"))

        now = datetime.utcnow()
        expired_by_inactivity = user.last_login and (now - user.last_login).days >= PASSWORD_VALID_DAYS
        expired_by_password_age = user.password_last_updated and (now - user.password_last_updated).days >= PASSWORD_VALID_DAYS
        login_user(user)
        user.last_login = now
        user.last_active = now
        if expired_by_inactivity or expired_by_password_age:
            user.password_reset_required = True
            db.session.commit()
            flash("Your password has expired. Please reset it before continuing.", "warning")
            return redirect(url_for("auth.force_change_password"))
        db.session.commit()
        flash("Login successful.", "success")
        return redirect_by_role(user)
    return render_template("auth/login.html")


@auth_bp.route("/verify/<token>")
def verify_email(token):
    try:
        email = confirm_token(token, "email-confirm-salt")
    except SignatureExpired:
        flash("Verification link expired. Please request a new one.", "danger")
        return redirect(url_for("auth.resend_verification"))
    except BadSignature:
        flash("Invalid verification link.", "danger")
        return redirect(url_for("auth.login"))
    user = User.query.filter_by(email=email).first_or_404()
    user.is_verified = True
    db.session.commit()
    flash("Email verified successfully. You can now login.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("No account found with this email.", "danger")
            return redirect(url_for("auth.resend_verification"))
        if user.is_verified:
            flash("This account is already verified. Please login.", "info")
            return redirect(url_for("auth.login"))
        send_verification_email(user)
        flash("A new verification email has been sent if email is configured.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/resend_verification.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            send_password_reset_email(user)
        flash("If that email exists, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = confirm_token(token, "password-reset-salt")
    except SignatureExpired:
        flash("Password reset link expired.", "danger")
        return redirect(url_for("auth.forgot_password"))
    except BadSignature:
        flash("Invalid password reset link.", "danger")
        return redirect(url_for("auth.forgot_password"))
    user = User.query.filter_by(email=email).first_or_404()
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password", token=token))
        if not validate_password(password):
            flash("Password must be at least 8 characters with uppercase, lowercase, number and special character.", "danger")
            return redirect(url_for("auth.reset_password", token=token))
        user.set_password(password)
        db.session.commit()
        flash("Password reset successfully. Please login.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not current_user.password_hash:
            flash("Google Login accounts cannot change password here.", "warning")
            return redirect(url_for("routes.edit_profile"))
        if not current_user.password_reset_required and not check_password_hash(current_user.password_hash, current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("auth.change_password"))
        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("auth.change_password"))
        if not validate_password(new_password):
            flash("Password must be at least 8 characters with uppercase, lowercase, number and special character.", "danger")
            return redirect(url_for("auth.change_password"))
        current_user.set_password(new_password)
        db.session.commit()
        flash("Password changed successfully.", "success")
        return redirect_by_role(current_user)
    return render_template("auth/change_password.html")


@auth_bp.route("/force-change-password", methods=["GET", "POST"])
@login_required
def force_change_password():
    return change_password()


'''@auth_bp.route("/login/google")
def login_google():
    try:
        redirect_uri = url_for("auth.google_callback", _external=True)
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception as e:
        print("Google OAuth error:", e)
        flash("Google Login is not configured correctly. Please use email and password.", "warning")
        return redirect(url_for("auth.login"))


@auth_bp.route("/login/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo") or oauth.google.userinfo()
        email = user_info.get("email")
        if not email:
            flash("Google account did not return an email.", "danger")
            return redirect(url_for("auth.login"))
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            user = User(
                full_name=user_info.get("name", "Google User"),
                email=email.lower(),
                password_hash=None,
                role="Buyer",
                profile_picture=user_info.get("picture", "default.jpg"),
                is_verified=True,
                is_approved_seller=True,
                auth_provider="google",
                google_sub=user_info.get("sub"),
                last_login=datetime.utcnow(),
                last_active=datetime.utcnow(),
            )
            db.session.add(user)
            db.session.commit()
        login_user(user)
        user.last_login = datetime.utcnow()
        user.last_active = datetime.utcnow()
        db.session.commit()
        flash("Logged in successfully with Google.", "success")
        return redirect_by_role(user)
    except Exception as e:
        print("Google callback error:", e)
        flash("Google Login failed. Please use email and password.", "danger")
        return redirect(url_for("auth.login"))'''
@auth_bp.route("/login/google")
def login_google():
    try:
        redirect_uri = url_for("auth.google_callback", _external=True)
        print("GOOGLE REDIRECT URI:", redirect_uri)
        return oauth.google.authorize_redirect(redirect_uri)

    except Exception as e:
        return f"""
        <h2>Google OAuth Start Error</h2>
        <pre>{str(e)}</pre>
        """


@auth_bp.route("/login/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        print("GOOGLE TOKEN:", token)

        user_info = token.get("userinfo") or oauth.google.userinfo()
        print("GOOGLE USER INFO:", user_info)

        email = user_info.get("email")
        google_sub = user_info.get("sub")

        if not email:
            flash("Google account did not return an email.", "danger")
            return redirect(url_for("auth.login"))

        email = email.lower()
        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                full_name=user_info.get("name", "Google User"),
                email=email,
                password_hash=None,
                role="Buyer",
                profile_picture=user_info.get("picture") or "default.jpg",
                is_verified=True,
                is_approved_seller=True,
                auth_provider="google",
                google_sub=google_sub,
                last_login=datetime.utcnow(),
                last_active=datetime.utcnow(),
                password_last_updated=datetime.utcnow(),
            )
            db.session.add(user)
        else:
            user.is_verified = True
            user.auth_provider = user.auth_provider or "google"
            user.google_sub = user.google_sub or google_sub

        login_user(user)

        user.last_login = datetime.utcnow()
        user.last_active = datetime.utcnow()

        db.session.commit()

        flash("Logged in successfully with Google.", "success")
        return redirect_by_role(user)

    except Exception as e:
        return f"""
        <h2>Google OAuth Callback Error</h2>
        <pre>{str(e)}</pre>
        """

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("routes.index"))
