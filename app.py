from flask import Flask, render_template, request, jsonify, send_from_directory, abort
try:
    from flask_cors import CORS
    _HAS_FLASK_CORS = True
except Exception:
    CORS = None
    _HAS_FLASK_CORS = False
import os
import random
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# Persistence and auth
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from flask_mail import Mail, Message
except Exception:
    Mail = None
    Message = None
try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None

# Initialize app
app = Flask(__name__)
# Secret key for session cookies (generate a secure one for production)
app.config.setdefault('SECRET_KEY', os.environ.get('SECRET_KEY', 'dev-secret-key'))

# Database (SQLite file in project)
app.config.setdefault('SQLALCHEMY_DATABASE_URI', os.environ.get('DATABASE_URL', 'sqlite:///data.db'))
app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)

# Mail config (optional)
app.config.setdefault('MAIL_SERVER', os.environ.get('MAIL_SERVER', ''))
app.config.setdefault('MAIL_PORT', int(os.environ.get('MAIL_PORT', '0') or 0))
app.config.setdefault('MAIL_USERNAME', os.environ.get('MAIL_USERNAME', ''))
app.config.setdefault('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
app.config.setdefault('MAIL_USE_TLS', bool(os.environ.get('MAIL_USE_TLS', False)))
app.config.setdefault('MAIL_USE_SSL', bool(os.environ.get('MAIL_USE_SSL', False)))

# Twilio config (optional)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_FROM = os.environ.get('TWILIO_FROM')

# Enable CORS if the package is available (optional)
if _HAS_FLASK_CORS and CORS:
    CORS(app)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
mail = Mail(app) if Mail else None
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if (TwilioClient and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) else None

# upload folder
UPLOAD_FOLDER = os.path.join(app.static_folder or 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# in-memory rate-limits and simple caches (not persisted)
# ----------------------------
# DATABASE MODELS
# ----------------------------


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(256), unique=True, nullable=False)  # normalized key (email lower or digits-only mobile)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(256), nullable=True)
    mobile = db.Column(db.String(32), nullable=True)
    licence = db.Column(db.String(64), nullable=True)
    address = db.Column(db.String(256), nullable=True)
    photo = db.Column(db.String(256), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(128), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'identifier': self.identifier,
            'name': self.name,
            'email': self.email,
            'mobile': self.mobile,
            'licence': self.licence,
            'address': self.address,
            'photo': self.photo,
            'is_admin': self.is_admin
        }


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(256), nullable=False)
    type = db.Column(db.String(64), nullable=False)
    weight = db.Column(db.String(64), nullable=True)
    lat = db.Column(db.String(64), nullable=True)
    lon = db.Column(db.String(64), nullable=True)
    photo = db.Column(db.String(256), nullable=True)
    timestamp = db.Column(db.String(64), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'location': self.location,
            'type': self.type,
            'weight': self.weight,
            'lat': self.lat,
            'lon': self.lon,
            'photo': self.photo,
            'timestamp': self.timestamp
        }


# (OTP removed - using passcode/password flow now)


# create tables if they don't exist
with app.app_context():
    db.create_all()
    # Seed an admin user automatically if environment variables are provided
    try:
        ADMIN_MOBILE = os.environ.get('ADMIN_MOBILE')
        ADMIN_PASSCODE = os.environ.get('ADMIN_PASSCODE')
        ADMIN_NAME = os.environ.get('ADMIN_NAME', 'Administrator')
        if ADMIN_MOBILE and ADMIN_PASSCODE:
            mobile_norm = ''.join(filter(str.isdigit, ADMIN_MOBILE))
            if len(mobile_norm) == 10 and not User.query.filter_by(identifier=mobile_norm).first():
                admin = User(identifier=mobile_norm, name=ADMIN_NAME, mobile=mobile_norm, is_admin=True)
                admin.password_hash = generate_password_hash(ADMIN_PASSCODE)
                db.session.add(admin)
                db.session.commit()
                app.logger.info('Seeded admin user: %s', mobile_norm)
    except Exception as _err:
        app.logger.exception('Admin seed failed')
    # Small automatic migration: add missing columns to existing tables (safe ALTER TABLE ADD COLUMN)
    try:
        engine = db.get_engine()
        conn = engine.connect()
        # helper to check columns
        def table_has_column(table_name, column_name):
            res = conn.execute(f"PRAGMA table_info('{table_name}')")
            cols = [r[1] for r in res.fetchall()]
            return column_name in cols

        user_table = User.__table__.name
        # add password_hash if missing
        if not table_has_column(user_table, 'password_hash'):
            app.logger.info('Adding password_hash column to %s', user_table)
            conn.execute(f"ALTER TABLE {user_table} ADD COLUMN password_hash VARCHAR(128)")
        # add is_admin if missing
        if not table_has_column(user_table, 'is_admin'):
            app.logger.info('Adding is_admin column to %s', user_table)
            conn.execute(f"ALTER TABLE {user_table} ADD COLUMN is_admin BOOLEAN DEFAULT 0")

        conn.close()
    except Exception:
        app.logger.exception('Automatic schema migration failed')

# ----------------------------
# HOME & PAGES
# ----------------------------


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health():
    """Simple health check for deployment platforms and monitoring.

    Returns 200 and a small JSON payload if the app can connect to the database.
    """
    ok = True
    msg = 'ok'
    try:
        # quick DB check
        db.session.execute('SELECT 1')
    except Exception as e:
        ok = False
        msg = f'db error: {e}'
    return jsonify({'status': 'ok' if ok else 'error', 'message': msg}), (200 if ok else 500)


@app.route('/track', endpoint='track')
def track_page():
    return render_template('track.html')


@app.route('/report', endpoint='report')
def report_page():
    return render_template('report.html')


@app.route('/about', endpoint='about')
def about_page():
    return render_template('about.html')


@app.route('/dashboard', endpoint='dashboard')
def dashboard_page():
    return render_template('dashboard.html')


# Serve legacy static asset paths that some pages or bots may request directly.
# This prevents 404s for requests like /static/style.css or /static/script.js
# and keeps backward-compatible URLs working on deployed sites.
@app.route('/static/style.css')
def legacy_style_css():
    app.logger.debug('Serving legacy /static/style.css -> static/css/style.css')
    return send_from_directory(app.static_folder, 'css/style.css')


@app.route('/static/script.js')
def legacy_script_js():
    app.logger.debug('Serving legacy /static/script.js -> static/js/script.js')
    # prefer the consolidated script if present
    if os.path.exists(os.path.join(app.static_folder, 'js', 'script.js')):
        return send_from_directory(app.static_folder, 'js/script.js')
    return send_from_directory(app.static_folder, 'js/main.js')


# (OTP/send_code removed) Using simple mobile+passcode signup/login instead.


# ----------------------------
# SIGNUP
# ----------------------------
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()

    name = data.get("name")
    mobile = data.get("mobile")
    passcode = data.get("passcode")

    if not all([name, mobile, passcode]):
        return jsonify({"message": "All fields required"}), 400

    if mobile in users:
        return jsonify({"message": "User already exists"}), 409

    users[mobile] = {
        "name": name,
        "mobile": mobile,
        "passcode": passcode,
        "licence": "",
        "address": "",
        "photo": "",
        "is_admin": False
    }

    return jsonify({
        "message": "Signup successful",
        "user": users[mobile]
    }), 200



# ----------------------------
# LOGIN
# ----------------------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    mobile = data.get("mobile")
    passcode = data.get("passcode")

    if not mobile or not passcode:
        return jsonify({"message": "Missing credentials"}), 400

    if mobile not in users:
        return jsonify({"message": "User not found"}), 404

    if users[mobile]["passcode"] != passcode:
        return jsonify({"message": "Incorrect passcode"}), 401

    return jsonify({
        "message": f"Welcome {users[mobile]['name']}",
        "user": users[mobile]
    }), 200



@app.route('/api/logout', methods=['POST'])
def logout():
    return jsonify({"message": "Logged out"})



# ----------------------------
# PROFILE UPDATE
# ----------------------------
@app.route('/api/profile', methods=['POST'])
@login_required
def profile():
    # update profile for logged-in user
    user = current_user
    name = request.form.get('name')
    address = request.form.get('address')
    licence = request.form.get('licence')

    if name:
        user.name = name
    if licence:
        user.licence = licence
    user.address = address

    photo = request.files.get('photo')
    if photo:
        filename = secure_filename(photo.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(path)
        user.photo = filename

    db.session.commit()
    return jsonify({'message':'Profile saved','user': user.to_dict()}), 200


# ----------------------------
# SAVE WASTE REPORT
# ----------------------------
# ----------------------------
# SAVE WASTE REPORT
# ----------------------------
@app.route('/api/report', methods=['POST'])
def report_waste():

    location = request.form.get("location")
    waste_type = request.form.get("type")
    weight = request.form.get("weight")
    lat = request.form.get("lat")
    lon = request.form.get("lon")

    if not location or not waste_type or not weight:
        return jsonify({"message": "Missing fields"}), 400

    photo = request.files.get("photo")
    filename = ""

    if photo:
        filename = secure_filename(photo.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(path)

    report = {
        "location": location,
        "type": waste_type,
        "weight": weight,
        "lat": lat,
        "lon": lon,
        "photo": filename
    }

    reports.append(report)

    print("New Waste Report:", report)

    return jsonify({
        "message": "Waste report saved",
        "report": report   # ✅ VERY IMPORTANT
    }), 200



# ----------------------------
# GET ALL REPORTS (for map)
# ----------------------------
@app.route('/api/reports', methods=['GET'])
def get_reports():
    rs = Report.query.order_by(Report.id.asc()).all()
    return jsonify([r.to_dict() for r in rs])


# Admin dashboard data
@app.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard():
    # return counts and recent reports
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'message':'Forbidden'}), 403
    total_users = User.query.count()
    total_reports = Report.query.count()
    recent_q = Report.query.order_by(Report.id.desc()).limit(100).all()
    recent = [r.to_dict() for r in recent_q]
    return jsonify({
        'total_users': total_users,
        'total_reports': total_reports,
        'reports': recent
    })


@app.route('/admin', methods=['GET'])
def admin_page():
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        abort(403)
    return render_template('admin.html')


@app.route('/api/admin/report/<int:report_id>', methods=['DELETE'])
def admin_delete_report(report_id):
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'message':'Forbidden'}), 403
    r = Report.query.get(report_id)
    if not r:
        return jsonify({'message':'Report not found'}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({'message':'Report deleted','report': r.to_dict()}), 200


@app.route('/api/admin/create', methods=['POST'])
def admin_create():
    """Dev / admin creation endpoint.

    Protection logic:
    - If ADMIN_SECRET env var is set, caller must provide that secret (in JSON `secret` or header `X-ADMIN-SECRET`).
    - If ADMIN_SECRET is not set, creation is only allowed when FLASK_ENV=development (local dev).
    """
    data = request.get_json(silent=True)
    if not data:
        data = request.form.to_dict()

    secret = data.get('secret') or request.headers.get('X-ADMIN-SECRET')
    env_secret = os.environ.get('ADMIN_SECRET')
    if env_secret:
        if not secret or secret != env_secret:
            return jsonify({'message':'Forbidden'}), 403
    else:
        if os.environ.get('FLASK_ENV') != 'development':
            return jsonify({'message':'Admin creation disabled in production; set ADMIN_SECRET to enable.'}), 403

    mobile = data.get('mobile')
    passcode = data.get('passcode') or os.environ.get('ADMIN_PASSCODE')
    name = data.get('name') or os.environ.get('ADMIN_NAME') or 'Administrator'

    if not mobile or not passcode:
        return jsonify({'message':'mobile and passcode required'}), 400

    mobile_norm = ''.join(filter(str.isdigit, mobile))
    if len(mobile_norm) != 10:
        return jsonify({'message':'Please provide a valid 10-digit Australian mobile number'}), 400

    existing = User.query.filter_by(identifier=mobile_norm).first()
    if existing:
        existing.is_admin = True
        if passcode:
            existing.password_hash = generate_password_hash(passcode)
        db.session.commit()
        return jsonify({'message':'User elevated to admin','user': existing.to_dict()}), 200

    user = User(identifier=mobile_norm, name=name, mobile=mobile_norm, is_admin=True)
    user.password_hash = generate_password_hash(passcode)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message':'Admin user created','user': user.to_dict()}), 201


# Debug: list users (development only)
@app.route('/api/users', methods=['GET'])
def list_users():
    # admin-only: return users
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'message':'Forbidden'}), 403
    users_q = User.query.all()
    return jsonify([u.to_dict() for u in users_q])


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None
        @app.route('/reports')
def reports_page():
    return render_template('loadreports.html')

