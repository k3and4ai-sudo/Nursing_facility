import unittest
import os
from PIL import Image
from backend import multimedia, config

class TestEtegamiRendering(unittest.TestCase):
    def test_puppy_rendering(self):
        output_name = "test_puppy_render.jpg"
        url = multimedia.create_artistic_watercolor_image(
            motif="白い子犬",
            theme_title="【手作り絵手紙】白い子犬の温もり",
            season="autumn",
            output_filename=output_name
        )
        self.assertTrue(url.endswith(output_name))
        path = os.path.join(os.path.dirname(config.BASE_DIR), "frontend/family/assets", output_name)
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (800, 600))
            self.assertEqual(img.mode, "RGB")
        print("✓ Puppy render verified successfully.")

    def test_cat_rendering(self):
        output_name = "test_cat_render.jpg"
        url = multimedia.create_artistic_watercolor_image(
            motif="三毛猫",
            theme_title="【手作り絵手紙】三毛猫の日だまり",
            season="spring",
            output_filename=output_name
        )
        self.assertTrue(url.endswith(output_name))
        path = os.path.join(os.path.dirname(config.BASE_DIR), "frontend/family/assets", output_name)
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (800, 600))
        print("✓ Cat render verified successfully.")

    def test_fuji_rendering(self):
        output_name = "test_fuji_render.jpg"
        url = multimedia.create_artistic_watercolor_image(
            motif="富士山の夕焼け",
            theme_title="【手作り絵手紙】雄大な富士山",
            season="winter",
            output_filename=output_name
        )
        self.assertTrue(url.endswith(output_name))
        path = os.path.join(os.path.dirname(config.BASE_DIR), "frontend/family/assets", output_name)
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (800, 600))
        print("✓ Fuji render verified successfully.")

if __name__ == "__main__":
    unittest.main()
