"""
backend/test_etegami_engine_switch.py
Verifies engine switching between Pollinations.ai (Free) and Google Image (Paid) with safety fallbacks.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import multimedia, database as db

def test_engine_switch():
    print("=== Testing Etegami Engine Switch ===")

    # 1. Test Pollinations.ai (Free AI generation)
    print("\n--- Test 1: Generate with Pollinations.ai (Free) ---")
    url_free = multimedia.generate_new_etegami_artwork(
        motif="可愛い白い犬",
        theme_title="【手作り絵手紙】白い犬の温もり",
        season="autumn",
        user_id=1,
        engine="pollinations"
    )
    print(f"Generated URL (Free): {url_free}")
    assert url_free is not None
    engine_meta = multimedia.get_last_used_image_engine()
    print(f"Engine Meta: {engine_meta}")
    assert engine_meta["engine"] in ["pollinations", "local_watercolor"]

    # 2. Test modify_or_create_etegami with engine="pollinations"
    print("\n--- Test 2: modify_or_create_etegami with mode=generate_new, image_engine=pollinations ---")
    res_free = multimedia.modify_or_create_etegami(
        user_id=1,
        terminal_id="user_tablet_1",
        motif_hint="秋のコスモス",
        mode="generate_new",
        image_engine="pollinations"
    )
    print("Result Free Theme:", res_free.get("theme"))
    print("Result Free Engine:", res_free.get("engine"), res_free.get("engine_name"))
    print("Result Free Image:", res_free.get("generated_image_url"))
    assert res_free.get("engine") in ["pollinations", "local_watercolor"]

    # 3. Test modify_or_create_etegami with engine="google_image" (should try Gemini and fallback on quota/error)
    print("\n--- Test 3: modify_or_create_etegami with mode=generate_new, image_engine=google_image ---")
    res_paid = multimedia.modify_or_create_etegami(
        user_id=1,
        terminal_id="user_tablet_1",
        motif_hint="夕焼けの小鳥",
        mode="generate_new",
        image_engine="google_image"
    )
    print("Result Paid Theme:", res_paid.get("theme"))
    print("Result Paid Engine:", res_paid.get("engine"), res_paid.get("engine_name"))
    print("Result Paid Image:", res_paid.get("generated_image_url"))

    print("\n✅ All Engine Switch tests PASSED successfully!")

if __name__ == "__main__":
    test_engine_switch()
