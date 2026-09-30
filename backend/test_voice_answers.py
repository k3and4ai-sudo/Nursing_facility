import unittest
import re

class TestEtegamiVoiceAnswers(unittest.TestCase):
    def test_mode_recognition_keywords(self):
        new_samples = [
            "新しく描く",
            "新しく描きたいです",
            "新しい絵を描きたい",
            "新しい絵",
            "新しいのがいい",
            "最初から描きます",
            "いいえ",
            "違う絵がいいです",
            "新規でお願いします",
            "新しく",
            "新しい絵を描く"
        ]
        
        base_samples = [
            "今までの絵をベースにしてください",
            "今までのでいいです",
            "今までの絵",
            "ベースにして",
            "ベースでお願いします",
            "前のでいいです",
            "前回の絵",
            "はい",
            "うん",
            "そうしてください"
        ]

        def check_mode(transcribed_text):
            clean_ans = transcribed_text.replace(" ", "").replace("、", "").replace("。", "")
            is_new_choice = any(w in clean_ans for w in [
                "新しく", "新しい", "ちがう", "違う", "いや", "最初から", "別のに", "別の絵", "新規", "新柄",
                "新しいの", "新しい絵", "新しく描く", "新しく描きたい", "新しい絵を描く", "いいえ"
            ])
            is_base_choice = any(w in clean_ans for w in [
                "はい", "うん", "そうして", "そう", "ベースに", "ベースで", "ベース", "前ので", "前のでいい",
                "今までの", "今までので", "前回の絵", "前の絵", "今までの絵", "ベースの絵"
            ])
            if is_new_choice:
                return "generate_new"
            if is_base_choice:
                return "asset_base"
            return None

        for s in new_samples:
            mode = check_mode(s)
            self.assertEqual(mode, "generate_new", f"Failed for new sample: {s}")

        for s in base_samples:
            mode = check_mode(s)
            self.assertEqual(mode, "asset_base", f"Failed for base sample: {s}")

    def test_invalid_motif_exclusion(self):
        def is_invalid_motif(cand_text: str) -> bool:
            if not cand_text or len(cand_text) < 1:
                return True
            exact_banned = [
                "絵", "え", "絵手紙", "えてがみ", "お絵描き", "お絵かき", "何か", "なに",
                "新しい", "新しく", "新しい絵", "新しいの", "最初から", "別のに",
                "前のでいい", "前の絵", "今までの絵", "ベースの絵", "ベース", "画像", "新しい画像"
            ]
            if cand_text in exact_banned:
                return True
            contains_banned = [
                "新しい", "新しく", "ベース", "前ので", "今まで", "最初から", "聞こえ", "ますか", "です", "たい", "さん"
            ]
            return any(b in cand_text for b in contains_banned)

        self.assertTrue(is_invalid_motif("新しい絵"))
        self.assertTrue(is_invalid_motif("新しく"))
        self.assertTrue(is_invalid_motif("新しいの"))
        self.assertTrue(is_invalid_motif("前のでいい"))
        self.assertTrue(is_invalid_motif("ベース"))
        self.assertFalse(is_invalid_motif("白い子犬"))
        self.assertFalse(is_invalid_motif("富士山"))
        self.assertFalse(is_invalid_motif("縁側とお茶"))

if __name__ == "__main__":
    unittest.main()
