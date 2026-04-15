"""Unit tests for auth utility functions (no DB or network needed)."""

import pytest
from app.core.auth import hash_password, verify_password, generate_api_key


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("mysecretpassword")
        assert h != "mysecretpassword"

    def test_verify_correct_password(self):
        h = hash_password("correct-horse-battery")
        assert verify_password("correct-horse-battery", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correct-horse-battery")
        assert verify_password("wrong-password", h) is False

    def test_each_hash_is_unique(self):
        # bcrypt salts each hash - same password produces different hashes
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2
        # But both should verify
        assert verify_password("samepassword", h1)
        assert verify_password("samepassword", h2)


class TestGenerateApiKey:
    def test_length_is_32(self):
        key = generate_api_key()
        assert len(key) == 32

    def test_is_hex(self):
        key = generate_api_key()
        int(key, 16)  # raises ValueError if not hex

    def test_each_key_is_unique(self):
        keys = {generate_api_key() for _ in range(20)}
        assert len(keys) == 20
