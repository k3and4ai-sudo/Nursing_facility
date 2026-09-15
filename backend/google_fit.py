import os
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from backend.config import BASE_DIR
from backend import database as db
from backend import vital_parser

# Fitness API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.read",
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read"
]

PROJECT_ROOT = os.path.dirname(BASE_DIR)
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json") if os.path.exists(os.path.join(PROJECT_ROOT, "credentials.json")) else os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json") if os.path.exists(os.path.join(PROJECT_ROOT, "token.json")) else os.path.join(BASE_DIR, "token.json")

def get_google_fit_credentials() -> Optional[Credentials]:
    """
    Loads, refreshes, or initiates OAuth 2.0 flow for Google Fit.
    Returns Credentials or None if credentials.json is missing.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[Google Fit] Error loading token.json: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
                print("[Google Fit] Token successfully refreshed.")
            except Exception as e:
                print(f"[Google Fit] Error refreshing token: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"[Google Fit] {CREDENTIALS_FILE} not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            # Run local server on an available port
            creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            print("[Google Fit] New token.json created.")

    return creds

def get_fitness_service():
    """Builds and returns the Google Fitness API service resource."""
    creds = get_google_fit_credentials()
    if not creds:
        return None
    return build("fitness", "v1", credentials=creds, cache_discovery=False)

def fetch_latest_fit_vitals(hours_back: int = 12) -> Dict[str, Any]:
    """
    Fetches the latest heart rate and SpO2 readings recorded in Google Fit within the last `hours_back` hours.
    Returns a dict with latest 'heart_rate', 'spo2', 'timestamp', and 'status'.
    """
    service = get_fitness_service()
    if not service:
        return {"status": "error", "message": "Google Fit credentials not configured"}

    now_dt = datetime.now()
    start_dt = now_dt - timedelta(hours=hours_back)
    start_ns = int(start_dt.timestamp() * 1e9)
    end_ns = int(now_dt.timestamp() * 1e9)

    result = {
        "heart_rate": None,
        "spo2": None,
        "steps": None,
        "latest_timestamp": None,
        "status": "success",
        "raw_points": []
    }

    # Aggregate request for Heart Rate and Oxygen Saturation
    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.heart_rate.bpm"},
            {"dataTypeName": "com.google.oxygen_saturation"},
            {"dataTypeName": "com.google.step_count.delta"}
        ],
        "bucketByTime": {"durationMillis": hours_back * 3600 * 1000},
        "startTimeMillis": int(start_dt.timestamp() * 1000),
        "endTimeMillis": int(now_dt.timestamp() * 1000)
    }

    try:
        res = service.users().dataset().aggregate(userId="me", body=body).execute()
        for bucket in res.get("bucket", []):
            for dataset in bucket.get("dataset", []):
                for point in dataset.get("point", []):
                    dt_name = point.get("dataTypeName", "")
                    vals = point.get("value", [])
                    end_time_ns = int(point.get("endTimeNanos", 0))
                    point_time = datetime.fromtimestamp(end_time_ns / 1e9).isoformat() if end_time_ns else now_dt.isoformat()

                    if dt_name == "com.google.heart_rate.bpm" and vals:
                        # Value contains [bpm]
                        hr = round(vals[0].get("fpVal", vals[0].get("intVal", 0)))
                        if hr > 0:
                            result["heart_rate"] = hr
                            result["latest_timestamp"] = point_time
                    elif dt_name == "com.google.oxygen_saturation" and vals:
                        # Value contains [oxygen_saturation percentage]
                        spo2 = round(vals[0].get("fpVal", vals[0].get("intVal", 0)))
                        if spo2 > 0:
                            result["spo2"] = spo2
                            result["latest_timestamp"] = point_time
                    elif dt_name == "com.google.step_count.delta" and vals:
                        steps = vals[0].get("intVal", 0)
                        result["steps"] = (result["steps"] or 0) + steps
    except Exception as e:
        print(f"[Google Fit] Aggregate query error: {e}")
        result["status"] = "error"
        result["message"] = str(e)

    # Fallback to direct DataSource listing if aggregate returns no points (some third-party apps sync directly)
    if result["heart_rate"] is None:
        try:
            # Query recent heart rate data source directly
            sources = service.users().dataSources().list(userId="me").execute().get("dataSource", [])
            for src in sources:
                if src.get("dataType", {}).get("name") == "com.google.heart_rate.bpm":
                    stream_id = src.get("dataStreamId")
                    if stream_id:
                        ds = service.users().dataSources().datasets().get(
                            userId="me",
                            dataSourceId=stream_id,
                            datasetId=f"{start_ns}-{end_ns}"
                        ).execute()
                        points = ds.get("point", [])
                        if points:
                            last_pt = points[-1]
                            v = last_pt.get("value", [{}])[0]
                            hr = round(v.get("fpVal", v.get("intVal", 0)))
                            if hr > 0:
                                result["heart_rate"] = hr
                                pt_ns = int(last_pt.get("endTimeNanos", 0))
                                result["latest_timestamp"] = datetime.fromtimestamp(pt_ns / 1e9).isoformat() if pt_ns else now_dt.isoformat()
                                break
        except Exception as e:
            print(f"[Google Fit] Direct datasource query error: {e}")

    return result

async def sync_user_google_fit(user_id: int, broadcast_callback=None) -> Dict[str, Any]:
    """
    Fetches latest data from Google Fit, saves to DB if new, and triggers staff alert if abnormal.
    """
    user = db.get_user(user_id)
    if not user:
        return {"status": "error", "message": f"User {user_id} not found"}

    fit_data = fetch_latest_fit_vitals(hours_back=6)
    if fit_data.get("status") != "success":
        return fit_data

    hr = fit_data.get("heart_rate")
    spo2 = fit_data.get("spo2")

    if hr is None and spo2 is None:
        return {"status": "no_data", "message": "Google Fitに直近6時間の心拍/SpO2データがありません"}

    # Check against thresholds
    vitals_check = {
        "heart_rate": hr,
        "spo2": spo2
    }
    is_alert, alert_reason = vital_parser.validate_vitals(vitals_check)

    # Check if latest DB record already has this exact value to avoid duplicate logging
    recent_records = db.get_vital_records(user_id, limit=1)
    if recent_records:
        latest_rec = recent_records[0]
        if latest_rec.get("heart_rate") == hr and latest_rec.get("spo2") == spo2:
            return {"status": "already_synced", "heart_rate": hr, "spo2": spo2}

    rec_id = db.add_vital_record(
        user_id=user_id,
        heart_rate=hr,
        spo2=spo2,
        source="google_fit",
        raw_text=f"Google Fit自動同期 (心拍: {hr or '-'} bpm, SpO2: {spo2 or '-'} %)",
        is_alert=1 if is_alert else 0,
        alert_reason=alert_reason
    )

    if broadcast_callback and (is_alert or True):
        alert_payload = {
            "type": "vital_alert" if is_alert else "vital_update",
            "user_id": user_id,
            "user_name": user.get("name", f"利用者ID:{user_id}"),
            "room_number": user.get("room_number", ""),
            "vitals": vitals_check,
            "source": "google_fit",
            "is_alert": is_alert,
            "reason": alert_reason,
            "timestamp": datetime.now().isoformat()
        }
        await broadcast_callback(alert_payload)

    return {
        "status": "success",
        "record_id": rec_id,
        "heart_rate": hr,
        "spo2": spo2,
        "is_alert": is_alert,
        "alert_reason": alert_reason
    }

if __name__ == "__main__":
    print("[Google Fit Module] Running authorization / test query...")
    creds = get_google_fit_credentials()
    if creds:
        print("✅ Authorization succeeded! Querying latest data...")
        data = fetch_latest_fit_vitals()
        print("Result:", json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("❌ Authorization failed or cancelled.")
