"""One-time copy of the Jipdam vault and GMS ledger into BATON. The original is never changed."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

from .credential_vault import (MASTER_KEY_BYTES, CredentialVault, CredentialVaultError, MacOSKeychain, MasterKeyStore,
                               WindowsCredentialManager, default_vault_path)

LEGACY_MASTER_KEY_TARGET = "Jipdam/ApiCredentialVault/MasterKey/v1"
BUDGET_NAME = "gms-budget.sqlite3"


def legacy_vault_path() -> Path:
    return default_vault_path().parent.parent / "Jipdam" / "credentials.sqlite3"


def _legacy_key_store() -> MasterKeyStore:
    kind = MacOSKeychain if sys.platform == "darwin" else WindowsCredentialManager
    return kind(LEGACY_MASTER_KEY_TARGET)


def _default_key_store() -> MasterKeyStore:
    return MacOSKeychain() if sys.platform == "darwin" else WindowsCredentialManager()


def _rows(path: Path, query: str) -> int:
    """Count rows in an existing DB; a missing DB or table holds nothing to protect."""
    if not path.exists():
        return 0
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return connection.execute(query).fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        connection.close()


def _snapshot(source: Path, target: Path) -> None:
    origin = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        origin.backup(copy)
    finally:
        copy.close()
        origin.close()


def import_jipdam(*, source: Path | None = None, target: Path | None = None,
                  source_keys: MasterKeyStore | None = None, target_keys: MasterKeyStore | None = None) -> dict:
    """Copy keys with their IDs, then leave GMS off. Results hold counts only, never a secret."""
    source = Path(source) if source is not None else legacy_vault_path()
    target = Path(target) if target is not None else default_vault_path()
    source_keys = source_keys or _legacy_key_store()
    target_keys = target_keys or _default_key_store()
    source_budget, target_budget = source.with_name(BUDGET_NAME), target.with_name(BUDGET_NAME)
    if not source.is_file():
        raise CredentialVaultError("이전할 Jipdam 보관함을 찾을 수 없습니다.")
    if _rows(target, "SELECT COUNT(*) FROM credentials") or _rows(target, "SELECT COUNT(*) FROM credential_folders"):
        raise CredentialVaultError("BATON 보관함에 이미 데이터가 있어 이전을 중단했습니다.")
    if _rows(target_budget, "SELECT COUNT(*) FROM calls"):
        raise CredentialVaultError("BATON GMS 원장에 이미 기록이 있어 이전을 중단했습니다.")
    key = source_keys.read()
    if not isinstance(key, bytes) or len(key) != MASTER_KEY_BYTES:
        raise CredentialVaultError("Jipdam 보관함의 암호화 키를 읽을 수 없습니다.")

    target.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staged_vault = target.with_name(f".import-{token}-vault.sqlite3")
    staged_budget = target.with_name(f".import-{token}-budget.sqlite3")
    try:
        _snapshot(source, staged_vault)
        connection = sqlite3.connect(staged_vault)
        connection.row_factory = sqlite3.Row
        try:
            folders = connection.execute("SELECT COUNT(*) FROM credential_folders").fetchone()[0]
            rows = connection.execute("SELECT * FROM credentials").fetchall()
            for row in rows:  # Every key must decrypt before anything in BATON changes.
                CredentialVault._decrypt(key, row)
        finally:
            connection.close()
        calls = 0
        if source_budget.is_file():
            _snapshot(source_budget, staged_budget)
            connection = sqlite3.connect(staged_budget)
            try:
                calls = connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
                body = json.loads(connection.execute("SELECT body FROM policy WHERE id=1").fetchone()[0])
                with connection:
                    connection.execute("UPDATE policy SET revision=revision+1,body=? WHERE id=1",
                                       (json.dumps({**body, "enabled": False}),))
            finally:
                connection.close()
        target_keys.write(key)
        if target_keys.read() != key:
            raise CredentialVaultError("BATON 암호화 키 저장을 확인하지 못했습니다.")
        os.replace(staged_vault, target)
        if staged_budget.exists():
            os.replace(staged_budget, target_budget)
    finally:
        staged_vault.unlink(missing_ok=True)
        staged_budget.unlink(missing_ok=True)
    return {"imported": True, "folders": folders, "credentials": len(rows), "gms_calls": calls, "gms_enabled": False}
