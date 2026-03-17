from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import random
from werkzeug.utils import secure_filename

# Serve static files and templates from the `Frontend` folder so your existing
# HTML, CSS and JS work without changing their paths.
app = Flask(__name__, static_folder='Frontend', static_url_path='', template_folder='Frontend')
CORS(app)

# ----------------------------
# STORAGE (replace with database later)
# ----------------------------
users = {}
codes = {}
reports = []   # store waste reports

UPLOAD_FOLDER = os.path.join(app.static_folder or 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------
# HOME PAGE
# ----------------------------
@app.route('/')
def home():
    # Render the index.html inside Frontend/ (template_folder set above)
    return render_template('index.html')


# ----------------------------
# SEND OTP CODE
# ----------------------------
@app.route('/api/send_code', methods=['POST'])
def send_code():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"message": "Mobile number required"}), 400

    mobile = data.get("mobile")

    if not mobile:
        return jsonify({"message": "Mobile number required"}), 400

    mobile = ''.join(filter(str.isdigit, mobile))

    # generate random 4 digit code
    code = str(random.randint(1000, 9999))

    codes[mobile] = code

    print(f"OTP for {mobile}: {code}")

    return jsonify({"message": "Verification code sent"}), 200


# ----------------------------
# SIGNUP
# ----------------------------
@app.route('/api/signup', methods=['POST'])
def signup():

    data = request.get_json(silent=True)

    if not data:
        data = request.form.to_dict()


    name = data.get("name")
    mobile = data.get("mobile")
    code = data.get("code")

    # Signup simplified: only name, mobile and 4-digit code required
    if not all([name, mobile, code]):
        return jsonify({"message": "Name, mobile and code are required"}), 400

    mobile = ''.join(filter(str.isdigit, mobile))

    if mobile not in codes or codes[mobile] != code:
        return jsonify({"message": "Invalid verification code"}), 400

    if mobile in users:
        return jsonify({"message": "User already exists"}), 409

    # create user; licence may be empty/added later via profile
    users[mobile] = {
        "name": name,
        "mobile": mobile,
        "licence": "",
        "address": "",
        "photo": ""
    }

    print("User created:", users[mobile])

    return jsonify({"message": "Signup successful"}), 200


# ----------------------------
# LOGIN
# ----------------------------
@app.route('/api/login', methods=['POST'])
def login():

    data = request.get_json(silent=True)

    if not data:
        data = request.form.to_dict()

    mobile = data.get("mobile")
    code = data.get("code")

    if not mobile or not code:
        return jsonify({"message": "Mobile and code required"}), 400

    mobile = ''.join(filter(str.isdigit, mobile))

    if mobile not in users:
        return jsonify({"message": "User not found"}), 404

    if codes.get(mobile) != code:
        return jsonify({"message": "Invalid code"}), 401

    return jsonify({
        "message": f"Welcome {users[mobile]['name']}!",
        "user": users[mobile]
    }), 200


# ----------------------------
# PROFILE UPDATE
# ----------------------------
@app.route('/api/profile', methods=['POST'])
def profile():

    name = request.form.get("name")
    mobile = request.form.get("mobile")
    address = request.form.get("address")

    # licence is optional now; require at least name and mobile
    if not all([name, mobile]):
        return jsonify({"message": "Missing name or mobile"}), 400

    mobile = ''.join(filter(str.isdigit, mobile))

    if mobile not in users:
        return jsonify({"message": "User not found"}), 404

    users[mobile]["name"] = name
    # update licence only if provided
    licence = request.form.get("licence")
    if licence:
        users[mobile]["licence"] = licence
    users[mobile]["address"] = address

    photo = request.files.get("photo")

    if photo:
        filename = secure_filename(photo.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(path)
        users[mobile]["photo"] = filename

    return jsonify({
        "message": "Profile saved",
        "user": users[mobile]
    }), 200


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

    return jsonify({"message": "Waste report saved"}), 200




# ----------------------------
# GET ALL REPORTS (for map)
# ----------------------------
@app.route('/api/reports', methods=['GET'])
def get_reports():
    return jsonify(reports)


# Debug: list users (development only)
@app.route('/api/users', methods=['GET'])
def list_users():
    # return users dictionary (do not enable in production)
    return jsonify(users)
