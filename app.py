from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import pytesseract
from fuzzywuzzy import fuzz 

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract" 

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["hospital_db"]
patients_collection = db["patients"]
doctors_collection = db["doctors"]
UPLOAD_FOLDER = os.path.join("static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# Home Page
@app.route("/")
def home():
    return render_template("firstpage.html")

# Doctor Signup
@app.route("/signup1", methods=["GET", "POST"])
def signup1():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if doctors_collection.find_one({"username": username}):
            flash("Username already exists!", "error")
            return render_template("signup1.html")
        doctors_collection.insert_one({"username": username, "password": password})
        session["doctor"] = username
        flash("Doctor registered successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("signup1.html")

# Doctor Login
@app.route("/doctor", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        doctor = doctors_collection.find_one({"username": username, "password": password})
        if doctor:
            session["doctor"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html")

# Doctor Dashboard
@app.route("/dashboard",methods=["GET", "POST"])
def dashboard():
    if "doctor" not in session:
        flash("Please login to access the dashboard", "error")
        return redirect(url_for("doctor_login"))

    # Fetch data from MongoDB
    total_patients = patients_collection.count_documents({})
    total_reports = db["reports"].count_documents({})
    
    today = datetime.today().strftime("%Y-%m-%d")
    today_appointments = db["appointments"].count_documents({"date": today})

    recent_reports = list(db["reports"].find().sort("date", -1).limit(3))
    upcoming_appointments = list(db["appointments"].find({"date": today}).sort("time", 1))

    return render_template("Doc_dashboard.html",
        total_patients=total_patients,
        total_reports=total_reports,
        today_appointments=today_appointments,
        recent_reports=recent_reports,
        upcoming_appointments=upcoming_appointments
    )


@app.route("/signup2", methods=["GET", "POST"])
def signup2():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if patients_collection.find_one({"username": username}):
            flash("Username already exists!", "error")
            return render_template("signup2.html")
        patients_collection.insert_one({"username": username, "password": password})
        session["patient"] = username
        flash("Patient registered successfully!", "success")
        return redirect(url_for("patient_dashboard"))
    return render_template("signup2.html")
  


# Patient Login
@app.route("/patient", methods=["GET", "POST"])
def patient_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        patient = patients_collection.find_one({"username": username, "password": password})
        if patient:
            session["patient"] = username
            return redirect(url_for("patient_dashboard"))
        else:
            flash("Invalid patient username or password", "error")
    return render_template("patient_login.html")

@app.route("/patient_dashboard", methods=["GET", "POST"])
def patient_dashboard():
    if "patient" not in session:
        flash("Please login to access the dashboard", "error")
        return redirect(url_for("patient_login"))

    username = session["patient"]

    # Fetch upcoming appointments for this user
    upcoming_appointments = list(db.appointments.find(
        {"username": username, "date": {"$gte": datetime.today().strftime("%Y-%m-%d")}}
    ).sort("date", 1))

    # Get prescriptions for this user
    prescriptions = list(db.prescriptions.find({"username": username}).sort("date", -1))

    # Get lab reports for this user
    reports = list(db.reports.find({"username": username}).sort("date", -1))

    return render_template("Patient_dashboard.html",
        name=username,
        upcoming_appointments=upcoming_appointments,
        prescriptions=prescriptions,
        reports=reports
    )

    
    
@app.route("/patient_db")
def patient_db():
    name = request.args.get("name", "Patient")
    return render_template("Patient_db.html", name=name)

@app.route("/appointments")
def patient_appointments():
    if "patient" not in session:
        return redirect(url_for("patient_login"))

    username = session["patient"]

    # Fetch all appointments for this user
    appointments = list(db.appointments.find({"username": username}))

    return render_template("Patient_appointments.html", appointments=appointments)

@app.route('/book-appointment', methods=['GET', 'POST'])
def book_appointment():
    if "patient" not in session:
        return redirect(url_for("patient_login"))
        
    username = session["patient"]
    
    # 🔹 Fetch all doctor usernames from the "doctors" collection
    doctors = list(db.doctors.find({}, {"_id": 0, "username": 1}))
    doctor_usernames = [doc["username"] for doc in doctors]

    if request.method == 'POST':
        new_appt = {
            "username": username,           
            "patient": request.form['patient_name'],
            "doctor": request.form['doctor'],
            "department": request.form['department'],
            "date": request.form['date'],
            "time": request.form['time'],
            "status": "Pending"
        }
        db.appointments.insert_one(new_appt)
        flash("Appointment booked successfully!", "success")
        return redirect(url_for('patient_appointments'))
    
    # 🔸 Pass the doctor usernames to the template
    return render_template('Patient_bookappointments.html', doctor_usernames=doctor_usernames)


@app.route("/prescriptions")
def patient_prescriptions():
    if "patient" not in session:
        flash("Please log in to view prescriptions.", "error")
        return redirect(url_for("patient_login"))

    username = session["patient"]
    print("Fetching prescriptions for:", username)  # debug

    prescriptions = list(db.prescriptions.find({"username": username}).sort("date", -1))

    print("Found prescriptions:", prescriptions)  # debug

    return render_template("Patient_prescriptions.html", prescriptions=prescriptions)
    
def preprocess_image(filepath):
    img = Image.open(filepath).convert("L")  # Grayscale conversion
    max_size = (800, 800)  # Resize smaller to save memory
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    img.save(filepath, optimize=True, quality=85)

def has_watermark(filepath, expected_text="Verified by Doctor"):
    try:
        preprocess_image(filepath)
        text = pytesseract.image_to_string(Image.open(filepath))
        print("🔍 OCR TEXT EXTRACTED:", repr(text))  # Use repr to see hidden characters

        match_score = fuzz.partial_ratio(expected_text.lower(), text.lower())
        print("🔢 Match score:", match_score)

        return match_score > 80, text.strip(), match_score
    except Exception as e:
        print("OCR error:", e)
        return False, "", 0


@app.route("/lab_reports", methods=["GET", "POST"])
def patient_lab_reports():
    if "patient" not in session:
        flash("Please log in to view lab reports", "error")
        return redirect(url_for("patient_login"))

    verification_result = None
    if request.method == "POST":
        file = request.files.get("verify_file")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            ok, ocr_text, match_score = has_watermark(save_path)
            verification_result = {
                "filename": filename,
                "is_verified": ok,
                "ocr_text": ocr_text,
                "match_score": match_score
            }
        else:
            flash("Please upload a valid image file to verify.", "error")

    reports = list(db.reports.find({"patient": session["patient"]}).sort("date", -1))
    return render_template(
        "Patient_lab_reports.html",
        reports=reports,
        verification_result=verification_result
    )

@app.route("/messages", methods=["GET", "POST"])
def patient_messages():
    if "patient" not in session:
        flash("Please login to view messages", "error")
        return redirect(url_for("patient_login"))

    username = session["patient"]

    # Handle sending a message
    if request.method == "POST":
        message_text = request.form.get("message")
        to_user = request.form.get("to_user")  # doctor's username

        if message_text and to_user:
            db.messages.insert_one({
                "from": username,
                "to": to_user,
                "message": message_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "sender_type": "patient"
            })
            flash("Message sent!", "success")

    # Show all messages sent to or received from any doctor
    messages = list(db.messages.find({
        "$or": [
            {"from": username},
            {"to": username}
        ]
    }).sort("timestamp", -1))

    # Get list of all doctors for dropdown
    all_doctors = doctors_collection.find({}, {"username": 1, "_id": 0})
    doctor_usernames = [doc["username"] for doc in all_doctors]

    return render_template("Patient_messages.html", messages=messages, doctors=doctor_usernames)


@app.route("/settings", methods=["GET", "POST"])
def patient_settings():
    if "patient" not in session:
        flash("Please log in to access settings", "error")
        return redirect(url_for("patient_login"))

    username = session["patient"]
    patient = patients_collection.find_one({"username": username})

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")

        # Verify current password
        if patient and patient["password"] == current_password:
            patients_collection.update_one(
                {"username": username},
                {"$set": {"password": new_password}}
            )
            flash("Password updated successfully!", "success")
        else:
            flash("Current password is incorrect.", "error")

    return render_template("Patient_settings.html")


@app.route("/logout")
def logout():
  
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))  



@app.route("/doc_patients")
def doc_patients():
    # Fetch all patients from MongoDB
    patients_cursor = patients_collection.find()

    # Convert MongoDB cursor to list of dicts
    patients = []
    for p in patients_cursor:
        patients.append({
            "name": p.get("name", p.get("username", "N/A")),
            "age": p.get("age", "N/A"),
            "gender": p.get("gender", "N/A"),
            "last_visit": p.get("last_visit", "N/A")
        })

    return render_template("Doc_patients.html", patients=patients)

def add_watermark_to_image(input_path, output_path, watermark_text="Verified by Doctor"):
    try:
        base = Image.open(input_path).convert("RGBA")

        # Create transparent layer for watermark
        watermark_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)

        # Font size relative to image size
        font_size = int(min(base.size) / 20)

        # ✅ Try loading a font file, fallback to default
        try:
            font_path = os.path.join("static", "fonts", "Arial.ttf")  # only used if available
            font = ImageFont.truetype(font_path, font_size)
        except Exception as font_error:
            print("⚠️ Font not found, using default:", font_error)
            font = ImageFont.load_default()

        # Get text size and position
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = base.width - text_width - 20
        y = base.height - text_height - 20

        # Draw maroon text
        maroon = (128, 0, 0, 180)  # semi-transparent maroon
        draw.text((x, y), watermark_text, font=font, fill=maroon)

        # Combine layers and save
        watermarked = Image.alpha_composite(base, watermark_layer).convert("RGB")
        watermarked.save(output_path)

        print("✅ Watermark added successfully")

    except Exception as e:
        print("❌ Watermarking error:", e)
        raise e

@app.route("/doc_reports", methods=["GET", "POST"])
def doc_reports():
    if "doctor" not in session:
        flash("Please log in to view reports.", "error")
        return redirect(url_for("doctor_login"))

    if request.method == "POST":
        patient = request.form.get("patient").strip()
        report_type = request.form.get("report_type").strip()
        medicine = request.form.get("medicine").strip()
        dosage = request.form.get("dosage").strip()
        duration = request.form.get("duration").strip()
        file = request.files.get("report_file")

        report_link = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # Apply watermark
            try:
                add_watermark_to_image(filepath, filepath, watermark_text="Verified by Doctor")
            except Exception as e:
                flash(f"Failed to add watermark: {e}", "error")
                return redirect(url_for("doc_reports"))

            report_link = filename
        else:
            flash("Invalid or missing report file.", "error")
            return redirect(url_for("doc_reports"))

        # Insert into reports collection
        db.reports.insert_one({
            "patient": patient,
            "report_type": report_type,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "report_link": report_link,
            "medicine": medicine,
            "dosage": dosage,
            "duration": duration,
            "doctor": session.get("doctor")
        })

        # ALSO insert prescription into a separate collection for patients to query easily
        db.prescriptions.insert_one({
            "username": patient,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "medicine": medicine,
            "dosage": dosage,
            "duration": duration,
            "doctor": session.get("doctor")
        })

        flash("Report and prescription submitted successfully!", "success")
        return redirect(url_for("doc_reports"))

    reports = list(db.reports.find().sort("date", -1))
    return render_template("Doc_reports.html", reports=reports)

@app.route("/doc_appointments")
def doc_appointments():
    doctor_username = session.get('doctor')
    if not doctor_username:
        return redirect(url_for('doctor_login'))  # or your login route

    appointments = list(db.appointments.find({"doctor": doctor_username}))

    for appt in appointments:
        appt["_id"] = str(appt["_id"])

    return render_template("doc_appointments.html", appointments=appointments)

@app.route('/doc_messages', methods=["GET", "POST"])
def doc_messages():
    if "doctor" not in session:
        flash("Please login to access messages", "error")
        return redirect(url_for("doctor_login"))

    doctor_username = session["doctor"]

    try:
        # Always define messages first, in case POST fails
        messages = list(db.messages.find({
            "$or": [{"from": doctor_username}, {"to": doctor_username}]
        }).sort("timestamp", -1))

        if request.method == "POST":
            message_text = request.form.get("message")
            to_user = request.form.get("to_user")

            if message_text and to_user:
                db.messages.insert_one({
                    "from": doctor_username,
                    "to": to_user,
                    "message": message_text,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                    "sender_type": "doctor"
                })
                flash("Message sent!", "success")
                return redirect(url_for("doc_messages"))

        # Get all patient usernames
        all_patients = patients_collection.find({}, {"username": 1, "_id": 0})
        

        patient_usernames = []

        for pat in all_patients:
            print(pat)  # 🟡 Debug: print each document
            if "username" in pat:
                patient_usernames.append(pat["username"])
            elif "email" in pat:
                patient_usernames.append(pat["email"])

        return render_template('doc_messages.html', messages=messages, patients=patient_usernames)

    except Exception as e:
        print("🔥 ERROR in /doc_messages:", e)
        return "Internal server error occurred.", 500

    
@app.route('/doc_settings', methods=['GET', 'POST'])
def doc_settings():
    if "doctor" not in session:
        flash("Please login to access settings", "error")
        return redirect(url_for("doctor_login"))

    username = session["doctor"]
    doctor = doctors_collection.find_one({"username": username})

    if request.method == "POST":
        prev_password = request.form.get("prev_password")
        new_password = request.form.get("new_password")

        if not prev_password or not new_password:
            flash("Please fill out all fields", "error")
            return redirect(url_for('doc_settings'))

        if not doctor:
            flash("User not found", "error")
            return redirect(url_for('doc_settings'))

        # Check if previous password matches
        if doctor["password"] != prev_password:
            flash("Previous password is incorrect", "error")
            return redirect(url_for('doc_settings'))

        # Update password in MongoDB
        doctors_collection.update_one(
            {"username": username},
            {"$set": {"password": new_password}}
        )

        flash("Password updated successfully", "success")
        return redirect(url_for('doc_settings'))

    # GET request
    return render_template("doc_settings.html")


@app.route('/doc_logout')
def doc_logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('home'))


@app.route("/tesseract-check")
def check_tesseract():
    import subprocess
    try:
        output = subprocess.check_output(["tesseract", "--version"]).decode()
        return f"<h3>✅ Tesseract is installed</h3><pre>{output}</pre>"
    except Exception as e:
        return f"<h3>❌ Tesseract not working</h3><pre>{str(e)}</pre>"


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=False)
