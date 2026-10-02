import unittest
from backend import multimedia

class TestIncrementalDrawingAndPrompt(unittest.TestCase):
    def test_build_rich_etegami_prompt(self):
        prompt = multimedia.build_rich_etegami_prompt(
            motif_ja="白いマルチーズ",
            details_ja=["座敷を走って回っています"]
        )
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 20)
        # Verify it contains no raw non-ASCII characters
        self.assertTrue(all(ord(c) < 128 for c in prompt))
        print("✓ Verified build_rich_etegami_prompt output:", prompt)

    def test_generate_image_with_pollinations_sana(self):
        prompt = "A beautiful Japanese Etegami watercolor painting of a fluffy cute white maltese puppy running in tatami room, washi paper texture, masterpiece"
        url = multimedia.generate_image_with_pollinations(
            prompt=prompt,
            output_filename="test_maltese_incremental.jpg",
            seed=42
        )
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("/family/assets/"))
        print("✓ Verified Pollinations.ai image generation with model=sana:", url)

if __name__ == "__main__":
    unittest.main()
