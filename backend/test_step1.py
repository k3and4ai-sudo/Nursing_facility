import unittest
import os
import sys

# Ensure backend folder is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import hash_password, verify_password
import backend.database as db

class TestStep1AuthAndRoles(unittest.TestCase):

    def setUp(self):
        # Setup temporary test database
        db.DB_PATH = "test_step1_auth.db"
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
        db.db_init()

    def tearDown(self):
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)

    def test_password_hashing_and_verification(self):
        """Test SHA-256 salted password hashing and verification."""
        password = "mySecretPassword123"
        pwd_hash, salt = hash_password(password)
        
        self.assertNotEqual(password, pwd_hash)
        self.assertTrue(len(salt) > 0)
        self.assertTrue(verify_password(password, pwd_hash, salt))
        self.assertFalse(verify_password("wrongPassword", pwd_hash, salt))

    def test_demo_account_seeding(self):
        """Test that default demo accounts for all 4 roles are seeded."""
        roles_to_check = ["staff", "patient", "family", "barber"]
        user_codes = ["staff01", "patient01", "family01", "barber01"]
        passwords = ["staff123", "patient123", "family123", "barber123"]

        for user_code, password, expected_role in zip(user_codes, passwords, roles_to_check):
            acc = db.authenticate_user_account(user_code, password)
            self.assertIsNotNone(acc, f"Failed to authenticate seeded user: {user_code}")
            self.assertEqual(acc["role"], expected_role)
            self.assertTrue(len(acc["name"]) > 0)

    def test_invalid_login(self):
        """Test that invalid user code or password is rejected."""
        acc_invalid_pass = db.authenticate_user_account("staff01", "wrongPassword")
        self.assertIsNone(acc_invalid_pass)

        acc_invalid_user = db.authenticate_user_account("nonexistent_user", "staff123")
        self.assertIsNone(acc_invalid_user)

    def test_custom_account_and_group(self):
        """Test creating a custom user account and binding it to a group."""
        patient_id = db.add_user("高橋 健太", 78, "303", "tablet_303", "none", "", "")
        group_id = db.add_group("高橋様ケアグループ", patient_id)

        user_acc_id = db.add_user_account(
            user_code="family_takahashi",
            password="passTakahashi",
            role="family",
            name="高橋 次郎 (ご男児)",
            group_id=group_id
        )
        self.assertTrue(user_acc_id > 0)

        acc = db.authenticate_user_account("family_takahashi", "passTakahashi")
        self.assertIsNotNone(acc)
        self.assertEqual(acc["role"], "family")
        self.assertEqual(acc["group_id"], group_id)
        self.assertEqual(acc["name"], "高橋 次郎 (ご男児)")

if __name__ == "__main__":
    unittest.main()
