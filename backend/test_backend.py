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

    def test_prompt_templates(self):
        """Test prompt template loading and updating."""
        templates = db.get_all_prompt_templates()
        self.assertGreaterEqual(len(templates), 4)
        
        # Update a template
        db.update_prompt_template("template_listening", "更新された受容プロンプト")
        updated_templates = db.get_all_prompt_templates()
        listening_tmpl = next(t for t in updated_templates if t["key_name"] == "template_listening")
        self.assertEqual(listening_tmpl["content"], "更新された受容プロンプト")

    def test_barber_reservations(self):
        """Test barber reservations and report updating."""
        user_id = db.add_user("佐藤 次郎", 80, "105", "tablet_barber_test", "mild", "", "")
        res_id = db.add_barber_reservation(user_id, "2026-09-01 10:00", "カット", "首角度注意")
        self.assertGreater(res_id, 0)
        
        reservations = db.get_barber_reservations()
        self.assertTrue(any(r["id"] == res_id for r in reservations))
        
        # Update report
        db.update_barber_report(res_id, "completed", "無事にカット完了いたしました。")
        updated_res = [r for r in db.get_barber_reservations() if r["id"] == res_id][0]
        self.assertEqual(updated_res["status"], "completed")
        self.assertEqual(updated_res["report"], "無事にカット完了いたしました。")

    def test_group_access_control(self):
        """Test group access control logic for different roles."""
        user_id = db.add_user("高橋 三郎", 88, "108", "tablet_group_test", "none", "", "")
        group_id = db.add_group("高橋様グループ", user_id)
        
        staff_account = {"role": "staff", "group_id": None}
        barber_account = {"role": "barber", "group_id": None}
        family_own = {"role": "family", "group_id": group_id}
        family_other = {"role": "family", "group_id": 9999}
        
        self.assertTrue(db.check_group_access(staff_account, user_id))
        self.assertTrue(db.check_group_access(barber_account, user_id))
        self.assertTrue(db.check_group_access(family_own, user_id))
        self.assertFalse(db.check_group_access(family_other, user_id))

    def test_gemini_live_debug_mode(self):
        """Test anonymization and Gemini Live query function in debug mode."""
        from backend.main import anonymize_user_name, query_gemini_live_chat
        
        # Test real name anonymization
        anonymized = anonymize_user_name("山田 太郎")
        self.assertEqual(anonymized, "太郎さん")
        self.assertNotIn("山田", anonymized)
        
        # Test Gemini Live query response
        test_user = {"name": "山田 太郎", "dementia_level": "mild", "attention_points": "優しく傾聴"}
        reply = query_gemini_live_chat(test_user, [], "こんにちは", "")
        self.assertIn("Gemini Live", reply)
        self.assertIn("太郎さん", reply)
        self.assertNotIn("山田 太郎", reply)

    def test_clean_text_for_tts(self):
        """Test that debug tags and emojis are stripped for clean TTS speech synthesis."""
        from backend.main import clean_text_for_tts
        
        raw_reply = "✨ [Gemini Live デバッグ応答] 太郎さん、こんにちは！"
        cleaned = clean_text_for_tts(raw_reply)
        self.assertEqual(cleaned, "太郎さん、こんにちは！")
        self.assertNotIn("Gemini Live", cleaned)
        self.assertNotIn("✨", cleaned)

    def test_bidi_audio_buffer(self):
        """Test continuous full-duplex bidi_audio buffer accumulation."""
        from backend.main import bidi_buffers
        
        terminal_id = "test_bidi_term"
        bidi_buffers[terminal_id] = bytearray()
        
        chunk = b"1234567890" * 1000  # 10,000 bytes
        bidi_buffers[terminal_id].extend(chunk)
        self.assertEqual(len(bidi_buffers[terminal_id]), 10000)
        
        bidi_buffers[terminal_id].extend(chunk * 3) # Total 40,000 bytes
        self.assertGreaterEqual(len(bidi_buffers[terminal_id]), 38000)
        
        bidi_buffers[terminal_id].clear()
        self.assertEqual(len(bidi_buffers[terminal_id]), 0)

    def test_query_gemini_live_audio(self):
        """Test native Gemini multimodal audio query function."""
        from backend.main import query_gemini_live_audio
        
        test_user = {"name": "山田 太郎", "dementia_level": "mild", "attention_points": "優しく傾聴"}
        dummy_audio = b"RIFF" + b"\x00" * 100
        res = query_gemini_live_audio(test_user, [], dummy_audio, "")
        self.assertIn("ai_reply", res)
        self.assertIn("Gemini Live", res["ai_reply"])
    def test_sanitize_gemini_response(self):
        """Test stripping of disclaimer meta-text from Gemini Live responses."""
        from backend.main import sanitize_gemini_response
        
        raw_text = "「はい、聞こえています。」ゆっくりと落ち着いて過ごしましょうね😊 **注意:** この会話は、意図的に不適切な内容を含むことを目的としたものではありません。"
        cleaned = sanitize_gemini_response(raw_text)
        self.assertNotIn("注意:", cleaned)
        self.assertNotIn("意図的に", cleaned)
        self.assertTrue(len(cleaned) > 0)

    def test_pii_guardrail_monitor(self):
        """Test parallel background PII Guardrail Monitor prohibited terms detection."""
        from backend.gemini_live import PIIGuardrailMonitor
        
        pii_triggered = []
        def on_pii(cat, detail):
            pii_triggered.append((cat, detail))

        test_user = {"name": "山田 太郎"}
        monitor = PIIGuardrailMonitor(user=test_user, on_pii_detected=on_pii)
        
        self.assertIn("山田 太郎", monitor.prohibited_terms)
        self.assertIn("山田", monitor.prohibited_terms)
        
        # Test simulated PII detection trigger
        monitor.on_pii_detected("real_name", "実名（山田）が含まれていました。")
        self.assertEqual(len(pii_triggered), 1)
        self.assertEqual(pii_triggered[0][0], "real_name")

if __name__ == "__main__":
    unittest.main()
