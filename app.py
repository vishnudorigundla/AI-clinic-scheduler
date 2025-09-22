
import os
import re
import pandas as pd
import streamlit as st
from typing import Dict, Any
from datetime import datetime, date, time as dtime, timedelta
from email.message import EmailMessage
import smtplib
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client
from dotenv import load_dotenv

# ==================== Boot ====================
load_dotenv()

# ---- ENV ----
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").strip()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

CALENDLY_NEW = os.getenv("CALENDLY_NEW", "https://calendly.com/vishnudorigundla453/new-meeting").strip()
CALENDLY_RETURNING = os.getenv("CALENDLY_RETURNING", "https://calendly.com/vishnudorigundla453/returning-patient").strip()

APPOINTMENTS_FILE = os.getenv("APPOINTMENTS_FILE", "appointments.xlsx")
PATIENTS_FILE = os.getenv("PATIENTS_FILE", "patients.csv")
SCHEDULE_FILE = os.getenv("SCHEDULE_FILE", "doctor_schedules_14days.xlsx")
PDF_FORM = os.getenv("INTAKE_FORM", "New Patient Intake Form.pdf")

REMINDER_MODE = os.getenv("REMINDER_MODE", "demo").lower()  # demo or prod

# ---- Paths relative to script ----
def _abs(p):
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, p)

APPOINTMENTS_FILE = _abs(APPOINTMENTS_FILE)
PATIENTS_FILE = _abs(PATIENTS_FILE)
SCHEDULE_FILE = _abs(SCHEDULE_FILE)
PDF_FORM = _abs(PDF_FORM)

# ==================== Init Safe Files ====================
def init_patients_file():
    if not os.path.exists(PATIENTS_FILE) or os.path.getsize(PATIENTS_FILE) == 0:
        df = pd.DataFrame(columns=["patient_id","first_name","last_name","dob","email","phone"])
        df.to_csv(PATIENTS_FILE, index=False)

def init_schedules_file():
    if not os.path.exists(SCHEDULE_FILE) or os.path.getsize(SCHEDULE_FILE) == 0:
        # create a schedules sheet with some slots
        rows = []
        today = date.today()
        for d in range(14):
            day = today + timedelta(days=d)
            for doctor_id, start_hours in [("D001",[9,10,11,14,15]), ("D002",[10,11,12,16])]:
                for hr in start_hours:
                    rows.append({
                        "doctor_id": doctor_id,
                        "date": day.strftime("%Y-%m-%d"),
                        "start_time": f"{hr:02d}:00",
                        "is_available": True
                    })
        df = pd.DataFrame(rows, columns=["doctor_id","date","start_time","is_available"])
        with pd.ExcelWriter(SCHEDULE_FILE, engine="openpyxl", mode="w") as xw:
            df.to_excel(xw, sheet_name="schedules", index=False)

def init_appointments_file():
    # create valid empty workbook with headers to avoid BadZipFile
    headers = ["patient_name","dob","doctor_id","date","start_time","is_new_patient","insurance_carrier","member_id","group_number","patient_phone","patient_email","created_at"]
    need_create = (not os.path.exists(APPOINTMENTS_FILE)) or os.path.getsize(APPOINTMENTS_FILE) == 0
    if not need_create:
        # also handle corrupted files
        try:
            _ = pd.read_excel(APPOINTMENTS_FILE)
            return
        except Exception:
            need_create = True
    if need_create:
        df = pd.DataFrame(columns=headers)
        with pd.ExcelWriter(APPOINTMENTS_FILE, engine="openpyxl", mode="w") as xw:
            df.to_excel(xw, index=False)

def ensure_pdf_form():
    if not os.path.exists(PDF_FORM) or os.path.getsize(PDF_FORM) == 0:
        # Write a tiny valid PDF (one-page placeholder)
        pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R>>endobj\n4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 72 100 Td (New Patient Intake Form Placeholder) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000104 00000 n \n0000000192 00000 n \ntrailer<</Root 1 0 R/Size 5>>\nstartxref\n280\n%%EOF\n"
        with open(PDF_FORM, "wb") as f:
            f.write(pdf_bytes)

def safe_load_schedules():
    if os.path.exists(SCHEDULE_FILE):
        try:
            return pd.read_excel(SCHEDULE_FILE, sheet_name="schedules", dtype={"doctor_id":str,"date":str,"start_time":str,"is_available":object})
        except Exception:
            try:
                return pd.read_excel(SCHEDULE_FILE, dtype=str)
            except Exception:
                return pd.DataFrame(columns=["doctor_id","date","start_time","is_available"])
    return pd.DataFrame(columns=["doctor_id","date","start_time","is_available"])

def safe_load_patients():
    if os.path.exists(PATIENTS_FILE):
        try:
            return pd.read_csv(PATIENTS_FILE, dtype=str)
        except Exception:
            init_patients_file()
            return pd.read_csv(PATIENTS_FILE, dtype=str)
    return pd.DataFrame(columns=["patient_id","first_name","last_name","dob","email","phone"])

def append_appointment_row(row: Dict[str, Any]):
    init_appointments_file()
    try:
        existing = pd.read_excel(APPOINTMENTS_FILE)
    except Exception:
        init_appointments_file()
        existing = pd.read_excel(APPOINTMENTS_FILE)
    newdf = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    with pd.ExcelWriter(APPOINTMENTS_FILE, engine="openpyxl", mode="w") as xw:
        newdf.to_excel(xw, index=False)

# Run initializers
init_patients_file()
init_schedules_file()
init_appointments_file()
ensure_pdf_form()

patients_df = safe_load_patients()
schedules_df = safe_load_schedules()

# ==================== Notifications ====================
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        print("Twilio init error:", e)

def send_email(to_email: str, subject: str, body: str, attach_pdf: str = None) -> str:
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        return "Email credentials not configured."
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if attach_pdf and os.path.exists(attach_pdf):
        try:
            with open(attach_pdf, "rb") as f:
                msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(attach_pdf))
        except Exception as e:
            return f"Email attachment error: {e}"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        return "Email sent"
    except Exception as e:
        return f"Email error: {e}"

def send_sms(to_number: str, body: str) -> str:
    if not twilio_client:
        return "Twilio not configured"
    try:
        msg = twilio_client.messages.create(body=body, from_=TWILIO_PHONE_NUMBER, to=to_number)
        return f"SMS sent ({msg.sid})"
    except Exception as e:
        return f"SMS error: {e}"

# ==================== Core helpers ====================
def lookup_patient(name: str, dob_str: str):
    if patients_df.empty or not name or not dob_str:
        return None
    first = name.split()[0].strip().lower()
    found = patients_df[
        patients_df["first_name"].astype(str).str.lower().eq(first) &
        patients_df["dob"].astype(str).eq(dob_str)
    ]
    return None if found.empty else found.iloc[0].to_dict()

def find_slot(doctor_id: str, date_str: str):
    if schedules_df.empty:
        return {"start_time": "10:00"}
    slot = schedules_df[
        (schedules_df["doctor_id"].astype(str) == str(doctor_id)) &
        (schedules_df["date"].astype(str) == str(date_str)) &
        (schedules_df["is_available"].astype(str).str.lower().isin(["true", "1", "yes"]))
    ]
    return None if slot.empty else slot.iloc[0].to_dict()

def compute_reminder_times(appt_date_str: str, slot_time_str: str):
    now = datetime.now()
    if REMINDER_MODE == "prod":
        try:
            appt_date = datetime.strptime(appt_date_str, "%Y-%m-%d").date()
        except Exception:
            appt_date = date.today()
        try:
            hh, mm = slot_time_str.split(":")
            appt_time = dtime(int(hh), int(mm))
        except Exception:
            appt_time = dtime(10, 0)
        appt_dt = datetime.combine(appt_date, appt_time)
        run1 = appt_dt - timedelta(hours=24)
        run2 = appt_dt - timedelta(hours=6)
        run3 = appt_dt - timedelta(hours=1)
        # ensure future
        run1 = run1 if run1 > now else now + timedelta(seconds=10)
        run2 = run2 if run2 > now else now + timedelta(seconds=20)
        run3 = run3 if run3 > now else now + timedelta(seconds=30)
        return run1, run2, run3
    else:
        # demo: send in short intervals
        return now + timedelta(seconds=15), now + timedelta(seconds=30), now + timedelta(seconds=45)

scheduler = BackgroundScheduler()
scheduler.start()

def schedule_reminders(patient_email, patient_name, doctor_id, date_str, slot_time_str, patient_phone=None):
    run1, run2, run3 = compute_reminder_times(date_str, slot_time_str)
    scheduler.add_job(send_email, 'date', run_date=run1,
                      args=[patient_email, f"Reminder: {patient_name}", f"Hello {patient_name}, reminder for {date_str} at {slot_time_str}"])
    scheduler.add_job(send_email, 'date', run_date=run2,
                      args=[patient_email, f"Reminder: Intake form - {patient_name}", f"Hello {patient_name}, please complete the attached intake form."], kwargs={"attach_pdf": PDF_FORM})
    scheduler.add_job(send_email, 'date', run_date=run3,
                      args=[patient_email, f"Reminder: Confirm/cancel - {patient_name}", f"Hello {patient_name}, please confirm or cancel your visit."])
    if patient_phone and twilio_client:
        scheduler.add_job(send_sms, 'date', run_date=run1, args=[patient_phone, f"Reminder: Appointment on {date_str} at {slot_time_str}"])
        scheduler.add_job(send_sms, 'date', run_date=run2, args=[patient_phone, "Have you filled the intake form?"])
        scheduler.add_job(send_sms, 'date', run_date=run3, args=[patient_phone, "Please confirm/cancel your appointment."])

# ==================== UI ====================
st.set_page_config(page_title="AI Clinic Scheduler", layout="centered")
st.title("🏥 AI Clinic Scheduler")
st.caption("Calendly token not required. Uses direct links from .env (CALENDLY_NEW, CALENDLY_RETURNING).")

with st.expander("ℹ️ Setup status & file locations", expanded=False):
    st.write(f"Appointments file: `{APPOINTMENTS_FILE}`")
    st.write(f"Patients file: `{PATIENTS_FILE}`")
    st.write(f"Schedules file: `{SCHEDULE_FILE}`")
    st.write(f"Intake PDF: `{PDF_FORM}`")

st.markdown("Fill the form. Booking will be created and you'll see a confirmation message. (Emails/SMS only send if credentials are configured.)")

with st.form("booking_form", clear_on_submit=True):
    patient_name = st.text_input("Patient Name")
    dob_date = st.date_input("Date of Birth", min_value=date(1900,1,1), max_value=date.today())
    doctor_id = st.text_input("Doctor ID", value="D001")
    appointment_date = st.date_input("Appointment Date", min_value=date.today())
    patient_email = st.text_input("Email")
    patient_phone = st.text_input("Phone (E.164, e.g. +15551234567)")
    insurance_carrier = st.text_input("Insurance (optional)")
    member_id = st.text_input("Member ID (optional)")
    group_number = st.text_input("Group Number (optional)")
    submitted = st.form_submit_button("📅 Book Appointment")

if submitted:
    # 1) simple validation
    errors = []
    if not patient_name.strip():
        errors.append("Name is required.")
    if not doctor_id.strip():
        errors.append("Doctor ID is required.")
    if errors:
        st.error(" ; ".join(errors))
        st.stop()

    # 2) slot recommend
    is_new = lookup_patient(patient_name, dob_date.strftime("%Y-%m-%d")) is None
    slot = find_slot(doctor_id.strip(), appointment_date.strftime("%Y-%m-%d"))
    if not slot:
        st.error("No slot available for this doctor/date.")
        st.stop()

    # 3) save appointment
    appt_row = {
        "patient_name": patient_name.strip(),
        "dob": dob_date.strftime("%Y-%m-%d"),
        "doctor_id": doctor_id.strip(),
        "date": appointment_date.strftime("%Y-%m-%d"),
        "start_time": slot.get("start_time", "10:00"),
        "is_new_patient": bool(is_new),
        "insurance_carrier": insurance_carrier.strip() or None,
        "member_id": member_id.strip() or None,
        "group_number": group_number.strip() or None,
        "patient_phone": patient_phone.strip() or None,
        "patient_email": patient_email.strip() or None,
        "created_at": datetime.now().isoformat(timespec="seconds")
    }
    try:
        append_appointment_row(appt_row)
    except Exception as e:
        st.error(f"Failed saving appointment: {e}")
        st.stop()

    # 4) notifications (optional)
    booking_link = CALENDLY_NEW if is_new else CALENDLY_RETURNING
    email_status = "No email provided"
    sms_status = "No phone provided"
    if patient_email.strip():
        email_status = send_email(
            patient_email.strip(),
            "Appointment Confirmation",
            f"Hello {patient_name},\nYour appointment is confirmed.\nDoctor: {doctor_id}\nDate: {appt_row['date']}\nTime: {appt_row['start_time']}\nBooking link: {booking_link}\nPlease find attached the intake form.",
            attach_pdf=PDF_FORM
        )
    if patient_phone.strip():
        sms_status = send_sms(patient_phone.strip(), f"Appointment confirmed: {appt_row['date']} {appt_row['start_time']}. Link: {booking_link}")

    # 5) reminders
    if patient_email.strip() or patient_phone.strip():
        schedule_reminders(patient_email.strip(), patient_name, doctor_id, appt_row["date"], appt_row["start_time"], patient_phone.strip() or None)

    st.success(f"Booking created ✅ Email: {email_status}. SMS: {sms_status}.")
    st.markdown(f"📅 **Booking link:** [{booking_link}]({booking_link})")

with st.expander("📄 Preview current appointments", expanded=False):
    try:
        st.dataframe(pd.read_excel(APPOINTMENTS_FILE))
    except Exception as e:
        st.warning(f"Could not read appointments file yet: {e}")