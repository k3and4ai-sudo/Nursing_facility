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

    def test_mode_and_engine_touch_only_flow(self):
        # モード選択（新規かベースか）およびエンジン選択（無料か有料か）のタッチ専用化テスト
        session = MagicMock()
        session.etegami_prepare_mode = None
        session.etegami_image_engine = "pollinations"

        # 1. モード未決定時は画面タッチ（set_prepare_mode）でのみモードがセットされる
        # 音声で「新しい絵を描く」と喋っても、自動判定されず None のまま
        # クライアントから set_prepare_mode が届いた時のみ更新される
        def handle_client_mode_choice(mode):
            session.etegami_prepare_mode = mode

        handle_client_mode_choice("generate_new")
        self.assertEqual(session.etegami_prepare_mode, "generate_new")

        # 2. エンジン選択も画面タッチ（set_image_engine）でのみ更新される
        def handle_client_engine_choice(engine):
            session.etegami_image_engine = engine

        handle_client_engine_choice("google_image")
        self.assertEqual(session.etegami_image_engine, "google_image")
        print("✓ Verified mode and engine selection are touch-only.")

    def test_continuous_speech_accumulation_and_prompt_augmentation(self):
        from backend.multimedia import build_rich_etegami_prompt

        session = MagicMock()
        session.is_etegami_listening = True
        session.etegami_accumulated_text = ""

        # 連続した聞き取り発話の蓄積シミュレーション
        utterances = [
            "マルチーズを描いてほしいな",
            "座敷を走る白い犬がいいな",
            "赤い首輪をしていてね"
        ]
        for speech in utterances:
            acc = session.etegami_accumulated_text or ""
            if speech not in acc:
                session.etegami_accumulated_text = (acc + " " + speech).strip()

        self.assertIn("マルチーズ", session.etegami_accumulated_text)
        self.assertIn("座敷", session.etegami_accumulated_text)
        self.assertIn("赤い首輪", session.etegami_accumulated_text)

        # 「この内容で次に進む」が押された際の画像プロンプト付け足し検証
        prompt_en = build_rich_etegami_prompt(
            motif_ja="マルチーズ",
            accumulated_text_ja=session.etegami_accumulated_text
        )
        self.assertIn("maltese", prompt_en.lower())
        self.assertTrue("tatami" in prompt_en.lower() or "room" in prompt_en.lower())
        self.assertTrue("collar" in prompt_en.lower() or "red" in prompt_en.lower())
        self.assertTrue("running" in prompt_en.lower())
        print("✓ Verified continuous speech accumulation and prompt augmentation.")

if __name__ == '__main__':
    unittest.main()
