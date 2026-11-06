from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
import types
from pathlib import Path
from unittest.mock import patch

from baton.credential_vault import (
    CredentialConfirmationRequired,
    CredentialNotFound,
    CredentialValidationError,
    CredentialVault,
    SecureStorageUnavailable,
    VaultStorageError,
    WindowsCredentialManager,
    MacOSKeychain,
    default_vault_path,
)


class MemoryKeyStore:
    def __init__(self) -> None:
        self.value: bytes | None = None
        self.fail_read = False
        self.fail_write = False
        self.fail_delete = False

    def read(self) -> bytes | None:
        if self.fail_read:
            raise SecureStorageUnavailable("synthetic read failure")
        return self.value

    def write(self, value: bytes) -> None:
        if self.fail_write:
            raise SecureStorageUnavailable("synthetic write failure")
        self.value = value

    def delete(self) -> None:
        if self.fail_delete:
            raise SecureStorageUnavailable("synthetic delete failure")
        self.value = None


class CredentialVaultTests(unittest.TestCase):
    def test_macos_default_path_uses_application_support(self) -> None:
        with patch("baton.credential_vault.sys.platform", "darwin"), \
                patch("baton.credential_vault.Path.home", return_value=Path("/Users/test")):
            self.assertEqual(default_vault_path(), Path("/Users/test/Library/Application Support/Baton/credentials.sqlite3"))

    def test_macos_keychain_round_trip_uses_os_backend(self) -> None:
        values: dict[tuple[str, str], str] = {}

        class FakeBackend:
            priority = 1

        class FakeErrors:
            class PasswordDeleteError(Exception):
                pass

        fake_keyring = types.ModuleType("keyring")
        fake_keyring.get_password = lambda service, username, backend=None: values.get((service, username))
        fake_keyring.set_password = lambda service, username, password, backend=None: values.__setitem__((service, username), password)
        fake_keyring.delete_password = lambda service, username, backend=None: values.pop((service, username))
        fake_keyring.errors = FakeErrors
        fake_backend_module = types.ModuleType("keyring.backends.macOS")
        fake_backend_module.Keyring = FakeBackend
        with patch("baton.credential_vault.sys.platform", "darwin"), \
                patch.dict("sys.modules", {"keyring": fake_keyring, "keyring.backends": types.ModuleType("keyring.backends"),
                                            "keyring.backends.macOS": fake_backend_module}):
            store = MacOSKeychain()
            store.write(b"synthetic-master-key")
            self.assertEqual(store.read(), b"synthetic-master-key")
            store.delete()
            self.assertIsNone(store.read())

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "credentials.sqlite3"
        self.key_store = MemoryKeyStore()
        self.vault = CredentialVault(self.path, self.key_store)

    def add_folder(self, name: str = "공공 API") -> str:
        return self.vault.create_folder(name)["id"]

    def add_key(self, folder_id: str, alias: str, secret: str, provider: str = "kakao_local") -> dict[str, str]:
        return self.vault.add_credential(folder_id=folder_id, provider_id=provider,
                                         alias=alias, api_key=secret)

    def test_multiple_keys_aliases_and_metadata_survive_reopen(self) -> None:
        folder_id = self.add_folder()
        first_secret = "synthetic-kakao-key-A"
        second_secret = "synthetic-kakao-key-B"
        first = self.add_key(folder_id, "개발용", first_secret)
        second = self.add_key(folder_id, "검증용", second_secret)

        reopened = CredentialVault(self.path, self.key_store)
        state = reopened.list_state()
        self.assertEqual(len(state["folders"]), 1)
        self.assertEqual(state["folders"][0]["credential_count"], 2)
        self.assertEqual({row["alias"] for row in state["credentials"]}, {"개발용", "검증용"})
        self.assertNotIn(first_secret, repr(state))
        self.assertNotIn(second_secret, repr(state))
        self.assertEqual(reopened.get_secret(first["id"], expected_provider_id="kakao_local"), first_secret)
        self.assertEqual(reopened.get_secret(second["id"], expected_provider_id="kakao_local"), second_secret)

    def test_alias_only_registration_and_legacy_folder_move_preserve_secret(self) -> None:
        folder = self.add_folder()
        destination = self.add_folder("공공데이터 API")
        new_key = self.vault.add_credential(folder_id=destination, alias="공공데이터 공통 인증키",
                                            api_key="synthetic-generic-key")
        legacy = self.add_key(folder, "이전 키", "synthetic-legacy-key", "molit_rental")
        moved = self.vault.update_credential(legacy["id"], alias="국토부 공통 키", folder_id=destination)
        reopened = CredentialVault(self.path, self.key_store)
        self.assertEqual(reopened.get_secret(new_key["id"]), "synthetic-generic-key")
        self.assertEqual(reopened.get_secret(legacy["id"]), "synthetic-legacy-key")
        self.assertEqual(moved["folder_id"], destination)
        self.assertEqual(moved["provider_id"], "molit_rental")
        counts = {f["id"]: f["credential_count"] for f in reopened.list_state()["folders"]}
        self.assertEqual(counts, {folder: 0, destination: 2})

    def test_invalid_folder_move_rolls_back_and_does_not_expose_secret(self) -> None:
        folder = self.add_folder()
        secret = "synthetic-move-secret"
        key = self.add_key(folder, "기존 별칭", secret)
        with self.assertRaises(CredentialNotFound):
            self.vault.update_credential(key["id"], folder_id=str(uuid.uuid4()), alias="변경 별칭")
        unsafe_folder = self.add_folder(secret)
        with self.assertRaises(CredentialValidationError):
            self.vault.update_credential(key["id"], folder_id=unsafe_folder)
        state = self.vault.list_state()["credentials"][0]
        self.assertEqual((state["folder_id"], state["alias"]), (folder, "기존 별칭"))
        self.assertEqual(self.vault.get_secret(key["id"]), secret)

    def test_database_contains_ciphertext_not_plaintext_and_provider_is_bound(self) -> None:
        folder_id = self.add_folder()
        secret = "synthetic-secret-value-not-for-production"
        credential = self.add_key(folder_id, "테스트 키", secret)
        database_bytes = self.path.read_bytes()
        self.assertNotIn(secret.encode(), database_bytes)
        self.assertNotIn(secret, repr(self.vault.list_state()))
        with self.assertRaises(CredentialNotFound):
            self.vault.get_secret(credential["id"], expected_provider_id="molit_rental")

    def test_ciphertext_tampering_fails_closed(self) -> None:
        folder_id = self.add_folder()
        credential = self.add_key(folder_id, "테스트 키", "synthetic-secret")
        connection = sqlite3.connect(self.path)
        with connection:
            ciphertext = bytearray(connection.execute(
                "SELECT ciphertext FROM credentials WHERE id = ?", (credential["id"],)
            ).fetchone()[0])
            ciphertext[0] ^= 0x01
            connection.execute("UPDATE credentials SET ciphertext = ? WHERE id = ?",
                               (bytes(ciphertext), credential["id"]))
        connection.close()
        with self.assertRaisesRegex(SecureStorageUnavailable, "복호화할 수 없습니다"):
            self.vault.get_secret(credential["id"], expected_provider_id="kakao_local")

    def test_missing_master_key_with_existing_credentials_never_replaces_it(self) -> None:
        folder_id = self.add_folder()
        self.add_key(folder_id, "기존 키", "synthetic-existing-secret")
        self.key_store.value = None
        with self.assertRaisesRegex(SecureStorageUnavailable, "새 키 저장을 중단"):
            self.add_key(folder_id, "새 키", "synthetic-new-secret")
        state = self.vault.list_state()
        self.assertFalse(state["secure_storage_ready"])
        self.assertEqual(len(state["credentials"]), 1)
        self.assertIsNone(self.key_store.value)

    def test_unavailable_or_failing_os_store_never_writes_plaintext_or_rows(self) -> None:
        folder_id = self.add_folder()
        self.key_store.fail_write = True
        secret = "synthetic-secret-never-persisted"
        with self.assertRaises(SecureStorageUnavailable):
            self.add_key(folder_id, "저장 실패", secret)
        self.assertEqual(self.vault.list_state()["credentials"], [])
        self.assertNotIn(secret.encode(), self.path.read_bytes())

        self.key_store.fail_write = False
        self.key_store.fail_read = True
        with self.assertRaises(SecureStorageUnavailable):
            self.add_key(folder_id, "저장소 읽기 실패", secret)
        self.assertEqual(self.vault.list_state()["credentials"], [])

    def test_replacement_and_alias_edit_change_only_selected_credential(self) -> None:
        folder_id = self.add_folder()
        first = self.add_key(folder_id, "첫 키", "synthetic-secret-A")
        second = self.add_key(folder_id, "둘째 키", "synthetic-secret-B")
        updated = self.vault.update_credential(first["id"], alias="교체 키",
                                               api_key="synthetic-secret-A2")
        self.assertEqual(updated["alias"], "교체 키")
        self.assertEqual(self.vault.get_secret(first["id"], expected_provider_id="kakao_local"),
                         "synthetic-secret-A2")
        self.assertEqual(self.vault.get_secret(second["id"], expected_provider_id="kakao_local"),
                         "synthetic-secret-B")
        renamed = self.vault.update_credential(second["id"], alias="둘째 키 이름 변경")
        self.assertEqual(renamed["alias"], "둘째 키 이름 변경")

    def test_provider_can_be_changed_and_secret_is_reencrypted(self) -> None:
        folder_id = self.add_folder()
        key = self.add_key(folder_id, "서울 검색", "synthetic-provider-bound-key", "kakao_local")
        updated = self.vault.update_credential(key["id"], provider_id="seoul_open_data")
        self.assertEqual(updated["provider_id"], "seoul_open_data")
        self.assertEqual(updated["alias"], "서울 검색")
        self.assertEqual(self.vault.get_secret(key["id"], expected_provider_id="seoul_open_data"),
                         "synthetic-provider-bound-key")
        with self.assertRaises(CredentialNotFound):
            self.vault.get_secret(key["id"], expected_provider_id="kakao_local")
        self.assertEqual(self.vault.list_state()["credentials"][0]["folder_id"], folder_id)

    def test_alias_cannot_echo_secret_in_responses_or_state(self) -> None:
        folder_id = self.add_folder()
        secret = "synthetic-secret-that-must-not-be-a-label"
        with self.assertRaisesRegex(CredentialValidationError, "별칭에 API 키 값"):
            self.add_key(folder_id, f"개발 {secret} 별칭", secret)
        self.assertEqual(self.vault.list_state()["credentials"], [])

    def test_folder_delete_requires_confirmation_and_cascades(self) -> None:
        folder_id = self.add_folder()
        first = self.add_key(folder_id, "첫 키", "synthetic-secret-A")
        self.add_key(folder_id, "둘째 키", "synthetic-secret-B", "molit_rental")
        with self.assertRaises(CredentialConfirmationRequired):
            self.vault.delete_folder(folder_id, confirmed=False)
        self.assertEqual(len(self.vault.list_state()["credentials"]), 2)
        result = self.vault.delete_folder(folder_id, confirmed=True)
        self.assertEqual(result, {"deleted_credentials": 2})
        self.assertEqual(self.vault.list_state()["folders"], [])
        self.assertEqual(self.vault.list_state()["credentials"], [])
        with self.assertRaises(CredentialNotFound):
            self.vault.get_secret(first["id"], expected_provider_id="kakao_local")

    def test_folder_delete_database_failure_rolls_back_folder_and_all_keys(self) -> None:
        folder_id = self.add_folder()
        self.add_key(folder_id, "첫 키", "synthetic-secret-A")
        self.add_key(folder_id, "둘째 키", "synthetic-secret-B")
        connection = sqlite3.connect(self.path)
        connection.execute(
            "CREATE TRIGGER reject_credential_delete BEFORE DELETE ON credentials "
            "BEGIN SELECT RAISE(ABORT, 'synthetic rollback'); END"
        )
        connection.commit()
        connection.close()
        with self.assertRaises(VaultStorageError):
            self.vault.delete_folder(folder_id, confirmed=True)
        state = self.vault.list_state()
        self.assertEqual(len(state["folders"]), 1)
        self.assertEqual(len(state["credentials"]), 2)

    def test_empty_folder_delete_and_individual_key_delete(self) -> None:
        empty_id = self.add_folder("빈 폴더")
        self.assertEqual(self.vault.delete_folder(empty_id, confirmed=True), {"deleted_credentials": 0})
        folder_id = self.add_folder()
        credential = self.add_key(folder_id, "삭제 대상", "synthetic-secret")
        self.vault.delete_credential(credential["id"])
        self.assertEqual(self.vault.list_state()["credentials"], [])
        self.assertEqual(self.vault.list_state()["folders"][0]["credential_count"], 0)

    def test_provider_and_field_validation_are_strict(self) -> None:
        folder_id = self.add_folder()
        with self.assertRaises(CredentialValidationError):
            self.add_key(folder_id, "키", "synthetic-secret", provider="unknown_provider")
        with self.assertRaises(CredentialValidationError):
            self.vault.create_folder("../outside")
        with self.assertRaises(CredentialValidationError):
            self.add_key(folder_id, "", "synthetic-secret")
        with self.assertRaises(CredentialValidationError):
            self.add_key(folder_id, "키", "\x00")

    def test_default_path_is_user_local_and_has_no_project_fallback(self) -> None:
        if os.name == "nt":
            old = os.environ.get("LOCALAPPDATA")
            try:
                os.environ["LOCALAPPDATA"] = str(Path(self.temp.name) / "Local App Data")
                self.assertEqual(default_vault_path(), Path(self.temp.name) / "Local App Data" / "Baton" / "credentials.sqlite3")
                os.environ.pop("LOCALAPPDATA", None)
                with self.assertRaises(SecureStorageUnavailable):
                    default_vault_path()
            finally:
                if old is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old
        else:
            with self.assertRaises(SecureStorageUnavailable):
                default_vault_path()

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager integration only")
    def test_native_credential_manager_round_trip_uses_synthetic_key(self) -> None:
        target = f"Baton/Test/CredentialVault/{uuid.uuid4()}"
        store = WindowsCredentialManager(target=target)
        synthetic_key = b"S" * 32
        try:
            self.assertIsNone(store.read())
            try:
                store.write(synthetic_key)
            except SecureStorageUnavailable as exc:
                if "1312" in str(exc):
                    self.skipTest("the managed test session has no Windows logon credential session")
                raise
            self.assertEqual(store.read(), synthetic_key)
        finally:
            store.delete()
        self.assertIsNone(store.read())


if __name__ == "__main__":
    unittest.main()
