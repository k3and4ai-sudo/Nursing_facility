import unittest
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import multimedia, database as db
from backend.gemini_live import GeminiLiveSession

class TestEtegamiConversationBase(unittest.TestCase):
    def setUp(self):
        db.db_init()
        users = db.get_all_users()
        if not users:
            db.create_user("テスト太郎", "101", "TERM-TEST-99", "0001", "test_group")
            self.user = db.get_user_by_terminal("TERM-TEST-99")
        else:
            self.user = users[0]
        self.terminal_id = self.user.get("terminal_id", "TERM-TEST-99")
        self.user_id = self.user["id"]

        # Clean up existing test records
        try:
            conn = db.get_db()
            conn.execute("DELETE FROM image_prompt_payloads WHERE user_id = ?", (self.user_id,))
            conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (self.user_id,))
            conn.commit()
        except Exception:
            pass

    def tearDown(self):
        try:
            conn = db.get_db()
            conn.execute("DELETE FROM image_prompt_payloads WHERE user_id = ?", (self.user_id,))
            conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (self.user_id,))
            conn.commit()
        except Exception:
            pass

    def test_reminiscence_conversation_base(self):
        """Verify that reminiscence conversation history (undoukai / bento) becomes the draft artwork base."""
        # Add reminiscence conversation
        db.add_chat_message(self.user_id, "user", "昔の子供の頃の運動会を思い出してね、お弁当に美味しい煮物が入っていたんですよ")
        db.add_chat_message(self.user_id, "assistant", "素敵ですね！運動会のご家族で囲んだお弁当、どんな味でしたか？")

        # Generate draft etegami without specific motif hint (as if clicking or saying "絵を更新して")
        card = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="",
            message_hint="",
            is_completed=False
        )

        self.assertIn("運動会", card["title"])
        self.assertIn("generated_undoukai_bento.jpg", card["image_url"])
        self.assertEqual(card["status"], "drafting")
        self.assertFalse(card["is_completed"])
        self.assertEqual(card["badge_text"], "🎨 会話をもとに下絵を制作中")
        self.assertEqual(card["base_source"], "reminiscence")

    def test_healing_conversation_base(self):
        """Verify that healing conversation history (tea / porch / anxiety) becomes the draft artwork base."""
        # Add consultation/healing conversation
        db.add_chat_message(self.user_id, "user", "少し不安なことがあってね、縁側でのんびり温かいお茶でも飲みたい気分です")
        db.add_chat_message(self.user_id, "assistant", "肩の力を抜いて、温かいお茶を飲んでホッと一息つきましょうね")

        # Generate draft etegami
        card = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="",
            message_hint="",
            is_completed=False
        )

        self.assertIn("縁側", card["title"])
        self.assertIn("generated_relaxation_porch.jpg", card["image_url"])
        self.assertEqual(card["status"], "drafting")
        self.assertFalse(card["is_completed"])
        self.assertEqual(card["base_source"], "healing")

    def test_resident_modification_and_completion(self):
        """Verify resident modifying draft to sparrows and finalizing to completed status."""
        # Step 1: Initial draft
        db.add_chat_message(self.user_id, "user", "昔の桜のお花見が綺麗だったなあ")
        card1 = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="",
            is_completed=False
        )
        self.assertIn("桜", card1["title"])
        self.assertEqual(card1["status"], "drafting")

        # Step 2: Resident requests modification -> "寄り添う小鳥の絵にして"
        card2 = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="寄り添う小鳥にして",
            message_hint="心穏やかに 寄り添う日々",
            is_completed=False
        )
        self.assertIn("小鳥", card2["title"])
        self.assertIn("generated_healing_sparrows.jpg", card2["image_url"])
        self.assertEqual(card2["status"], "drafting")

        # Step 3: Resident satisfied -> "これでいいよ、完成！"
        card3 = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="これで完成",
            message_hint="心穏やかに 寄り添う日々",
            is_completed=True
        )
        self.assertTrue(card3["is_completed"])
        self.assertEqual(card3["status"], "completed")
        self.assertEqual(card3["badge_text"], "💮 ご本人様と完成")

        # Verify payload saved in DB for family
        latest_row = db.get_latest_image_prompt_payload(terminal_id=self.terminal_id)
        self.assertIsNotNone(latest_row)
        payload = latest_row.get("payload", {})
        self.assertTrue(payload.get("is_completed"))
        meta = payload.get("postcard_metadata", {})
        self.assertTrue(meta.get("is_completed"))
        self.assertIn("ご本人様と一緒に絵や添え字", meta.get("summary_for_family", ""))

    def test_gemini_live_completion_trigger(self):
        """Verify that Gemini's 'みまもりさん、デジタル絵手紙完成' triggers callback."""
        completed_called = []
        def on_completed():
            completed_called.append(True)

        session = GeminiLiveSession(
            user={"id": 1, "name": "テスト"},
            on_audio_received=lambda a: None,
            on_error=lambda e: None,
            on_etegami_completed=on_completed
        )

        session._handle_text_chunk("みまもりさん、デジタル絵手紙完成。とても素敵な絵手紙ができましたね！")
        self.assertEqual(len(completed_called), 1)

if __name__ == "__main__":
    unittest.main()
