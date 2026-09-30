import unittest
from unittest.mock import MagicMock
from backend.gemini_live import GeminiLiveSession
from backend import multimedia

class TestEtegamiModes(unittest.TestCase):
    def setUp(self):
        self.user = {
            "id": 1,
            "name": "山田 太郎",
            "care_level": "要介護1",
            "terminal_id": "terminal_1"
        }

    def test_gemini_prepare_mode_asset_base(self):
        prepare_mock = MagicMock()
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_etegami_prepare_mode=prepare_mock
        )
        session.has_resident_requested_etegami = True
        
        # Test detection of "みまもりさん、絵手紙をベースにしてください"
        session._handle_text_chunk("みまもりさん、絵手紙をベースにしてください。どんな思い出やお話の絵手紙にしましょうか？")
        prepare_mock.assert_called_with("asset_base")
        self.assertEqual(session.etegami_prepare_mode, "asset_base")

    def test_gemini_prepare_mode_blocked_if_no_resident_request(self):
        prepare_mock = MagicMock()
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_etegami_prepare_mode=prepare_mock
        )
        session.has_resident_spoken_in_session = True
        session.has_resident_requested_etegami = False
        
        # If resident hasn't asked to draw etegami, unsolicited Gemini base mode is blocked
        session._handle_text_chunk("みまもりさん、絵手紙をベースにしてください。")
        prepare_mock.assert_not_called()
        self.assertIsNone(session.etegami_prepare_mode)

    def test_gemini_prepare_mode_generate_new(self):
        prepare_mock = MagicMock()
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_etegami_prepare_mode=prepare_mock
        )
        session.has_resident_requested_etegami = True
        
        # Test detection of "みまもりさん、新しい絵を描いてください"
        session._handle_text_chunk("みまもりさん、新しい絵を描いてください。新しい絵ですね！どんな場面を描きましょうか？")
        prepare_mock.assert_called_with("generate_new")
        self.assertEqual(session.etegami_prepare_mode, "generate_new")

    def test_gemini_prepare_mode_with_circle_3(self):
        prepare_mock = MagicMock()
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_etegami_prepare_mode=prepare_mock
        )
        session.has_resident_requested_etegami = True
        
        # Test variation with "みまもり③さん"
        session._handle_text_chunk("みまもり③さん、新しい画像をベースにしてください。")
        prepare_mock.assert_called_with("generate_new")

    def test_multimedia_mode_generate_new(self):
        card = multimedia.modify_or_create_etegami(
            user_id=1,
            terminal_id="terminal_1",
            motif_hint="愛犬ポチと河川敷の散歩",
            message_hint="今日も楽しく お散歩日和",
            mode="generate_new"
        )
        self.assertEqual(card["base_source"], "ai_generated_new")
        self.assertIn("愛犬ポチと河川敷の散歩", card["title"])
        self.assertTrue(card["image_url"].startswith("/family/assets/"))

    def test_multimedia_mode_asset_base_matching(self):
        card = multimedia.modify_or_create_etegami(
            user_id=1,
            terminal_id="terminal_1",
            motif_hint="運動会とお弁当",
            mode="asset_base"
        )
        self.assertEqual(card["base_source"], "reminiscence")
        self.assertEqual(card["image_url"], "/family/assets/generated_undoukai_bento.jpg")

    def test_multimedia_mode_asset_base_novel_motif(self):
        card = multimedia.modify_or_create_etegami(
            user_id=1,
            terminal_id="terminal_1",
            motif_hint="富士山と気球の旅",
            mode="asset_base"
        )
        # Should generate novel image since there is no matching preset asset
        self.assertEqual(card["base_source"], "ai_generated_novel")
        self.assertIn("富士山と気球の旅", card["title"])
        self.assertTrue(card["image_url"].startswith("/family/assets/"))

if __name__ == "__main__":
    unittest.main()
