import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.main import app
import backend.database as db

class TestSchedules(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        db.db_init()
        # Find valid user
        with db.get_db_connection() as conn:
            row = conn.execute("SELECT id, terminal_id FROM users LIMIT 1").fetchone()
            self.user_id = row["id"]
            self.terminal_id = row["terminal_id"]

    def test_schedule_crud(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Add Schedule via API
        res = self.client.post(f"/api/users/{self.user_id}/schedules", json={
            "date": today_str,
            "time": "11:00",
            "title": "機能訓練テスト",
            "category": "rehab",
            "location": "リハビリ室",
            "notes": "テスト用予定"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        sched_id = data["id"]

        # 2. Get Schedules by Date
        res_get = self.client.get(f"/api/users/{self.user_id}/schedules?date={today_str}")
        self.assertEqual(res_get.status_code, 200)
        schedules = res_get.json()
        self.assertTrue(any(s["id"] == sched_id for s in schedules))

        # 3. Update Schedule
        res_update = self.client.put(f"/api/schedules/{sched_id}", json={
            "date": today_str,
            "time": "11:15",
            "title": "機能訓練テスト（時間変更）",
            "category": "rehab",
            "location": "リハビリ室2",
            "notes": "時間変更完了"
        })
        self.assertEqual(res_update.status_code, 200)

        # 4. Delete Schedule
        res_delete = self.client.delete(f"/api/schedules/{sched_id}")
        self.assertEqual(res_delete.status_code, 200)

    def test_terminal_today_schedules_and_audio(self):
        # Test terminal today schedules endpoint
        res = self.client.get(f"/api/users/terminal/{self.terminal_id}/today_schedules")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("announcement_text", data)
        self.assertIn("schedules", data)
        self.assertTrue(len(data["announcement_text"]) > 0)
        print("Spoken Announcement:", data["announcement_text"])

if __name__ == "__main__":
    unittest.main()
