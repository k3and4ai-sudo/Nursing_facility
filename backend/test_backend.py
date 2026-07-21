import unittest
import os
import sys

# Ensure backend folder is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import encrypt_data, decrypt_data
import backend.database as db
import backend.vital_parser as vital_parser

class TestNursingFacilityBackend(unittest.TestCase):

    def setUp(self):
        # Setup temporary test database
        db.DB_PATH = "test_nursing_facility.db"
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
        db.db_init()

    def tearDown(self):
        # Clean up test database
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)

    def test_encryption_decryption(self):
        """Test that data is encrypted securely and can be decrypted correctly."""
        original_text = "山田 太郎"
        encrypted = encrypt_data(original_text)
        
        self.assertNotEqual(original_text, encrypted)
        self.assertTrue(len(encrypted) > 0)
        
        decrypted = decrypt_data(encrypted)
        self.assertEqual(original_text, decrypted)

    def test_regex_vital_parser(self):
        """Test regex fallback parser with common Japanese spoken patterns."""
        # Test pattern 1: Temperature and blood pressure
        text_1 = "熱は36度8分で、血圧は120の80です。"
        vitals_1 = vital_parser.fallback_regex_parser(text_1)
        self.assertEqual(vitals_1["temperature"], 36.8)
        self.assertEqual(vitals_1["systolic"], 120)
        self.assertEqual(vitals_1["diastolic"], 80)
        self.assertIsNone(vitals_1["weight"])

        # Test pattern 2: Temperature (decimal) and weight
        text_2 = "体温は37.2度。体重は65.4キロになりました。"
        vitals_2 = vital_parser.fallback_regex_parser(text_2)
        self.assertEqual(vitals_2["temperature"], 37.2)
        self.assertEqual(vitals_2["weight"], 65.4)
        self.assertIsNone(vitals_2["systolic"])

    def test_vital_validation_alerts(self):
        """Test that vital values outside threshold limits trigger alerts."""
        # Safe vital values
        safe_vitals = {"temperature": 36.5, "systolic": 120, "diastolic": 80, "weight": 60.0}
        is_alert, reason = vital_parser.validate_vitals(safe_vitals)
        self.assertFalse(is_alert)
        self.assertEqual(reason, "")

        # High temperature alert
        fever_vitals = {"temperature": 38.2, "systolic": 120, "diastolic": 80, "weight": 60.0}
        is_alert, reason = vital_parser.validate_vitals(fever_vitals)
        self.assertTrue(is_alert)
        self.assertIn("高熱", reason)

        # High blood pressure alert
        high_bp_vitals = {"temperature": 36.5, "systolic": 145, "diastolic": 95, "weight": 60.0}
        is_alert, reason = vital_parser.validate_vitals(high_bp_vitals)
        self.assertTrue(is_alert)
        self.assertIn("血圧高", reason)

    def test_database_user_crud(self):
        """Test patient registration, retrieval, and updates in SQLite."""
        # Create user
        user_id = db.add_user(
            name="山田 太郎",
            age=85,
            room_number="101",
            terminal_id="test_tablet_1",
            dementia_level="mild",
            notes="血圧注意",
            attention_points="優しく話す"
        )
        self.assertTrue(user_id > 0)

        # Retrieve user
        user = db.get_user(user_id)
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "山田 太郎")
        self.assertEqual(user["age"], 85)
        self.assertEqual(user["room_number"], "101")
        self.assertEqual(user["dementia_level"], "mild")
        self.assertEqual(user["notes"], "血圧注意")
        self.assertEqual(user["attention_points"], "優しく話す")

        # Get user by terminal_id
        user_by_term = db.get_user_by_terminal("test_tablet_1")
        self.assertEqual(user_by_term["id"], user_id)

        # Update user
        db.update_user(
            user_id=user_id,
            name="山田 花子",
            age=86,
            room_number="102",
            terminal_id="test_tablet_1",
            dementia_level="moderate",
            notes="歩行補助必要",
            attention_points="孫の話をする"
        )
        
        updated_user = db.get_user(user_id)
        self.assertEqual(updated_user["name"], "山田 花子")
        self.assertEqual(updated_user["age"], 86)
        self.assertEqual(updated_user["room_number"], "102")
        self.assertEqual(updated_user["dementia_level"], "moderate")
        self.assertEqual(updated_user["notes"], "歩行補助必要")

        # Delete user
        db.delete_user(user_id)
        self.assertIsNone(db.get_user(user_id))

    def test_database_relations_and_logs(self):
        """Test chat history and vital logging linked to a user."""
        user_id = db.add_user("鈴木 一郎", 90, "202", "test_tablet_2", "none", "", "")
        
        # Add vitals
        db.add_vital_record(user_id, 36.7, 72.1, 120, 80, "測定完了です", 0, "")
        records = db.get_vital_records(user_id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["temperature"], 36.7)
        self.assertEqual(records[0]["raw_text"], "測定完了です")

        # Add chat history
        db.add_chat_message(user_id, "user", "こんにちは")
        db.add_chat_message(user_id, "ai", "こんにちは、鈴木さん！")
        
        chat = db.get_chat_history(user_id)
        self.assertEqual(len(chat), 2)
        self.assertEqual(chat[0]["sender"], "user")
        self.assertEqual(chat[0]["message"], "こんにちは")
        self.assertEqual(chat[1]["sender"], "ai")
        self.assertEqual(chat[1]["message"], "こんにちは、鈴木さん！")

if __name__ == "__main__":
    unittest.main()
