import asyncio
import unittest
from fastapi.testclient import TestClient
from backend.main import app, manager
from backend import database as db
from backend import vital_parser

class TestSmartwatchIntegration(unittest.TestCase):
    def setUp(self):
        db.db_init()
        self.client = TestClient(app)
        
        # Ensure a test user bound to terminal_id exists
        user = db.get_user_by_terminal("user_tablet_1")
        if user:
            self.user_id = user["id"]
            self.terminal_id = "user_tablet_1"
        else:
            self.user_id = db.add_user("山田 太郎", 85, "101", "user_tablet_1", "mild", "要見守り", "優しく傾聴")
            self.terminal_id = "user_tablet_1"

    def test_rest_api_vital_recording(self):
        """Test POST /api/users/{user_id}/vitals with heart_rate and spo2."""
        # 1. Normal measurement
        payload = {
            "heart_rate": 72,
            "spo2": 98,
            "source": "smartwatch_ble",
            "raw_text": "BLE心拍テスト"
        }
        res = self.client.post(f"/api/users/{self.user_id}/vitals", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["is_alert"])

        # 2. Tachycardia alert
        tachy_payload = {
            "heart_rate": 130,
            "spo2": 97,
            "source": "smartwatch_ble"
        }
        res = self.client.post(f"/api/users/{self.user_id}/vitals", json=tachy_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_alert"])
        self.assertIn("頻脈", data["alert_reason"])

        # 3. Hypoxia alert
        hypoxia_payload = {
            "heart_rate": 80,
            "spo2": 89,
            "source": "smartwatch_ble"
        }
        res = self.client.post(f"/api/users/{self.user_id}/vitals", json=hypoxia_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_alert"])
        self.assertIn("危険低酸素", data["alert_reason"])

        # Verify DB records
        records = db.get_vital_records(self.user_id, limit=5)
        self.assertGreaterEqual(len(records), 3)
        self.assertEqual(records[0]["spo2"], 89)
        self.assertEqual(records[0]["source"], "smartwatch_ble")

    def test_websocket_smartwatch_vital_and_sos(self):
        """Test WebSocket client sending vital_data and emergency_sos."""
        with self.client.websocket_connect(f"/ws/user/{self.terminal_id}") as client_ws:
            # 1. Send normal vital data
            client_ws.send_json({
                "type": "vital_data",
                "heart_rate": 74,
                "spo2": 99,
                "source": "smartwatch_ble"
            })
            resp = client_ws.receive_json()
            if resp.get("type") == "today_schedules":
                resp = client_ws.receive_json()
            self.assertEqual(resp["type"], "vital_recorded")
            self.assertEqual(resp["heart_rate"], 74)
            self.assertEqual(resp["spo2"], 99)
            self.assertFalse(resp["is_alert"])

            # 2. Send tachycardia alert
            client_ws.send_json({
                "type": "vital_data",
                "heart_rate": 126,
                "spo2": 96,
                "source": "smartwatch_ble"
            })
            resp = client_ws.receive_json()
            self.assertEqual(resp["type"], "vital_recorded")
            self.assertTrue(resp["is_alert"])
            self.assertIn("頻脈", resp["alert_reason"])

            # 3. Send emergency SOS
            client_ws.send_json({
                "type": "emergency_sos",
                "reason": "転倒検知",
                "heart_rate": 115,
                "spo2": 95,
                "source": "smartwatch_sos"
            })
            resp = client_ws.receive_json()
            self.assertEqual(resp["type"], "emergency_sos_ack")
            self.assertEqual(resp["status"], "staff_notified")

if __name__ == "__main__":
    unittest.main()
