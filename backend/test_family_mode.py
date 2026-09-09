import unittest
import json
import base64
import os
import hashlib
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.main import app, _get_family_shared_key
import backend.database as db

class TestFamilyMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.db_init()
        cls.client = TestClient(app)

    def test_01_my_patient_authorized(self):
        """Verify family01 can access their designated patient data."""
        res = self.client.get("/api/family/my_patient?user_code=family01")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("patient", data)
        self.assertIn("vitals", data)
        self.assertIn("vitals_chronological", data)
        self.assertIn("recent_multimedia", data)
        self.assertEqual(data["family_user"]["user_code"], "family01")
        print("✓ Authorized family member access test PASSED (Patient:", data["patient"]["name"], ")")

    def test_02_group_access_control_forbidden(self):
        """Verify access is denied if user_code is invalid or lacks access to target patient."""
        # Non-existent user
        res_invalid = self.client.get("/api/family/my_patient?user_code=unknown_user")
        self.assertEqual(res_invalid.status_code, 401)

        # Cross-patient summary check with wrong family account
        res_cross = self.client.get("/api/family/patient_summary/99999?user_code=family01")
        self.assertEqual(res_cross.status_code, 403)
        print("✓ Group boundary 403 / 401 security access control test PASSED")

    def test_03_visitation_reservation_crud(self):
        """Verify creating and retrieving visitation reservations."""
        # Fetch current family patient id
        info = self.client.get("/api/family/my_patient?user_code=family01").json()
        patient_id = info["patient"]["id"]

        # Create a new reservation
        payload = {
            "patient_id": patient_id,
            "user_code": "family01",
            "visit_datetime": "2026-09-12 15:30",
            "visitors_count": 3,
            "message": "家族3名で伺います。アルバムを持参します。"
        }
        res_create = self.client.post("/api/family/reservations", json=payload)
        self.assertEqual(res_create.status_code, 200)
        create_data = res_create.json()
        self.assertEqual(create_data["status"], "success")
        res_id = create_data["reservation_id"]

        # Fetch reservations list
        res_list = self.client.get("/api/family/reservations?user_code=family01")
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json()
        self.assertTrue(any(r["id"] == res_id for r in items))
        created_item = [r for r in items if r["id"] == res_id][0]
        self.assertEqual(created_item["visitors_count"], 3)
        self.assertEqual(created_item["message"], "家族3名で伺います。アルバムを持参します。")
        print("✓ Visitation reservation creation & group retrieval test PASSED (ID:", res_id, ")")

    def test_04_aes_256_gcm_remote_sync(self):
        """Verify AES-256-GCM secure encrypted packet synchronization for remote access."""
        info = self.client.get("/api/family/my_patient?user_code=family01").json()
        patient_id = info["patient"]["id"]

        # Client-side encryption
        key = _get_family_shared_key("family01")
        aesgcm = AESGCM(key)
        client_payload = {"patient_id": patient_id, "timestamp": "2026-09-08T16:20:00"}
        payload_bytes = json.dumps(client_payload).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, payload_bytes, None)

        sync_req = {
            "user_code": "family01",
            "nonce_b64": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("utf-8")
        }

        res = self.client.post("/api/family/sync_encrypted", json=sync_req)
        self.assertEqual(res.status_code, 200)
        resp_data = res.json()
        self.assertEqual(resp_data["status"], "success")
        self.assertEqual(resp_data["algorithm"], "AES-256-GCM")

        # Client-side decryption of response
        resp_nonce = base64.b64decode(resp_data["resp_nonce_b64"])
        resp_ciphertext = base64.b64decode(resp_data["resp_ciphertext_b64"])
        decrypted_resp = aesgcm.decrypt(resp_nonce, resp_ciphertext, None)
        decrypted_json = json.loads(decrypted_resp.decode("utf-8"))

        self.assertIn("patient", decrypted_json)
        self.assertEqual(decrypted_json["patient"]["id"], patient_id)
        print("✓ AES-256-GCM remote sync encryption/decryption roundtrip PASSED")

    def test_05_multimedia_postcard_synthesis_and_seasons(self):
        """Verify dynamic seasonal postcard switching and conversational synthesis."""
        # 1. Templates list endpoint
        res_tpl = self.client.get("/api/family/postcard_templates")
        self.assertEqual(res_tpl.status_code, 200)
        templates = res_tpl.json().get("templates", [])
        self.assertEqual(len(templates), 4)
        season_keys = [t["key"] for t in templates]
        self.assertIn("spring", season_keys)
        self.assertIn("summer", season_keys)
        self.assertIn("autumn", season_keys)
        self.assertIn("winter", season_keys)

        # 2. Query with specific season
        res_spring = self.client.get("/api/family/my_patient?user_code=family01&season=spring")
        self.assertEqual(res_spring.status_code, 200)
        data_spring = res_spring.json()
        multimedia = data_spring["recent_multimedia"]
        self.assertEqual(multimedia["card_season"], "spring")
        self.assertEqual(multimedia["card_image_url"], "/family/assets/sample_postcard_spring.jpg")
        self.assertIn(data_spring["patient"]["name"], multimedia["card_title"])
        self.assertTrue(len(multimedia["summary_text"]) > 10)
        print("✓ Seasonal digital postcard dynamic synthesis test PASSED")

    def test_06_image_prompt_extraction_and_api(self):
        """Verify image generation JSON extraction and retrieval endpoint."""
        res = self.client.get("/api/family/multimedia/image_prompt/user_tablet_1")
        self.assertEqual(res.status_code, 200)
        json_data = res.json()
        self.assertEqual(json_data["status"], "success")
        data = json_data["data"]
        self.assertIn("image_generation_prompt", data)
        self.assertIn("positive_prompt", data["image_generation_prompt"])
        self.assertIn("postcard_metadata", data)
        self.assertIn("headline", data["postcard_metadata"])
        print(f"✓ Image generation JSON extraction & retrieval PASSED (Theme: '{data.get('theme')}')")

if __name__ == "__main__":
    unittest.main()
