"""BATON GMS switch, two-page routing and the one-time Jipdam import. No network, no OS key store."""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
import unittest

try:
    import cryptography  # noqa: F401
except ImportError:
    raise unittest.SkipTest("the gms extra is not installed") from None

from baton.credential_import import import_jipdam
from baton.credential_server import create_credential_server
from baton.credential_vault import CredentialVault, CredentialVaultError
from baton.gms_budget import GMSBudgetError, GMSBudgetManager

SECRET = "synthetic-secret-value-0001"
LIMITS = {"reserve_credits": 1000, "budget_mode": "reserve_only", "max_input_tokens": 100,
          "max_output_tokens": 64, "expected_output_tokens": 32}


class Keys:
    def __init__(self, value=None):
        self.value = value

    def read(self):
        return self.value

    def write(self, value):
        self.value = value

    def delete(self):
        self.value = None


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def vault(self, name="baton", keys=None):
        (self.root / name).mkdir(exist_ok=True)
        return CredentialVault(self.root / name / "credentials.sqlite3", keys if keys is not None else Keys())

    def seeded(self, vault):
        folder = vault.create_folder("GMS")
        return vault.add_credential(folder_id=folder["id"], alias="gms", api_key=SECRET)["id"]


class SwitchTests(Base):
    def setUp(self):
        super().setUp()
        self.store = self.vault()
        self.budget = GMSBudgetManager(self.store)

    def test_default_is_off(self):
        self.assertIs(self.budget.state()["policy"]["enabled"], False)

    def test_on_requires_a_key_and_limits(self):
        with self.assertRaises(GMSBudgetError):
            self.budget.set_enabled(True)
        self.assertIs(self.budget.state()["policy"]["enabled"], False)

    def test_on_then_off_keeps_saved_limits(self):
        credential = self.seeded(self.store)
        self.budget.save_policy({**LIMITS, "credential_id": credential, "enabled": False})
        self.assertIs(self.budget.set_enabled(True)["policy"]["enabled"], True)
        state = self.budget.set_enabled(False)
        self.assertIs(state["policy"]["enabled"], False)
        self.assertEqual(state["policy"]["credential_id"], credential)
        self.assertEqual(state["policy"]["max_input_tokens"], 100)

    def test_off_succeeds_during_a_call_and_voids_quotes(self):
        credential = self.seeded(self.store)
        self.budget.save_policy({**LIMITS, "credential_id": credential, "enabled": True})
        self.budget._quotes["pending"] = {"expires": 0}
        revision = self.budget.state()["revision"]
        with self.budget._lock:
            state = self.budget.set_enabled(False)
        self.assertIs(state["policy"]["enabled"], False)
        self.assertGreater(state["revision"], revision)
        self.assertEqual(self.budget._quotes, {})

    def test_off_blocks_quotes_and_rejects_non_boolean(self):
        with self.assertRaisesRegex(GMSBudgetError, "꺼져"):
            self.budget.quote(task_id="TASK-1", objective="draft")
        with self.assertRaises(GMSBudgetError):
            self.budget.set_enabled("false")


class PageTests(Base):
    def setUp(self):
        super().setUp()
        self.server = create_credential_server(self.vault(), port=0)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, method, path, body=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Origin": self.server.origin, "Content-Type": "application/json"}
        if token:
            headers["X-Baton-CSRF"] = token
        try:
            connection.request(method, path, None if body is None else json.dumps(body), headers)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def test_two_pages_link_each_other_and_split_their_content(self):
        status, keys = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn('id="credential-form"', keys)
        self.assertNotIn('id="gms-switch"', keys)
        status, gms = self.call("GET", "/gms")
        self.assertEqual(status, 200)
        self.assertIn('id="gms-switch"', gms)
        self.assertNotIn('id="credential-form"', gms)
        for page in (keys, gms):
            self.assertIn('href="/"', page)
            self.assertIn('href="/gms"', page)
            self.assertIn(self.server.csrf_token, page)
            self.assertNotIn("__BATON_CSRF_TOKEN__", page)

    def test_all_assets_are_served(self):
        for name in ("credentials.css", "common.js", "credentials.js", "gms.js"):
            self.assertEqual(self.call("GET", "/static/" + name)[0], 200, name)

    def test_switch_requires_csrf(self):
        self.assertEqual(self.call("POST", "/api/gms/enabled", {"enabled": False})[0], 403)
        status, body = self.call("POST", "/api/gms/enabled", {"enabled": False}, self.server.csrf_token)
        self.assertEqual(status, 200)
        self.assertIs(json.loads(body)["policy"]["enabled"], False)

    def test_switch_on_without_limits_is_rejected(self):
        status, _ = self.call("POST", "/api/gms/enabled", {"enabled": True}, self.server.csrf_token)
        self.assertEqual(status, 400)


class ImportTests(Base):
    def setUp(self):
        super().setUp()
        self.old_keys = Keys()
        self.old = self.vault("jipdam", self.old_keys)
        self.credential = self.seeded(self.old)
        budget = GMSBudgetManager(self.old)
        budget.save_policy({**LIMITS, "credential_id": self.credential, "enabled": True})
        self.new_keys = Keys()
        self.target = self.root / "baton" / "credentials.sqlite3"

    def run_import(self):
        return import_jipdam(source=self.old.path, target=self.target,
                             source_keys=self.old_keys, target_keys=self.new_keys)

    def test_keys_keep_their_ids_and_decrypt_in_baton(self):
        result = self.run_import()
        self.assertEqual((result["folders"], result["credentials"]), (1, 1))
        self.assertEqual(CredentialVault(self.target, self.new_keys).get_secret(self.credential), SECRET)

    def test_result_holds_no_secret_and_gms_arrives_off(self):
        result = self.run_import()
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertIs(result["gms_enabled"], False)
        policy = GMSBudgetManager(CredentialVault(self.target, self.new_keys)).state()["policy"]
        self.assertIs(policy["enabled"], False)
        self.assertEqual(policy["credential_id"], self.credential)

    def test_original_is_left_unchanged(self):
        before = self.old.path.read_bytes(), self.old.path.with_name("gms-budget.sqlite3").read_bytes()
        self.run_import()
        self.assertEqual(before, (self.old.path.read_bytes(), self.old.path.with_name("gms-budget.sqlite3").read_bytes()))
        self.assertIs(GMSBudgetManager(self.old).state()["policy"]["enabled"], True)

    def test_refuses_to_overwrite_existing_baton_data(self):
        existing = self.vault("baton", self.new_keys)
        kept = self.seeded(existing)
        key = self.new_keys.value
        with self.assertRaises(CredentialVaultError):
            self.run_import()
        self.assertEqual(self.new_keys.value, key)
        self.assertEqual(existing.get_secret(kept), SECRET)

    def test_empty_baton_vault_created_by_opening_the_page_is_replaced(self):
        self.vault("baton", self.new_keys).list_state()
        self.run_import()
        self.assertEqual(CredentialVault(self.target, self.new_keys).get_secret(self.credential), SECRET)

    def test_wrong_key_changes_nothing(self):
        self.old_keys.value = b"\0" * 32
        with self.assertRaises(CredentialVaultError):
            self.run_import()
        self.assertIsNone(self.new_keys.value)
        self.assertFalse(self.target.exists())
        self.assertEqual(sorted(p.name for p in self.target.parent.glob(".import-*")) if self.target.parent.exists() else [], [])

    def test_missing_source_is_reported(self):
        with self.assertRaises(CredentialVaultError):
            import_jipdam(source=self.root / "missing.sqlite3", target=self.target,
                          source_keys=self.old_keys, target_keys=self.new_keys)


if __name__ == "__main__":
    unittest.main()
