# AI Clinic Scheduler (Streamlit)

A self-contained example app that books appointments, writes to Excel/CSV safely, and sends optional email/SMS reminders. 
No Calendly API token required; uses your public booking links from `.env`.

## Quickstart

```bash
pip install -r requirements.txt
copy .env.example .env  # (Windows) or: cp .env.example .env
# Edit .env to set email/Twilio and URLs
streamlit run app.py
```

- First run creates valid **appointments.xlsx**, **patients.csv**, and **doctor_schedules_14days.xlsx** automatically.
- If email/Twilio credentials are not set, the app still works (it just skips sending).

## Files

- `app.py` – Streamlit app
- `requirements.txt` – pinned dependencies tested on Python 3.10
- `.env.example` – copy to `.env` and fill
- `.streamlit/config.toml` – dev-friendly defaults
- `patients.csv` – starts empty with headers
- `doctor_schedules_14days.xlsx` – pre-filled sample availability (D001, D002)
- `appointments.xlsx` – starts empty with headers
- `New Patient Intake Form.pdf` – tiny placeholder

## Notes

- If you previously created a zero-byte or corrupted `appointments.xlsx`, delete it and run the app again—this project always writes a valid workbook.
- Change `REMINDER_MODE` in `.env` to `prod` to schedule reminders 24h/6h/1h before the appointment.
