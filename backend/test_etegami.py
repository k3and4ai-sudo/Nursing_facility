import unittest
from backend import multimedia, database as db

class TestEtegamiRealtimeCreative(unittest.TestCase):
    def setUp(self):
        db.db_init()
        # Seed test resident
        users = db.get_all_users()
        if not users:
            db.create_user("テスト太郎", "101", "TERM-TEST-01", "0001", "test_group")
            self.user = db.get_user_by_terminal("TERM-TEST-01")
        else:
            self.user = users[0]
        self.terminal_id = self.user.get("terminal_id", "TERM-001")
        self.user_id = self.user["id"]

    def test_etegami_creation_and_motifs(self):
        # 1. Test Sunset / Veranda motif
        res1 = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="夕焼けの縁側",
            message_hint="のんびり お茶の時間"
        )
        self.assertTrue("夕暮れ" in res1["title"] or "縁側" in res1["title"])
        self.assertEqual(res1["calligraphy"], "のんびり お茶の時間")
        self.assertIn("generated_relaxation_porch.jpg", res1["image_url"])

        # 2. Test Sparrows / Birds motif
        res2 = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="寄り添う小鳥の絵",
            message_hint=""
        )
        self.assertIn("小鳥", res2["title"])
        self.assertIn("generated_healing_sparrows.jpg", res2["image_url"])
        self.assertEqual(res2["stamp_icon"], "🕊️")

        # 3. Test Spring / Sakura motif
        res3 = multimedia.modify_or_create_etegami(
            user_id=self.user_id,
            terminal_id=self.terminal_id,
            motif_hint="桜の花見",
            message_hint="春爛漫 心晴れやかに"
        )
        self.assertIn("桜", res3["title"])
        self.assertIn("sample_postcard_spring.jpg", res3["image_url"])
        self.assertEqual(res3["season"], "spring")

        # 4. Verify persistence in DB
        latest = db.get_latest_image_prompt_payload(terminal_id=self.terminal_id)
        self.assertIsNotNone(latest)
        self.assertIn("payload", latest)
        self.assertEqual(latest["payload"]["postcard_metadata"]["calligraphy_message"], "春爛漫 心晴れやかに")

if __name__ == "__main__":
    unittest.main()
