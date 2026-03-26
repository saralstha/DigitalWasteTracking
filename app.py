from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")

# Render Postgres / local fallback
database_url = os.environ.get("DATABASE_URL", "sqlite:///ewaste.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")

db = SQLAlchemy(app)
CORS(app)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ----------------------------
# DATABASE MODELS
# ----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    passcode = db.Column(db.String(10), nullable=False)
    licence = db.Column(db.String(50), default="")
    address = db.Column(db.String(255), default="")
    photo = db.Column(db.String(255), default="")
    is_admin = db.Column(db.Boolean, default=False)

class WasteReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(255), nullable=False)
    waste_type = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.String(50), nullable=False)
    lat = db.Column(db.String(50), default="")
    lon = db.Column(db.String(50), default="")
    photo = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# ----------------------------
# HELPERS
# ----------------------------
def get_current_user():
    mobile = session.get("user_mobile")
    if not mobile:
        return None
    return User.query.filter_by(mobile=mobile).first()

@app.context_processor
def inject_user():
    return {"current_user": get_current_user()}

# ----------------------------
# PAGE ROUTES
# ----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/report")
def report():
    return render_template("report.html")

@app.route("/track")
def track():
    return render_template("track.html")

@app.route("/reports")
def reports_page():
    return render_template("loadreports.html")

@app.route("/admin")
def admin_page():
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("home"))
    return render_template("admin.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ----------------------------
# AUTH API
# ----------------------------
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    mobile = "".join(filter(str.isdigit, data.get("mobile", "")))
    passcode = (data.get("passcode") or "").strip()

    if not name or not mobile or not passcode:
        return jsonify({"message": "Name, mobile and passcode are required"}), 400

    if len(mobile) != 10:
        return jsonify({"message": "Mobile number must be 10 digits"}), 400

    if not passcode.isdigit() or len(passcode) != 4:
        return jsonify({"message": "Passcode must be 4 digits"}), 400

    existing = User.query.filter_by(mobile=mobile).first()
    if existing:
        return jsonify({"message": "User already exists"}), 409

    user = User(
        name=name,
        mobile=mobile,
        passcode=passcode,
        is_admin=False
    )
    db.session.add(user)
    db.session.commit()

    session["user_mobile"] = mobile

    return jsonify({
        "message": "Signup successful",
        "user": {
            "name": user.name,
            "mobile": user.mobile,
            "licence": user.licence,
            "address": user.address,
            "photo": user.photo,
            "is_admin": user.is_admin
        }
    }), 200

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    mobile = "".join(filter(str.isdigit, data.get("mobile", "")))
    passcode = (data.get("passcode") or "").strip()

    if not mobile or not passcode:
        return jsonify({"message": "Mobile and passcode are required"}), 400

    user = User.query.filter_by(mobile=mobile).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    if user.passcode != passcode:
        return jsonify({"message": "Incorrect passcode"}), 401

    session["user_mobile"] = user.mobile

    return jsonify({
        "message": f"Welcome {user.name}",
        "user": {
            "name": user.name,
            "mobile": user.mobile,
            "licence": user.licence,
            "address": user.address,
            "photo": user.photo,
            "is_admin": user.is_admin
        }
    }), 200

@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user_mobile", None)
    return jsonify({"message": "Logged out successfully"}), 200

@app.route("/api/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 200

    return jsonify({
        "authenticated": True,
        "user": {
            "name": user.name,
            "mobile": user.mobile,
            "licence": user.licence,
            "address": user.address,
            "photo": user.photo,
            "is_admin": user.is_admin
        }
    }), 200

# ----------------------------
# PROFILE API
# ----------------------------
@app.route("/api/profile", methods=["POST"])
def profile():
    user = get_current_user()
    if not user:
        return jsonify({"message": "Please log in first"}), 401

    name = (request.form.get("name") or "").strip()
    licence = (request.form.get("licence") or "").strip()
    address = (request.form.get("address") or "").strip()

    if not name:
        return jsonify({"message": "Name is required"}), 400

    user.name = name
    user.licence = licence
    user.address = address

    photo = request.files.get("photo")
    if photo and photo.filename:
        filename = secure_filename(photo.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        photo.save(save_path)
        user.photo = filename

    db.session.commit()

    return jsonify({
        "message": "Profile saved",
        "user": {
            "name": user.name,
            "mobile": user.mobile,
            "licence": user.licence,
            "address": user.address,
            "photo": user.photo,
            "is_admin": user.is_admin
        }
    }), 200

# ----------------------------
# REPORT API
# ----------------------------
@app.route("/api/report", methods=["POST"])
def report_waste():
    location = (request.form.get("location") or "").strip()
    waste_type = (request.form.get("type") or "").strip()
    weight = (request.form.get("weight") or "").strip()
    lat = (request.form.get("lat") or "").strip()
    lon = (request.form.get("lon") or "").strip()

    if not location or not waste_type or not weight:
        return jsonify({"message": "Missing fields"}), 400

    filename = ""
    photo = request.files.get("photo")
    if photo and photo.filename:
        filename = secure_filename(photo.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        photo.save(save_path)

    report = WasteReport(
        location=location,
        waste_type=waste_type,
        weight=weight,
        lat=lat,
        lon=lon,
        photo=filename
    )
    db.session.add(report)
    db.session.commit()

    return jsonify({
        "message": "Waste report saved",
        "report": {
            "id": report.id,
            "location": report.location,
            "type": report.waste_type,
            "weight": report.weight,
            "lat": report.lat,
            "lon": report.lon,
            "photo": report.photo,
            "created_at": report.created_at.isoformat() if report.created_at else None
        }
    }), 200

@app.route("/api/reports", methods=["GET"])
def get_reports():
    all_reports = WasteReport.query.order_by(WasteReport.created_at.desc(), WasteReport.id.desc()).all()
    return jsonify([
        {
            "id": r.id,
            "location": r.location,
            "type": r.waste_type,
            "weight": r.weight,
            "lat": r.lat,
            "lon": r.lon,
            "photo": r.photo,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in all_reports
    ]), 200

# ----------------------------
# ADMIN API
# ----------------------------
@app.route("/api/admin/dashboard", methods=["GET"])
def admin_dashboard():
    user = get_current_user()
    if not user or not user.is_admin:
        return jsonify({"message": "Unauthorized"}), 403

    users = User.query.order_by(User.id.desc()).all()
    reports = WasteReport.query.order_by(WasteReport.created_at.desc(), WasteReport.id.desc()).all()

    return jsonify({
        "total_users": len(users),
        "total_reports": len(reports),
        "users": [
            {
                "name": u.name,
                "mobile": u.mobile,
                "licence": u.licence,
                "address": u.address,
                "photo": u.photo,
                "is_admin": u.is_admin
            }
            for u in users
        ],
        "reports": [
            {
                "id": r.id,
                "location": r.location,
                "type": r.waste_type,
                "weight": r.weight,
                "lat": r.lat,
                "lon": r.lon,
                "photo": r.photo,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in reports
        ]
    }), 200

# ----------------------------
# INIT DB
# ----------------------------
with app.app_context():
    db.create_all()

    admin = User.query.filter_by(mobile="0400000000").first()
    if not admin:
        admin = User(
            name="Admin",
            mobile="0400000000",
            passcode="1234",
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
