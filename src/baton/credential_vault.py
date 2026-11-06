"""Encrypted, per-Windows-user storage for local API credentials."""

from __future__ import annotations

import ctypes
import base64
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MASTER_KEY_TARGET = "Baton/ApiCredentialVault/MasterKey/v1"
MASTER_KEY_BYTES = 32
NONCE_BYTES = 12
FORMAT_VERSION = 1
MAX_SECRET_BYTES = 4096
PROVIDERS = {
    "generic": "별칭으로 관리",
    "molit_rental": "국토교통부 아파트 전월세 실거래가",
    "molit_trade": "국토교통부 아파트 매매 실거래가",
    "molit_trade_detail": "국토교통부 아파트 매매 실거래가 상세",
    "kakao_local": "Kakao Local",
    "seoul_open_data": "서울 열린데이터광장",
}


class CredentialVaultError(Exception):
    """Safe-to-display credential vault error; never contains secret input."""


class CredentialValidationError(CredentialVaultError):
    pass


class CredentialNotFound(CredentialVaultError):
    pass


class CredentialConfirmationRequired(CredentialVaultError):
    pass


class CredentialContentsChanged(CredentialVaultError):
    pass


class SecureStorageUnavailable(CredentialVaultError):
    pass


class VaultStorageError(CredentialVaultError):
    pass


class MasterKeyStore(Protocol):
    def read(self) -> bytes | None: ...
    def write(self, value: bytes) -> None: ...
    def delete(self) -> None: ...


def default_vault_path() -> Path:
    """Return the user-local database path, never a project-relative fallback."""
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "Baton"
        return root / "credentials.sqlite3"
    if os.name != "nt":
        raise SecureStorageUnavailable("운영체제의 보안 자격증명 저장소가 필요합니다.")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise SecureStorageUnavailable("Windows user-local storage is unavailable.")
    root = Path(local_app_data).expanduser()
    if not root.is_absolute():
        raise SecureStorageUnavailable("Windows user-local storage is unavailable.")
    return root / "Baton" / "credentials.sqlite3"


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class _CREDENTIAL_ATTRIBUTEW(ctypes.Structure):
    _fields_ = [
        ("Keyword", ctypes.c_wchar_p),
        ("Flags", ctypes.c_uint32),
        ("ValueSize", ctypes.c_uint32),
        ("Value", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.POINTER(_CREDENTIAL_ATTRIBUTEW)),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


class WindowsCredentialManager:
    """Narrow wrapper around the current Windows user's generic credential store."""

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self, target: str = MASTER_KEY_TARGET) -> None:
        if sys.platform != "win32":
            raise SecureStorageUnavailable("Windows Credential Manager is unavailable on this platform.")
        self._target = target
        try:
            self._advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
            self._cred_read = self._advapi.CredReadW
            self._cred_read.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.POINTER(ctypes.POINTER(_CREDENTIALW))]
            self._cred_read.restype = ctypes.c_int
            self._cred_write = self._advapi.CredWriteW
            self._cred_write.argtypes = [ctypes.POINTER(_CREDENTIALW), ctypes.c_uint32]
            self._cred_write.restype = ctypes.c_int
            self._cred_delete = self._advapi.CredDeleteW
            self._cred_delete.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
            self._cred_delete.restype = ctypes.c_int
            self._cred_free = self._advapi.CredFree
            self._cred_free.argtypes = [ctypes.c_void_p]
            self._cred_free.restype = None
        except (AttributeError, OSError) as exc:
            raise SecureStorageUnavailable("Windows Credential Manager could not be initialized.") from exc

    def read(self) -> bytes | None:
        pointer = ctypes.POINTER(_CREDENTIALW)()
        if not self._cred_read(self._target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == self.ERROR_NOT_FOUND:
                return None
            raise SecureStorageUnavailable(f"Windows Credential Manager read failed ({error}).")
        try:
            credential = pointer.contents
            if credential.CredentialBlobSize > 4096 or not credential.CredentialBlob:
                raise SecureStorageUnavailable("Windows Credential Manager returned an invalid master key.")
            return ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        finally:
            self._cred_free(pointer)

    def write(self, value: bytes) -> None:
        if not isinstance(value, bytes) or not value:
            raise SecureStorageUnavailable("Invalid master key material.")
        blob = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
        credential = _CREDENTIALW()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = self._target
        credential.Comment = "BATON encrypted API credential vault key"
        credential.CredentialBlobSize = len(value)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "Baton"
        if not self._cred_write(ctypes.byref(credential), 0):
            error = ctypes.get_last_error()
            raise SecureStorageUnavailable(f"Windows Credential Manager write failed ({error}).")

    def delete(self) -> None:
        if not self._cred_delete(self._target, self.CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error != self.ERROR_NOT_FOUND:
                raise SecureStorageUnavailable(f"Windows Credential Manager delete failed ({error}).")


class MacOSKeychain:
    """Store only the vault master key in the current user's macOS Keychain."""

    def __init__(self, target: str = MASTER_KEY_TARGET) -> None:
        if sys.platform != "darwin":
            raise SecureStorageUnavailable("macOS Keychain을 사용할 수 없는 환경입니다.")
        try:
            import keyring
            from keyring.backends.macOS import Keyring

            backend = Keyring()
            if not backend.priority:
                raise RuntimeError("Keychain backend is unavailable")
            self._keyring = keyring
            self._backend = backend
        except Exception as exc:
            raise SecureStorageUnavailable("macOS Keychain을 사용할 수 없습니다.") from exc
        self._target = target

    def read(self) -> bytes | None:
        try:
            encoded = self._keyring.get_password(self._target, "Baton", backend=self._backend)
            return base64.b64decode(encoded, validate=True) if encoded is not None else None
        except Exception as exc:
            raise SecureStorageUnavailable("macOS Keychain에서 암호화 키를 읽을 수 없습니다.") from exc

    def write(self, value: bytes) -> None:
        if not isinstance(value, bytes) or not value:
            raise SecureStorageUnavailable("Invalid master key material.")
        try:
            encoded = base64.b64encode(value).decode("ascii")
            self._keyring.set_password(self._target, "Baton", encoded, backend=self._backend)
        except Exception as exc:
            raise SecureStorageUnavailable("macOS Keychain에 암호화 키를 저장할 수 없습니다.") from exc

    def delete(self) -> None:
        try:
            self._keyring.delete_password(self._target, "Baton", backend=self._backend)
        except self._keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:
            raise SecureStorageUnavailable("macOS Keychain에서 암호화 키를 삭제할 수 없습니다.") from exc


class CredentialVault:
    """Local metadata DB and AES-256-GCM secrets, with a separate OS-held master key."""

    def __init__(self, path: Path | str | None = None, key_store: MasterKeyStore | None = None) -> None:
        self.path = Path(path) if path is not None else default_vault_path()
        if key_store is not None:
            self.key_store = key_store
        elif sys.platform == "darwin":
            self.key_store = MacOSKeychain()
        else:
            self.key_store = WindowsCredentialManager()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA secure_delete = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            return connection
        except sqlite3.Error as exc:
            raise VaultStorageError("자격증명 저장소를 열 수 없습니다.") from exc

    def _initialize(self) -> None:
        try:
            if self.path.exists() and self.path.is_symlink():
                raise VaultStorageError("자격증명 저장소 경로가 안전하지 않습니다.")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = self._connect()
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    raise VaultStorageError("지원하지 않는 자격증명 저장소 형식입니다.")
                connection.execute("PRAGMA journal_mode = DELETE")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS credential_folders (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS credentials (
                        id TEXT PRIMARY KEY,
                        folder_id TEXT NOT NULL REFERENCES credential_folders(id) ON DELETE CASCADE,
                        provider_id TEXT NOT NULL,
                        alias TEXT NOT NULL,
                        nonce BLOB NOT NULL CHECK(length(nonce) = 12),
                        ciphertext BLOB NOT NULL,
                        format_version INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_credentials_folder
                        ON credentials(folder_id, provider_id, alias);
                    PRAGMA user_version = 1;
                    """
                )
            finally:
                connection.close()
        except VaultStorageError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise VaultStorageError("자격증명 저장소를 초기화할 수 없습니다.") from exc

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _validate_name(value: object, *, kind: str, maximum: int) -> str:
        if not isinstance(value, str):
            raise CredentialValidationError(f"{kind}을 입력해 주세요.")
        normalized = value.strip()
        if not normalized or len(normalized) > maximum:
            raise CredentialValidationError(f"{kind}은 1~{maximum}자여야 합니다.")
        if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
            raise CredentialValidationError(f"{kind}에 제어 문자를 사용할 수 없습니다.")
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise CredentialValidationError(f"{kind} 형식이 올바르지 않습니다.") from exc
        return normalized

    @classmethod
    def _validate_folder_name(cls, value: object) -> str:
        name = cls._validate_name(value, kind="폴더 이름", maximum=60)
        if "/" in name or "\\" in name or name in {".", ".."}:
            raise CredentialValidationError("폴더는 한 단계 이름만 사용할 수 있습니다.")
        return name

    @classmethod
    def _validate_alias(cls, value: object) -> str:
        return cls._validate_name(value, kind="별칭", maximum=80)

    @staticmethod
    def _validate_provider(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", value):
            raise CredentialValidationError("지원되는 형식의 공급자 ID를 입력해 주세요.")
        if value not in PROVIDERS:
            raise CredentialValidationError("지원하지 않는 API 공급자입니다.")
        return value

    @staticmethod
    def _validate_secret(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise CredentialValidationError("API 키를 입력해 주세요.")
        try:
            raw = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise CredentialValidationError("API 키 형식이 올바르지 않습니다.") from exc
        if len(raw) > MAX_SECRET_BYTES or b"\x00" in raw:
            raise CredentialValidationError("API 키 크기 또는 형식이 올바르지 않습니다.")
        return value

    @staticmethod
    def _validate_id(value: object) -> str:
        if not isinstance(value, str):
            raise CredentialNotFound("항목을 찾을 수 없습니다.")
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise CredentialNotFound("항목을 찾을 수 없습니다.") from exc
        if str(parsed) != value.lower():
            raise CredentialNotFound("항목을 찾을 수 없습니다.")
        return str(parsed)

    def _key_from_store(self) -> bytes | None:
        try:
            key = self.key_store.read()
        except SecureStorageUnavailable:
            raise
        except Exception as exc:
            raise SecureStorageUnavailable("운영체제 자격 증명 저장소를 사용할 수 없습니다.") from exc
        if key is not None and (not isinstance(key, bytes) or len(key) != MASTER_KEY_BYTES):
            raise SecureStorageUnavailable("저장된 암호화 키를 사용할 수 없습니다.")
        return key

    def _master_key_for_write(self, connection: sqlite3.Connection) -> bytes:
        key = self._key_from_store()
        if key is not None:
            return key
        has_secrets = connection.execute("SELECT 1 FROM credentials LIMIT 1").fetchone() is not None
        if has_secrets:
            raise SecureStorageUnavailable("기존 암호화 키를 찾을 수 없어 새 키 저장을 중단했습니다.")
        generated = AESGCM.generate_key(bit_length=256)
        try:
            self.key_store.write(generated)
            saved = self._key_from_store()
        except SecureStorageUnavailable:
            raise
        except Exception as exc:
            raise SecureStorageUnavailable("Windows 자격 증명 저장소에 암호화 키를 저장할 수 없습니다.") from exc
        if saved != generated:
            raise SecureStorageUnavailable("Windows 자격 증명 저장소의 암호화 키 확인에 실패했습니다.")
        return generated

    @staticmethod
    def _associated_data(credential_id: str, folder_id: str, provider_id: str) -> bytes:
        # Fixed AEAD context: vaults imported from Jipdam must stay decryptable.
        return f"jipdam-credential-v1\0{credential_id}\0{folder_id}\0{provider_id}".encode("utf-8")

    @classmethod
    def _encrypt(cls, key: bytes, credential_id: str, folder_id: str,
                 provider_id: str, secret: str) -> tuple[bytes, bytes]:
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(key).encrypt(
            nonce, secret.encode("utf-8"), cls._associated_data(credential_id, folder_id, provider_id)
        )
        return nonce, ciphertext

    @classmethod
    def _decrypt(cls, key: bytes, row: sqlite3.Row) -> str:
        if row["format_version"] != FORMAT_VERSION:
            raise SecureStorageUnavailable("암호화된 자격증명 형식을 지원하지 않습니다.")
        try:
            plaintext = AESGCM(key).decrypt(
                row["nonce"], row["ciphertext"],
                cls._associated_data(row["id"], row["folder_id"], row["provider_id"]),
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError, ValueError) as exc:
            raise SecureStorageUnavailable("자격증명을 복호화할 수 없습니다. 저장소 또는 암호화 키를 확인해 주세요.") from exc

    def create_folder(self, name: object) -> dict[str, str]:
        folder_name = self._validate_folder_name(name)
        folder_id = str(uuid.uuid4())
        created_at = self._now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO credential_folders(id, name, created_at) VALUES (?, ?, ?)",
                (folder_id, folder_name, created_at),
            )
            connection.execute("COMMIT")
            return {"id": folder_id, "name": folder_name, "created_at": created_at}
        except sqlite3.IntegrityError as exc:
            connection.execute("ROLLBACK")
            raise CredentialValidationError("같은 이름의 폴더가 이미 있습니다.") from exc
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise VaultStorageError("폴더를 저장할 수 없습니다.") from exc
        finally:
            connection.close()

    def list_state(self) -> dict[str, object]:
        connection = self._connect()
        try:
            # Counts and IDs shown in one confirmation must describe the same snapshot.
            connection.execute("BEGIN")
            folders = [dict(row) for row in connection.execute(
                "SELECT f.id, f.name, f.created_at, COUNT(c.id) AS credential_count "
                "FROM credential_folders f LEFT JOIN credentials c ON c.folder_id = f.id "
                "GROUP BY f.id ORDER BY f.name COLLATE NOCASE"
            )]
            rows = connection.execute(
                "SELECT c.id, c.folder_id, f.name AS folder_name, c.provider_id, c.alias, "
                "c.created_at, c.updated_at FROM credentials c "
                "JOIN credential_folders f ON f.id = c.folder_id "
                "ORDER BY f.name COLLATE NOCASE, c.alias COLLATE NOCASE, c.id"
            ).fetchall()
            key_count = len(rows)
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            raise VaultStorageError("보관함 목록을 읽을 수 없습니다.") from exc
        finally:
            connection.close()
        try:
            key = self._key_from_store()
            if key is None and key_count == 0:
                init_connection = self._connect()
                try:
                    init_connection.execute("BEGIN IMMEDIATE")
                    self._master_key_for_write(init_connection)
                    init_connection.execute("COMMIT")
                    key = self._key_from_store()
                except Exception:
                    if init_connection.in_transaction:
                        init_connection.execute("ROLLBACK")
                    raise
                finally:
                    init_connection.close()
            ready = key is not None
            message = "" if ready else "기존 암호화 키를 찾을 수 없어 등록된 키를 사용할 수 없습니다."
        except SecureStorageUnavailable:
            ready = False
            message = "운영체제 자격 증명 저장소를 사용할 수 없습니다. 키 저장과 복호화가 중단됩니다."
        credentials = [
            {
                "id": row["id"], "folder_id": row["folder_id"],
                "folder_name": row["folder_name"], "provider_id": row["provider_id"],
                "provider_name": PROVIDERS.get(row["provider_id"], row["provider_id"]),
                "alias": row["alias"], "created_at": row["created_at"],
                "updated_at": row["updated_at"], "masked": "••••••••",
            }
            for row in rows
        ]
        return {"folders": folders, "credentials": credentials,
                "secure_storage_ready": ready, "secure_storage_message": message}

    def add_credential(self, *, folder_id: object, provider_id: object = "generic",
                       alias: object, api_key: object) -> dict[str, str]:
        folder_key = self._validate_id(folder_id)
        provider = self._validate_provider(provider_id)
        display_alias = self._validate_alias(alias)
        secret = self._validate_secret(api_key)
        if secret in display_alias:
            raise CredentialValidationError("별칭에 API 키 값이 포함될 수 없습니다.")
        credential_id = str(uuid.uuid4())
        now = self._now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            folder = connection.execute("SELECT name FROM credential_folders WHERE id = ?", (folder_key,)).fetchone()
            if folder is None:
                raise CredentialNotFound("폴더를 찾을 수 없습니다.")
            if secret in folder["name"]:
                raise CredentialValidationError("폴더 이름에 API 키 값이 포함될 수 없습니다.")
            master_key = self._master_key_for_write(connection)
            nonce, ciphertext = self._encrypt(master_key, credential_id, folder_key, provider, secret)
            connection.execute(
                "INSERT INTO credentials(id, folder_id, provider_id, alias, nonce, ciphertext, "
                "format_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (credential_id, folder_key, provider, display_alias, nonce, ciphertext,
                 FORMAT_VERSION, now, now),
            )
            connection.execute("COMMIT")
            return {"id": credential_id, "folder_id": folder_key, "provider_id": provider,
                    "provider_name": PROVIDERS[provider], "alias": display_alias,
                    "created_at": now, "updated_at": now, "masked": "••••••••"}
        except CredentialVaultError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise VaultStorageError("API 키를 안전하게 저장할 수 없습니다.") from exc
        finally:
            connection.close()

    def update_credential(self, credential_id: object, *, alias: object | None = None,
                          api_key: object | None = None,
                          provider_id: object | None = None,
                          folder_id: object | None = None) -> dict[str, str]:
        key_id = self._validate_id(credential_id)
        if alias is None and api_key is None and provider_id is None and folder_id is None:
            raise CredentialValidationError("변경할 폴더, 별칭 또는 API 키를 입력해 주세요.")
        display_alias = self._validate_alias(alias) if alias is not None else None
        secret = self._validate_secret(api_key) if api_key is not None else None
        replacement_provider = self._validate_provider(provider_id) if provider_id is not None else None
        replacement_folder = self._validate_id(folder_id) if folder_id is not None else None
        now = self._now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM credentials WHERE id = ?", (key_id,)).fetchone()
            if row is None:
                raise CredentialNotFound("API 키를 찾을 수 없습니다.")
            old_key = self._key_from_store()
            if old_key is None:
                raise SecureStorageUnavailable("기존 암호화 키를 찾을 수 없습니다.")
            existing_secret = self._decrypt(old_key, row)
            updated_alias = display_alias if display_alias is not None else row["alias"]
            replacement_secret = secret if secret is not None else existing_secret
            updated_provider = replacement_provider if replacement_provider is not None else row["provider_id"]
            updated_folder = replacement_folder if replacement_folder is not None else row["folder_id"]
            if existing_secret in updated_alias or replacement_secret in updated_alias:
                raise CredentialValidationError("별칭에 API 키 값이 포함될 수 없습니다.")
            folder = connection.execute("SELECT name FROM credential_folders WHERE id = ?",
                                        (updated_folder,)).fetchone()
            if folder is None:
                raise CredentialNotFound("폴더를 찾을 수 없습니다.")
            folder_name = folder["name"]
            if existing_secret in folder_name or replacement_secret in folder_name:
                raise CredentialValidationError("폴더 이름에 API 키 값이 포함될 수 없습니다.")
            if secret is not None or updated_provider != row["provider_id"] or updated_folder != row["folder_id"]:
                nonce, ciphertext = self._encrypt(old_key, key_id, updated_folder, updated_provider, replacement_secret)
                connection.execute(
                    "UPDATE credentials SET folder_id = ?, provider_id = ?, alias = ?, nonce = ?, ciphertext = ?, updated_at = ? WHERE id = ?",
                    (updated_folder, updated_provider, updated_alias, nonce, ciphertext, now, key_id),
                )
            else:
                connection.execute("UPDATE credentials SET alias = ?, updated_at = ? WHERE id = ?",
                                   (updated_alias, now, key_id))
            connection.execute("COMMIT")
            return {"id": key_id, "folder_id": updated_folder, "provider_id": updated_provider,
                    "provider_name": PROVIDERS.get(updated_provider, updated_provider),
                    "alias": updated_alias, "created_at": row["created_at"],
                    "updated_at": now, "masked": "••••••••"}
        except CredentialVaultError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise VaultStorageError("API 키를 변경할 수 없습니다.") from exc
        finally:
            connection.close()

    def get_secret(self, credential_id: object, *, expected_provider_id: object | None = None) -> str:
        """Read an explicitly selected ID; retain optional legacy provider checks."""
        key_id = self._validate_id(credential_id)
        provider = self._validate_provider(expected_provider_id) if expected_provider_id is not None else None
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM credentials WHERE id = ?", (key_id,)).fetchone()
            if row is None or (provider is not None and row["provider_id"] != provider):
                raise CredentialNotFound("지정한 API 키를 찾을 수 없습니다.")
            key = self._key_from_store()
            if key is None:
                raise SecureStorageUnavailable("기존 암호화 키를 찾을 수 없습니다.")
            return self._decrypt(key, row)
        except CredentialVaultError:
            raise
        except sqlite3.Error as exc:
            raise VaultStorageError("API 키를 읽을 수 없습니다.") from exc
        finally:
            connection.close()

    def delete_credential(self, credential_id: object) -> None:
        key_id = self._validate_id(credential_id)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute("DELETE FROM credentials WHERE id = ?", (key_id,))
            if cursor.rowcount == 0:
                raise CredentialNotFound("API 키를 찾을 수 없습니다.")
            connection.execute("COMMIT")
        except CredentialVaultError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise VaultStorageError("API 키를 삭제할 수 없습니다.") from exc
        finally:
            connection.close()

    def delete_folder(self, folder_id: object, *, confirmed: object,
                      expected_credential_ids: list[str] | None = None) -> dict[str, int]:
        folder_key = self._validate_id(folder_id)
        if confirmed is not True:
            raise CredentialConfirmationRequired("폴더와 포함된 API 키 삭제 확인이 필요합니다.")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM credential_folders WHERE id = ?", (folder_key,)).fetchone() is None:
                raise CredentialNotFound("폴더를 찾을 수 없습니다.")
            current_ids = [row[0] for row in connection.execute("SELECT id FROM credentials WHERE folder_id = ?",
                                                               (folder_key,))]
            if expected_credential_ids is not None and sorted(expected_credential_ids) != sorted(current_ids):
                raise CredentialContentsChanged("폴더의 키 목록이 변경되었습니다. 새 목록을 확인하고 다시 삭제해 주세요.")
            count = len(current_ids)
            connection.execute("DELETE FROM credential_folders WHERE id = ?", (folder_key,))
            connection.execute("COMMIT")
            return {"deleted_credentials": count}
        except CredentialVaultError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise VaultStorageError("폴더와 포함된 API 키를 삭제할 수 없습니다.") from exc
        finally:
            connection.close()
