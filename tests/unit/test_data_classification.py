import pytest

from odap.infra.security.data_classification import (
    DataClassification,
    CLASSIFICATION_LABELS,
    CLASSIFICATION_HIERARCHY,
    can_access,
)


class TestDataClassification:
    def test_enum_values(self):
        assert DataClassification.TS.value == "TS"
        assert DataClassification.S.value == "S"
        assert DataClassification.C.value == "C"
        assert DataClassification.U.value == "U"

    def test_str_enum(self):
        assert DataClassification.TS == "TS"
        assert isinstance(DataClassification.U, str)

    def test_labels(self):
        assert CLASSIFICATION_LABELS[DataClassification.TS] == "Top Secret"
        assert CLASSIFICATION_LABELS[DataClassification.S] == "Secret"
        assert CLASSIFICATION_LABELS[DataClassification.C] == "Confidential"
        assert CLASSIFICATION_LABELS[DataClassification.U] == "Unclassified"

    def test_hierarchy(self):
        assert CLASSIFICATION_HIERARCHY[DataClassification.TS] > CLASSIFICATION_HIERARCHY[DataClassification.S]
        assert CLASSIFICATION_HIERARCHY[DataClassification.S] > CLASSIFICATION_HIERARCHY[DataClassification.C]
        assert CLASSIFICATION_HIERARCHY[DataClassification.C] > CLASSIFICATION_HIERARCHY[DataClassification.U]


class TestCanAccess:
    def test_ts_can_access_all(self):
        assert can_access(DataClassification.TS, DataClassification.TS) is True
        assert can_access(DataClassification.TS, DataClassification.S) is True
        assert can_access(DataClassification.TS, DataClassification.C) is True
        assert can_access(DataClassification.TS, DataClassification.U) is True

    def test_u_can_only_access_u(self):
        assert can_access(DataClassification.U, DataClassification.U) is True
        assert can_access(DataClassification.U, DataClassification.C) is False
        assert can_access(DataClassification.U, DataClassification.S) is False
        assert can_access(DataClassification.U, DataClassification.TS) is False

    def test_s_can_access_s_and_below(self):
        assert can_access(DataClassification.S, DataClassification.S) is True
        assert can_access(DataClassification.S, DataClassification.C) is True
        assert can_access(DataClassification.S, DataClassification.U) is True
        assert can_access(DataClassification.S, DataClassification.TS) is False

    def test_c_can_access_c_and_below(self):
        assert can_access(DataClassification.C, DataClassification.C) is True
        assert can_access(DataClassification.C, DataClassification.U) is True
        assert can_access(DataClassification.C, DataClassification.S) is False
        assert can_access(DataClassification.C, DataClassification.TS) is False


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            has_crypto = True
        except ImportError:
            has_crypto = False

        from odap.infra.security.encryption import generate_key, encrypt_field, decrypt_field

        key = generate_key()
        assert len(key) == 32

        original = "sensitive data"
        encrypted = encrypt_field(original, key)
        assert "encrypted" in encrypted
        assert "nonce" in encrypted
        assert "tag" in encrypted

        if has_crypto:
            decrypted = decrypt_field(
                encrypted["encrypted"], key, encrypted["nonce"], encrypted["tag"]
            )
            assert decrypted == original
        else:
            assert encrypted.get("fallback") is True

    def test_generate_key_length(self):
        from odap.infra.security.encryption import generate_key
        key = generate_key()
        assert len(key) == 32

    def test_encrypt_different_nonce_each_time(self):
        from odap.infra.security.encryption import generate_key, encrypt_field
        key = generate_key()
        e1 = encrypt_field("test", key)
        e2 = encrypt_field("test", key)
        assert e1["nonce"] != e2["nonce"]
