import unittest
from backend.main import check_etegami_visibility_intent
from backend.gemini_live import PIIGuardrailMonitor

class TestEtegamiNoFalsePositiveTriggers(unittest.TestCase):
    def test_whisper_hallucination_filter(self):
        monitor = PIIGuardrailMonitor(user={"name": "テスト"}, on_pii_detected=lambda cat, det: None)
        # Video/YouTube style hallucination phrases
        self.assertTrue(PIIGuardrailMonitor.is_hallucination_or_echo("この映像は、私の作品によると、 絵を描きたいです。こんにちは、ジェミナイさん。"))
        self.assertTrue(PIIGuardrailMonitor.is_hallucination_or_echo("作品によると、犬がいます"))
        self.assertTrue(PIIGuardrailMonitor.is_hallucination_or_echo("ご視聴ありがとうございました。"))
        self.assertTrue(PIIGuardrailMonitor.is_hallucination_or_echo("チャンネル登録よろしくお願いします"))
        # Genuine user speech must not be blocked
        self.assertFalse(PIIGuardrailMonitor.is_hallucination_or_echo("絵手紙を描きたいです"))
        self.assertFalse(PIIGuardrailMonitor.is_hallucination_or_echo("犬が走っている絵にしてください"))

    def test_normal_conversation_intent_rejection(self):
        casual_phrases = [
            "こんにちは、良い天気ですね",
            "お茶を淹れてください",
            "コーヒーを飲みますか",
            "犬の散歩に行ってきました",
            "夕焼けが綺麗ですね",
            "お弁当を作りました",
            "絵手紙が完成しました。通常会話に戻します。",
            "さっきの絵手紙は楽しかったですね",
            "汗をかきたいな",
            "恥をかきたくないです",
            "何か作りたいですね",
            "普通会話に戻してください",
            "普通にお話ししましょう",
        ]
        for phrase in casual_phrases:
            intent = check_etegami_visibility_intent(phrase)
            self.assertIn(
                intent,
                [None, False],
                f"Phrase '{phrase}' should not trigger etegami creation (got {intent})"
            )

    def test_explicit_etegami_intent_acceptance(self):
        explicit_phrases = [
            ("絵手紙を描きたいです", "creation_request"),
            ("絵を描きたい", "creation_request"),
            ("デジタル絵手紙を描きたい", "creation_request"),
            ("お絵描きしたいな", "creation_request"),
            ("絵手紙を見せて", True),
            ("絵手紙を出して", True),
            ("デジタル絵手紙を表示して", True),
            ("絵手紙を閉じて", False),
            ("絵手紙終了", False),
        ]
        for phrase, expected in explicit_phrases:
            intent = check_etegami_visibility_intent(phrase)
            self.assertEqual(
                intent,
                expected,
                f"Phrase '{phrase}' expected intent {expected}, got {intent}"
            )

if __name__ == "__main__":
    unittest.main()
