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
## Results :
![ai1](https://github.com/user-attachments/assets/74dd238a-e4fb-4a79-a763-81c0f53b5744)

![ai02](https://github.com/user-attachments/assets/303c501b-48bb-4fe1-b331-216ff2924797)

![ai3](https://github.com/user-attachments/assets/47697c02-4da6-4774-b3f6-69ae62f2144a)

![ai4](https://github.com/user-attachments/assets/9e575d21-aa2a-43d3-be66-598d74b6fe0a)

![ai05](https://github.com/user-attachments/assets/5ca8d16f-e1b2-4c0d-885d-9c2142cd7987)

<img width="1203" height="773" alt="image" src="https://github.com/user-attachments/assets/42960e95-4e87-4b43-a187-84023dfa5f93" />

<img width="896" height="419" alt="image" src="https://github.com/user-attachments/assets/f623ca76-9dcd-44dc-832d-5e0a1a7b43e6" />
