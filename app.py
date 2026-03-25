from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
CORS(app)

# ----------------------------
# CONFIG
# ----------------------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------
# TEMP STORAGE
# ----------------------------
users = {}
reports = []

# Create one demo admin account
users["0400000000"] = {
    "name": "Admin",
    "mobile": "0400000000",
    "passcode": "1234",
    "licence": "",
    "address": "",
    "photo": "",
    "is_admin": True
}

# ----------------------------
# PAGE ROUTES
# ----------------------------
@app.route("/")
def home():
    current_user = None
    mobile = session.get("user_mobile")
    if mobile and mobile in users:
        current_user = users[mobile]
    return render_template("index.html", current_user=current_user)


@app.route("/about")
def about():
    current_user = None
    mobile = session.get("user_mobile")
    if mobile and mobile in users:
        current_user = users[mobile]
    return render_template("about.html", current_user=current_user)


@app.route("/report")
def report():
    current_user = None
    mobile = session.get("user_mobile")
    if mobile and mobile in users:
        current_user = users[mobile]
    return render_template("report.html", current_user=current_user)


@app.route("/track")
def track():
    current_user = None
    mobile = session.get("user_mobile")
    if mobile and mobile in users:
        current_user = users[mobile]
    return render_template("track.html", current_user=current_user)


@app.route("/reports")
def reports_page():
    current_user = None
    mobile = session.get("user_mobile")
    if mobile and mobile in users:
        current_user = users[mobile]
    return render_template("loadreports.html", current_user=current_user)


@app.route("/admin")
def admin_page():
    mobile = session.get("user_mobile")
    if not mobile or mobile not in users or not users[mobile].get("is_admin"):
        return redirect(url_for("home"))
    return render_template("admin.html", current_user=users[mobile])


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

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

    session["user_mobile"] = mobile

    return jsonify({
        "message": "Signup successful",
        "user": {
            "name": users[mobile]["name"],
            "mobile": users[mobile]["mobile"],
            "licence": users[mobile]["licence"],
            "address": users[mobile]["address"],
            "photo": users[mobile]["photo"],
            "is_admin": users[mobile]["is_admin"]
        }
    }), 200


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    mobile = "".join(filter(str.isdigit, data.get("mobile", "")))
    passcode = (data.get("passcode") or "").strip()

    if not mobile or not passcode:
        return jsonify({"message": "Mobile and passcode are required"}), 400

    if mobile not in users:
        return jsonify({"message": "User not found"}), 404

    if users[mobile]["passcode"] != passcode:
        return jsonify({"message": "Incorrect passcode"}), 401

    session["user_mobile"] = mobile

    return jsonify({
        "message": f"Welcome {users[mobile]['name']}",
        "user": {
            "name": users[mobile]["name"],
            "mobile": users[mobile]["mobile"],
            "licence": users[mobile]["licence"],
            "address": users[mobile]["address"],
            "photo": users[mobile]["photo"],
            "is_admin": users[mobile]["is_admin"]
        }
    }), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user_mobile", None)
    return jsonify({"message": "Logged out successfully"}), 200


@app.route("/api/me", methods=["GET"])
def me():
    mobile = session.get("user_mobile")
    if not mobile or mobile not in users:
        return jsonify({"authenticated": False}), 200

    user = users[mobile]
    return jsonify({
        "authenticated": True,
        "user": {
            "name": user["name"],
            "mobile": user["mobile"],
            "licence": user["licence"],
            "address": user["address"],
            "photo": user["photo"],
            "is_admin": user["is_admin"]
        }
    }), 200

# ----------------------------
# PROFILE API
# ----------------------------
@app.route("/api/profile", methods=["POST"])
def profile():
    mobile = session.get("user_mobile")
    if not mobile or mobile not in users:
        return jsonify({"message": "Please log in first"}), 401

    name = (request.form.get("name") or "").strip()
    licence = (request.form.get("licence") or "").strip()
    address = (request.form.get("address") or "").strip()

    if not name:
        return jsonify({"message": "Name is required"}), 400

    users[mobile]["name"] = name
    users[mobile]["licence"] = licence
    users[mobile]["address"] = address

    photo = request.files.get("photo")
    if photo and photo.filename:
        filename = secure_filename(photo.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(save_path)
        users[mobile]["photo"] = filename

    return jsonify({
        "message": "Profile saved",
        "user": {
            "name": users[mobile]["name"],
            "mobile": users[mobile]["mobile"],
            "licence": users[mobile]["licence"],
            "address": users[mobile]["address"],
            "photo": users[mobile]["photo"],
            "is_admin": users[mobile]["is_admin"]
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

    photo = request.files.get("photo")
    filename = ""

    if photo and photo.filename:
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

    return jsonify({
        "message": "Waste report saved",
        "report": report
    }), 200


@app.route("/api/reports", methods=["GET"])
def get_reports():
    return jsonify(reports), 200

# ----------------------------
# ADMIN API
# ----------------------------
@app.route("/api/admin/dashboard", methods=["GET"])
def admin_dashboard():
    mobile = session.get("user_mobile")
    if not mobile or mobile not in users or not users[mobile].get("is_admin"):
        return jsonify({"message": "Unauthorized"}), 403

    return jsonify({
        "total_users": len(users),
        "total_reports": len(reports),
        "users": [
            {
                "name": u["name"],
                "mobile": u["mobile"],
                "licence": u["licence"],
                "address": u["address"],
                "photo": u["photo"],
                "is_admin": u["is_admin"]
            }
            for u in users.values()
        ],
        "reports": reports
    }), 200

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
