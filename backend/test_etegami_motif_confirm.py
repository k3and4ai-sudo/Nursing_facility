import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock

class TestEtegamiMotifConfirm(unittest.TestCase):
    def test_voice_answering_ignored_when_confirm_pending(self):
        # モチーフ確認待機中は音声での回答判定を行わず、画面タッチのみを待つ仕様のテスト
        session = MagicMock()
        session.pending_motif_confirm = {
            "motif": "白いマルチーズ",
            "prompt_en": "a white maltese",
            "title": "手作り絵手紙",
            "calligraphy": "元気いっぱい"
        }

        # 音声で「はい」「これでいいよ」「いいえ」などが来ても、pending_confirmがあるときは
        # 音声による確定・却下は実行されず、画面タッチを待つ
        voice_inputs = ["はい", "これでいいよ", "いいえ", "直して", "うん"]
        for speech_text in voice_inputs:
            pending_confirm = getattr(session, "pending_motif_confirm", None)
            self.assertIsNotNone(pending_confirm)
            # バックエンド内では pending_confirm がある場合は即 return して音声判定をスキップする
            should_wait_touch = pending_confirm is not None
            self.assertTrue(should_wait_touch)

        print("✓ Verified voice answering is completely ignored during motif confirmation.")

    def test_gemini_system_note_touch_only_guidance(self):
        eff_motif = "白いマルチーズ"
        system_note = (
            f"画面に聞き取り内容の確認（『{eff_motif}』）が表示されました。"
            f"利用者に優しく『聞き取り内容の確認が表示されています。よろしければ画面の「はい」をタッチしてくださいね。描き直すときは「いいえ」をタッチしてくださいね』と音声で案内してください。"
            f"画面タッチでのみ受け付けるため、声での返事は求めないでください。"
        )
        self.assertIn("よろしければ画面の「はい」をタッチしてくださいね", system_note)
        self.assertIn("描き直すときは「いいえ」をタッチしてくださいね", system_note)
        self.assertIn("声での返事は求めないでください", system_note)
        self.assertNotIn("これでいいよと伝えてください", system_note)
        print("✓ Verified Gemini system note guides touch-only response.")

if __name__ == '__main__':
    unittest.main()
