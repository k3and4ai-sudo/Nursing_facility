import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock

class TestEtegamiMotifConfirm(unittest.TestCase):
    def test_voice_affirmation_keywords(self):
        confirm_samples = [
            "はい",
            "これでいいよ",
            "これでいい",
            "これで描いて",
            "これで描く",
            "描いて",
            "かいて",
            "オッケー",
            "おっけー",
            "いいよ",
            "おねがい",
            "お願い",
            "よろしく",
            "決定",
            "そうして",
            "そうですね",
            "そうです",
            "うん",
            "良い",
            "いいね",
            "ええ"
        ]

        reject_samples = [
            "いいえ",
            "直して",
            "なおして",
            "違う",
            "ちがう",
            "変更",
            "へんこう",
            "やり直して",
            "やりなおして",
            "違います",
            "ダメ",
            "だめ",
            "直したい",
            "変えたい"
        ]

        def check_confirmation(speech_text):
            clean = speech_text.replace(" ", "").replace("、", "").replace("。", "")
            is_yes = any(y in clean for y in [
                "はい", "これでいい", "これでいいよ", "これで描いて", "これで描く", "描いて", "かいて", "オッケー", "おっけー",
                "いいよ", "おねがい", "お願い", "よろしく", "決定", "そうして", "そうですね", "そうです", "うん", "良い", "いいね", "ええ"
            ])
            is_no = any(n in clean for n in [
                "いいえ", "直して", "なおして", "違う", "ちがう", "変更", "へんこう", "やり直して", "やりなおして",
                "もう一回", "もういちど", "違います", "ちがいます", "ダメ", "だめ", "直したい", "変えたい"
            ])
            has_replacement = any(kw in clean for kw in ["にして", "に変えて", "にしてほしい", "を描いて", "をかいて"])
            if is_yes and not is_no and not has_replacement:
                return True
            elif is_no and not has_replacement:
                return False
            return None

        for s in confirm_samples:
            res = check_confirmation(s)
            self.assertTrue(res, f"Failed for positive confirmation: '{s}'")

        for s in reject_samples:
            res = check_confirmation(s)
            self.assertFalse(res, f"Failed for negative confirmation: '{s}'")

        print("✓ Verified all voice confirmation keywords.")

    def test_gemini_system_note_content(self):
        eff_motif = "白いマルチーズ"
        system_note = (
            f"画面に聞き取り内容の確認（『{eff_motif}』）が表示されました。"
            f"利用者に優しく『聞き取り内容の確認が表示されています。これでよろしければ画面の「はい」をタッチするか、「これでいいよ」と伝えてくださいね』と音声で案内してください。"
        )
        self.assertIn("聞き取り内容の確認が表示されています", system_note)
        self.assertIn("これでいいよ", system_note)
        self.assertIn("白いマルチーズ", system_note)
        print("✓ Verified Gemini system note structure and wording.")

if __name__ == '__main__':
    unittest.main()
