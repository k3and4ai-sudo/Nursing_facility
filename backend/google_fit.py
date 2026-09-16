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
    Fetches the latest heart rate, SpO2 readings, and today's total steps recorded in Google Fit.
    Returns a dict with latest 'heart_rate', 'spo2', 'steps', 'latest_timestamp', and 'status'.
    """
    service = get_fitness_service()
    if not service:
        return {"status": "error", "message": "Google Fit credentials not configured"}

    now_dt = datetime.now()
    start_dt = now_dt - timedelta(hours=hours_back)
    start_today_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    start_ns = int(start_dt.timestamp() * 1e9)
    end_ns = int(now_dt.timestamp() * 1e9)

    result = {
        "heart_rate": None,
        "spo2": None,
        "steps": 0,
        "latest_timestamp": None,
        "status": "success",
        "raw_points": []
    }

    # 1. Query today's steps from 00:00:00 to now
    try:
        step_body = {
            "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
            "bucketByTime": {"durationMillis": int((now_dt.timestamp() - start_today_dt.timestamp()) * 1000) or 3600000},
            "startTimeMillis": int(start_today_dt.timestamp() * 1000),
            "endTimeMillis": int(now_dt.timestamp() * 1000)
        }
        res_steps = service.users().dataset().aggregate(userId="me", body=step_body).execute()
        today_steps = 0
        for bucket in res_steps.get("bucket", []):
            for dataset in bucket.get("dataset", []):
                for point in dataset.get("point", []):
                    vals = point.get("value", [])
                    if vals:
                        today_steps += vals[0].get("intVal", 0)
        result["steps"] = today_steps
    except Exception as e:
        print(f"[Google Fit] Error querying today's steps: {e}")

    # 2. Query latest Heart Rate & SpO2 in the last `hours_back` hours
    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.heart_rate.bpm"},
            {"dataTypeName": "com.google.oxygen_saturation"}
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

                    if "heart_rate" in dt_name and vals:
                        hr = round(vals[0].get("fpVal", vals[0].get("intVal", 0)))
                        if hr > 0:
                            result["heart_rate"] = hr
                            result["latest_timestamp"] = point_time
                    elif "oxygen_saturation" in dt_name and vals:
                        spo2 = round(vals[0].get("fpVal", vals[0].get("intVal", 0)))
                        if spo2 > 0:
                            result["spo2"] = spo2
                            result["latest_timestamp"] = point_time
    except Exception as e:
        print(f"[Google Fit] Aggregate query error: {e}")
        result["status"] = "error"
        result["message"] = str(e)

    # Fallback to direct DataSource listing if aggregate returns no heart rate
    if result["heart_rate"] is None:
        try:
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

def fetch_fit_hourly_trends(hours_back: int = 24) -> Dict[str, Any]:
    """
    Fetches 1-hour bucket trends for steps and heart rate for chart visualization.
    """
    service = get_fitness_service()
    if not service:
        return {"status": "error", "message": "Google Fit credentials not configured"}

    now_dt = datetime.now()
    start_dt = now_dt - timedelta(hours=hours_back)

    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.heart_rate.bpm"},
            {"dataTypeName": "com.google.step_count.delta"}
        ],
        "bucketByTime": {"durationMillis": 3600 * 1000},
        "startTimeMillis": int(start_dt.timestamp() * 1000),
        "endTimeMillis": int(now_dt.timestamp() * 1000)
    }

    labels = []
    steps_data = []
    hr_data = []

    try:
        res = service.users().dataset().aggregate(userId="me", body=body).execute()
        for bucket in res.get("bucket", []):
            st_ms = int(bucket.get("startTimeMillis", 0))
            dt = datetime.fromtimestamp(st_ms / 1000)
            label = dt.strftime("%H:00")
            labels.append(label)

            b_steps = 0
            b_hr = None

            for dataset in bucket.get("dataset", []):
                for point in dataset.get("point", []):
                    dt_name = point.get("dataTypeName", "")
                    vals = point.get("value", [])
                    if "step_count" in dt_name and vals:
                        b_steps += vals[0].get("intVal", 0)
                    elif "heart_rate" in dt_name and vals:
                        v = vals[0].get("fpVal", vals[0].get("intVal", 0))
                        if v > 0:
                            b_hr = round(v)

            steps_data.append(b_steps)
            hr_data.append(b_hr)

        return {
            "status": "success",
            "labels": labels,
            "steps": steps_data,
            "heart_rates": hr_data,
            "total_steps": sum(steps_data),
            "synced_at": now_dt.isoformat()
        }
    except Exception as e:
        print(f"[Google Fit] Error fetching hourly trends: {e}")
        return {"status": "error", "message": str(e)}

def get_today_activity_summary(user_id: int) -> Dict[str, Any]:
    """
    Generates a structured daily activity and clinical summary suitable for medical records (カルテ) and handover.
    """
    user = db.get_user(user_id)
    fit_vitals = fetch_latest_fit_vitals(hours_back=24)
    trends = fetch_fit_hourly_trends(hours_back=24)

    steps = fit_vitals.get("steps", 0)
    hr = fit_vitals.get("heart_rate")
    spo2 = fit_vitals.get("spo2")

    # Evaluate activity level
    if steps >= 5000:
        activity_status = "非常に活発"
        activity_comment = f"本日累計 {steps:,} 歩。積極的な歩行運動・自立移動が継続されています。"
    elif steps >= 2000:
        activity_status = "適度な活動"
        activity_comment = f"本日累計 {steps:,} 歩。施設内の移動・リハビリ活動が適度に確認されています。"
    elif steps > 0:
        activity_status = "軽度の移動"
        activity_comment = f"本日累計 {steps:,} 歩。室内周辺での移動を確認。無理のない見守りを継続。"
    else:
        activity_status = "安静状態"
        activity_comment = "本日の顕著な歩行記録は未検出（室内安静または休養中）。"

    # Evaluate vitals
    if hr:
        if hr > 100:
            vital_status = "頻脈注意"
            vital_comment = f"最新心拍数 {hr} bpm (頻脈傾向)。水分補給と安静時再測定を推奨。"
        elif hr < 50:
            vital_status = "徐脈注意"
            vital_comment = f"最新心拍数 {hr} bpm (徐脈傾向)。随時状態確認。"
        else:
            vital_status = "正常安定"
            vital_comment = f"最新心拍数 {hr} bpm (正常安静域)。リズム良好。"
    else:
        vital_status = "未測定"
        vital_comment = "直近の心拍数記録なし。"

    spo2_comment = f"最新SpO2: {spo2}%" if spo2 else "SpO2: -%"

    karte_entry = (
        f"【スマートウォッチ活動日報（Google Fit連携）】\n"
        f"・活動評価: {activity_status}（{activity_comment}）\n"
        f"・バイタル推移: {vital_status}（{vital_comment} / {spo2_comment}）\n"
        f"・取得元: B16Pro実機 ➔ Google Fitクラウド同期 ({datetime.now().strftime('%H:%M')}確認)"
    )

    return {
        "status": "success",
        "user_id": user_id,
        "user_name": user.get("name") if user else f"利用者ID:{user_id}",
        "room_number": user.get("room_number", "") if user else "",
        "steps": steps,
        "heart_rate": hr,
        "spo2": spo2,
        "activity_status": activity_status,
        "activity_comment": activity_comment,
        "vital_status": vital_status,
        "vital_comment": vital_comment,
        "karte_entry": karte_entry,
        "hourly_trends": trends,
        "updated_at": datetime.now().isoformat()
    }

async def sync_user_google_fit(user_id: int, broadcast_callback=None) -> Dict[str, Any]:
    """
    Fetches latest data from Google Fit, saves to DB if new, and triggers staff alert if abnormal.
    """
    user = db.get_user(user_id)
    if not user:
        return {"status": "error", "message": f"User {user_id} not found"}

    fit_data = fetch_latest_fit_vitals(hours_back=12)
    if fit_data.get("status") != "success":
        return fit_data

    hr = fit_data.get("heart_rate")
    spo2 = fit_data.get("spo2")
    steps = fit_data.get("steps", 0)

    if hr is None and spo2 is None and (steps is None or steps == 0):
        return {"status": "no_data", "message": "Google Fitに直近の心拍/SpO2/歩数データがありません"}

    # Check against thresholds
    vitals_check = {
        "heart_rate": hr,
        "spo2": spo2,
        "steps": steps
    }
    is_alert, alert_reason = vital_parser.validate_vitals(vitals_check)

    # Check recent record to avoid duplicate logging if values have not changed significantly
    recent_records = db.get_vital_records(user_id, limit=1)
    if recent_records:
        latest_rec = recent_records[0]
        same_hr = (latest_rec.get("heart_rate") == hr)
        same_spo2 = (latest_rec.get("spo2") == spo2)
        step_diff = abs((latest_rec.get("steps") or 0) - (steps or 0))
        # If HR & SpO2 match and steps haven't changed by >= 30, consider already synced
        if same_hr and same_spo2 and step_diff < 30:
            return {
                "status": "already_synced",
                "heart_rate": hr,
                "spo2": spo2,
                "steps": steps,
                "message": "最新データは既に記録済みです"
            }

    raw_text = f"Google Fit自動同期 (心拍: {hr or '-'} bpm, SpO2: {spo2 or '-'} %, 歩数: {steps:,} 歩)"

    rec_id = db.add_vital_record(
        user_id=user_id,
        heart_rate=hr,
        spo2=spo2,
        steps=steps,
        source="google_fit",
        raw_text=raw_text,
        is_alert=1 if is_alert else 0,
        alert_reason=alert_reason
    )

    if broadcast_callback:
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

    summary_info = get_today_activity_summary(user_id)

    return {
        "status": "success",
        "record_id": rec_id,
        "heart_rate": hr,
        "spo2": spo2,
        "steps": steps,
        "is_alert": is_alert,
        "alert_reason": alert_reason,
        "summary": summary_info
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
