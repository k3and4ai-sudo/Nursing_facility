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
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Clean existing test schedules for today
        with db.get_db_connection() as conn:
            conn.execute("DELETE FROM schedules WHERE user_id = ? AND date = ?", (self.user_id, today_str))
            conn.commit()
        # Add one past schedule (01:00) and one upcoming schedule (23:50)
        res_past = self.client.post(f"/api/users/{self.user_id}/schedules", json={
            "date": today_str,
            "time": "01:00",
            "title": "深夜見守り",
            "category": "meal",
            "location": "居室",
            "notes": "過去予定テスト"
        })
        past_id = res_past.json()["id"]

        res_up = self.client.post(f"/api/users/{self.user_id}/schedules", json={
            "date": today_str,
            "time": "23:50",
            "title": "夜間リラックス",
            "category": "event",
            "location": "居室",
            "notes": "未来予定テスト"
        })
        up_id = res_up.json()["id"]

        try:
            # Test terminal today schedules endpoint
            res = self.client.get(f"/api/users/terminal/{self.terminal_id}/today_schedules")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("announcement_text", data)
            self.assertIn("schedules", data)
            self.assertEqual(data["upcoming_count"], 1)
            self.assertEqual(data["past_count"], 1)
            # Verify phrasing
            self.assertIn("本日、これからの予定は", data["announcement_text"])
            self.assertIn("については予定時刻を過ぎました", data["announcement_text"])
            self.assertIn("深夜見守り", data["announcement_text"])
            self.assertIn("夜間リラックス", data["announcement_text"])
            print("\nSpoken Announcement with Past & Upcoming:\n", data["announcement_text"])

            # Verify schedules order: upcoming first, then past
            schedules = data["schedules"]
            self.assertFalse(schedules[0]["is_past"])
            self.assertEqual(schedules[0]["title"], "夜間リラックス")
            self.assertEqual(schedules[0]["reminder_time"], "23:48")
            self.assertIn("23時50分に", schedules[0]["reminder_text"])
            self.assertIn("予定されています", schedules[0]["reminder_text"])
            self.assertTrue(len(schedules[0]["reminder_audio"]) > 0)

            self.assertTrue(schedules[1]["is_past"])
            self.assertEqual(schedules[1]["title"], "深夜見守り")
            self.assertEqual(schedules[1]["reminder_time"], "00:58")
        finally:
            self.client.delete(f"/api/schedules/{past_id}")
            self.client.delete(f"/api/schedules/{up_id}")

if __name__ == "__main__":
    unittest.main()
