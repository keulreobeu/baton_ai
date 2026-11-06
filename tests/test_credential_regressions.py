from __future__ import annotations

import http.client
import json
import socket
import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread, current_thread
from unittest.mock import patch

try:
    import cryptography  # noqa: F401
except ImportError:
    raise unittest.SkipTest("the gms extra is not installed") from None

from baton.credential_server import _CredentialRequestHandler, create_credential_server
from baton.credential_vault import CredentialValidationError, CredentialVault


class MemoryKeyStore:
    def __init__(self):
        self.value = None

    def read(self):
        return self.value

    def write(self, value):
        self.value = value


class CredentialRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = CredentialVault(Path(self.temp.name) / 'credentials.sqlite3', MemoryKeyStore())
        self.folder = self.vault.create_folder('QA')['id']
        self.server = create_credential_server(self.vault, port=0)
        self.thread = Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, value=None, *, token=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=1)
        try:
            headers = {'Origin': self.server.origin, 'X-Baton-CSRF': token or self.server.csrf_token,
                       'Content-Type': 'application/json'}
            connection.request(method, path, json.dumps(value).encode() if value is not None else None, headers)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def add_key(self, secret='synthetic-old-key', alias='QA key'):
        return self.vault.add_credential(folder_id=self.folder, provider_id='kakao_local', alias=alias, api_key=secret)

    def test_rotation_rejects_old_secret_in_alias_and_rolls_back(self):
        key = self.add_key()
        with self.assertRaises(CredentialValidationError):
            self.vault.update_credential(key['id'], alias='synthetic-old-key', api_key='synthetic-new-key')
        self.assertEqual(self.vault.get_secret(key['id'], expected_provider_id='kakao_local'), 'synthetic-old-key')
        self.assertEqual(self.vault.list_state()['credentials'][0]['alias'], 'QA key')

    def test_folder_name_cannot_echo_key(self):
        folder = self.vault.create_folder('synthetic-folder-key')['id']
        with self.assertRaises(CredentialValidationError):
            self.vault.add_credential(folder_id=folder, provider_id='kakao_local', alias='QA', api_key='synthetic-folder-key')
        self.assertEqual(self.vault.list_state()['credentials'], [])

    def test_invalid_unicode_label_is_input_error(self):
        status, _, _ = self.request('POST', '/api/folders', {'name': '\ud800'})
        self.assertEqual(status, 400)
        self.assertEqual(len(self.vault.list_state()['folders']), 1)

    def test_non_ascii_csrf_is_rejected_without_disconnect(self):
        status, _, _ = self.request('POST', '/api/folders', {'name': 'unexpected'}, token='é')
        self.assertEqual(status, 403)
        self.assertEqual(len(self.vault.list_state()['folders']), 1)

    def test_unsupported_method_does_not_echo_input_and_has_security_headers(self):
        status, body, headers = self.request('SYNTHETICMETHODVALUE', '/')
        self.assertEqual(status, 501)
        self.assertNotIn(b'SYNTHETICMETHODVALUE', body)
        self.assertEqual(headers.get('Cache-Control'), 'no-store')
        self.assertIn('error', json.loads(body))

    def test_idle_connection_does_not_block_other_requests(self):
        accepted = Event()

        class ObservedHandler(_CredentialRequestHandler):
            def setup(self):
                super().setup()
                accepted.set()

        self.server.RequestHandlerClass = ObservedHandler
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=1) as idle:
            self.assertTrue(accepted.wait(1))
            self.assertEqual(self.request('GET', '/api/state')[0], 200)

    def test_truncated_body_is_rejected_without_mutation(self):
        body = b'{"name":"unexpected"}'
        headers = (f'POST /api/folders HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n'
                   f'Origin: {self.server.origin}\r\nX-Baton-CSRF: {self.server.csrf_token}\r\n'
                   f'Content-Type: application/json\r\nContent-Length: {len(body) + 10}\r\n\r\n').encode()
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=1) as client:
            client.sendall(headers + body)
            client.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(client)
            response.begin()
            self.assertEqual(response.status, 400)
            response.read()
        self.assertEqual(len(self.vault.list_state()['folders']), 1)

    def test_incomplete_body_times_out_without_mutation(self):
        with patch('baton.credential_server.REQUEST_TIMEOUT_SECONDS', 0.1):
            with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=1) as client:
                client.sendall((f'POST /api/folders HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n'
                                f'Origin: {self.server.origin}\r\nX-Baton-CSRF: {self.server.csrf_token}\r\n'
                                'Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{').encode())
                response = http.client.HTTPResponse(client)
                response.begin()
                self.assertEqual(response.status, 408)
                response.read()
        self.assertEqual(len(self.vault.list_state()['folders']), 1)

    def test_folder_delete_requires_explicit_key_list(self):
        self.assertEqual(self.request('DELETE', f'/api/folders/{self.folder}', {'confirm': True})[0], 400)
        self.assertEqual(len(self.vault.list_state()['folders']), 1)

    def test_stale_folder_confirmation_preserves_all_keys_even_with_same_count(self):
        first = self.add_key()
        self.vault.delete_credential(first['id'])
        current = self.add_key(secret='synthetic-current-key')
        status, _, _ = self.request('DELETE', f'/api/folders/{self.folder}',
                                    {'confirm': True, 'credential_ids': [first['id']]})
        self.assertEqual(status, 409)
        self.assertEqual(self.vault.list_state()['credentials'][0]['id'], current['id'])
        self.assertEqual(self.request('DELETE', f'/api/folders/{self.folder}',
                         {'confirm': True, 'credential_ids': [current['id']]})[0], 200)

    def test_folder_counts_and_key_ids_share_one_snapshot_during_concurrent_add(self):
        for journal_mode in ('DELETE', 'WAL'):
            with self.subTest(journal_mode=journal_mode):
                vault = CredentialVault(Path(self.temp.name) / f'snapshot-{journal_mode}.sqlite3', MemoryKeyStore())
                folder = vault.create_folder('QA')['id']
                vault.list_state()  # Initialize the synthetic master key before concurrent work.
                reader_thread = current_thread()
                original_connect = vault._connect
                connection = original_connect()
                try:
                    mode = connection.execute(f'PRAGMA journal_mode = {journal_mode}').fetchone()[0]
                    self.assertEqual(mode, journal_mode.lower())
                finally:
                    connection.close()
                writer_done = Event()
                writer_at_commit = Event()
                writer_errors = []
                coordination_errors = []
                writers = []

                def write_key():
                    try:
                        vault.add_credential(folder_id=folder, provider_id='kakao_local',
                                             alias='QA key', api_key='synthetic-snapshot-key')
                    except Exception as error:
                        writer_errors.append(error)
                    finally:
                        writer_done.set()

                def writer_trace(sql):
                    if sql == 'COMMIT':
                        writer_at_commit.set()

                def reader_trace(sql):
                    if sql.startswith('SELECT c.id,') and not writers:
                        writer = Thread(target=write_key)
                        writers.append(writer)
                        writer.start()
                        # DELETE blocks COMMIT behind this reader. WAL permits the
                        # commit between queries, proving the reader keeps its snapshot.
                        reached = writer_done if journal_mode == 'WAL' else writer_at_commit
                        if not reached.wait(10):
                            # sqlite trace callbacks swallow exceptions; assert after closing.
                            coordination_errors.append('Writer did not reach the required event')

                def connect():
                    connection = original_connect()
                    connection.set_trace_callback(reader_trace if current_thread() is reader_thread else writer_trace)
                    return connection

                try:
                    with patch.object(vault, '_connect', side_effect=connect):
                        state = vault.list_state()
                finally:
                    # Drain workers even when the read fails, before temporary DB cleanup.
                    # This watchdog exceeds SQLite's five-second lock timeout.
                    for writer in writers:
                        writer.join(10)
                self.assertEqual(len(writers), 1)
                self.assertFalse(any(writer.is_alive() for writer in writers))
                self.assertFalse(coordination_errors)
                self.assertFalse(writer_errors)
                self.assertEqual(state['folders'][0]['credential_count'], 0)
                self.assertEqual(state['credentials'], [])
                fresh_state = vault.list_state()
                self.assertEqual(fresh_state['folders'][0]['credential_count'], 1)
                self.assertEqual(len(fresh_state['credentials']), 1)


if __name__ == '__main__':
    unittest.main()
