from __future__ import annotations
import io
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread
from datetime import datetime
from unittest.mock import patch

from baton.credential_vault import CredentialVault, CredentialValidationError
from baton.gms_budget import GMSBudgetError, GMSBudgetManager, GMSClient, KEY_INFO_ENDPOINT, COUNT_ENDPOINT, _expiry, KST
from baton.gms import ENDPOINT
from baton.gms_models import cost_cents, select_model, reservation_cents
from baton.gms_work import LocalGMSWork, prepare_work
from baton.credential_server import create_credential_server


class MemoryKeyStore:
    value = None
    def read(self): return self.value
    def write(self, value): self.value = value


class FakeClient:
    def __init__(self):
        self.remaining = 30000
        self.inputs = 100
        self.output = 20
        self.generated = 0
        self.expired = False
        self.error = False
        self.missing_usage = False
        self.count_error = False
        self.count_charge = 0
        self.generation_charge = None
        self.requests = []
    def balance(self, key):
        return {"total_credit": 30000, "used_credit": round(30000 - self.remaining, 6), "remain_credit": self.remaining,
                "expired_date": "2099-01-01T18:00:00+09:00", "expired": self.expired,
                "checked_at": "2026-10-14T09:00:00+09:00", "source": "gms_key_info"}
    def count(self, key, payload):
        if self.count_error: raise GMSBudgetError("카운트 미지원")
        self.remaining -= self.count_charge
        self.requests.append((COUNT_ENDPOINT, key, dict(payload)))
        return self.inputs
    def request(self, key, endpoint, payload):
        self.generated += 1
        self.requests.append((endpoint, key, dict(payload)))
        if self.error: raise RuntimeError(key)
        charge = cost_cents(payload['model'], self.inputs, self.output) / 100 if self.generation_charge is None else self.generation_charge
        self.remaining = round(self.remaining - charge, 6)
        result = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "code draft"}]}]}
        if not self.missing_usage: result["usage"] = {"input_tokens": self.inputs, "output_tokens": self.output}
        return result


class GMSBudgetTests(unittest.TestCase):
    def test_reserve_only_ignores_cumulative_limits_and_preserves_ledger(self):
        self.manager.save_policy({**self.policy,'budget_mode':'reserve_only',
                                  'max_total_credits':0,'max_call_credits':0,'max_total_tokens':0})
        for difficulty in ('simple','complex'):
            quote=self.manager.quote(task_id='TASK-TEST',objective='draft',difficulty=difficulty)
            self.assertEqual(self.manager.execute(quote['quote_id'],confirmed=True)['status'],'available')
        self.assertEqual(self.manager.state()['accounted_credits'],4.2)
        self.assertEqual(self.manager.state()['accounted_tokens'],240)
        restarted=GMSBudgetManager(self.vault,path=self.manager.path,client=self.client)
        self.assertEqual(restarted.state()['policy']['budget_mode'],'reserve_only')
        self.assertEqual(restarted.state()['accounted_credits'],4.2)

    def test_reserve_only_still_blocks_below_floor_and_floor_cannot_be_lowered(self):
        self.manager.save_policy({**self.policy,'budget_mode':'reserve_only','reserve_credits':1000})
        self.client.remaining=1000
        with self.assertRaises(GMSBudgetError): self.quote()
        self.assertEqual(self.client.generated,0)
        self.assertEqual(self.client.requests,[])
        with self.assertRaises(GMSBudgetError):
            self.manager.save_policy({**self.policy,'budget_mode':'reserve_only','reserve_credits':999})

    def test_reserve_only_1000_floor_preserves_existing_5000_and_cumulative_policy(self):
        for reserve in (1000, 5000):
            self.manager.save_policy({**self.policy, 'budget_mode': 'reserve_only', 'reserve_credits': reserve})
            self.assertEqual(self.manager.state()['policy']['reserve_credits'], reserve)
        # The new floor applies to the user-selected reserve_only mode.
        self.manager.save_policy({**self.policy, 'budget_mode': 'cumulative', 'reserve_credits': 0})
        self.assertEqual(self.manager.state()['policy']['reserve_credits'], 0)

    def test_reserve_only_1000_checks_reservation_before_count_and_generation(self):
        self.manager.save_policy({**self.policy, 'budget_mode': 'reserve_only', 'reserve_credits': 1000})
        # Even zero input needs 200 credits for the selected maximum output.
        minimum = reservation_cents('gpt-6.1-sol', 0, self.policy['max_output_tokens']) / 100
        self.client.remaining = 1000 + minimum - .01
        with self.assertRaises(GMSBudgetError):
            self.quote()
        self.assertEqual(self.client.requests, [])
        self.assertEqual(self.client.generated, 0)
        # Counted input raises the actual reservation to 202; exact equality fits.
        maximum = reservation_cents('gpt-6.1-sol', self.client.inputs, self.policy['max_output_tokens']) / 100
        self.client.remaining = 1000 + maximum
        quote = self.quote()
        self.assertEqual(quote['generation_maximum_credits'], maximum)
        counted_requests = len(self.client.requests)
        # A balance change after quotation must still block generation.
        self.client.remaining = 1000 + maximum - .01
        with self.assertRaises(GMSBudgetError):
            self.manager.execute(quote['quote_id'], confirmed=True)
        self.assertEqual(len(self.client.requests), counted_requests)
        self.assertEqual(self.client.generated, 0)

    def test_lower_reserve_and_restart_preserve_uncertain_ledger_and_holds(self):
        self.client.error = True
        quote = self.quote()
        self.assertEqual(self.manager.execute(quote['quote_id'], confirmed=True)['status'], 'uncertain')
        before = self.manager.state()
        self.assertGreater(before['held_credits'], 0)
        self.manager.save_policy({**self.policy, 'budget_mode': 'reserve_only', 'reserve_credits': 1000})
        restarted = GMSBudgetManager(self.vault, path=self.manager.path, client=self.client)
        after = restarted.state()
        self.assertEqual(after['policy']['reserve_credits'], 1000)
        for field in ('accounted_credits', 'accounted_tokens', 'held_credits', 'call_count', 'calls'):
            self.assertEqual(after[field], before[field])
        self.client.error = False
        self.client.remaining = 1000 + before['held_credits']
        counted_requests = len(self.client.requests)
        with self.assertRaises(GMSBudgetError):
            restarted.quote(task_id='TASK-HARNESS-OPS-001', objective='Do not spend held credits')
        self.assertEqual(len(self.client.requests), counted_requests)
        self.assertEqual(self.client.generated, 1)

    def test_model_rates_and_round_up(self):
        self.assertEqual(select_model('simple')['model'], 'gpt-6-luna')
        self.assertEqual(select_model('complex')['model'], 'gpt-6.1-sol')
        self.assertEqual(cost_cents('gpt-6-luna', 1, 0), 1)
        self.assertEqual(cost_cents('gpt-6-luna', 100, 20), 20)
        self.assertEqual(cost_cents('gpt-6.1-sol', 100, 20), 400)
        with self.assertRaises(ValueError):
            select_model('simple', 'gpt-6.1-sol')
        with self.assertRaises(ValueError):
            select_model(model='unsupported')

    def test_reservation_covers_provider_whole_credit_rounding(self):
        self.assertEqual(cost_cents('gpt-6.1-sol', 498, 600), 6996)
        self.assertEqual(reservation_cents('gpt-6.1-sol', 498, 600), 7000)
        self.assertEqual(reservation_cents('gpt-6-luna', 1, 0), 100)

    def test_luna_count_generation_and_ledger_share_model(self):
        quote = self.manager.quote(task_id='TASK-TEST', objective='draft', difficulty='simple')
        self.assertEqual(quote['model'], 'gpt-6-luna')
        self.assertEqual(quote['generation_maximum_credits'], reservation_cents('gpt-6-luna', 100, quote['max_output_tokens']) / 100)
        result = self.manager.execute(quote['quote_id'], confirmed=True)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['model'], 'gpt-6-luna')
        self.assertEqual(result['estimated_credits'], .2)
        self.assertEqual([payload['model'] for _, _, payload in self.client.requests], ['gpt-6-luna', 'gpt-6-luna'])
        self.assertTrue(all(row['model'] == 'gpt-6-luna' for row in self.manager.state()['calls']))

    def test_model_conflicts_and_invalid_difficulty_never_count(self):
        for fields in ({'difficulty': 'simple', 'model': 'gpt-6.1-sol'}, {'difficulty': 'unknown'},
                       {'model': 'gpt-6-astra'}, {'model': []}):
            with self.subTest(fields=fields), self.assertRaises(GMSBudgetError):
                self.manager.quote(task_id='TASK-TEST', objective='draft', **fields)
        self.assertEqual(self.client.requests, [])

    def test_per_work_output_limit_cannot_increase_policy(self):
        quote = self.manager.quote(task_id='TASK-TEST', objective='draft', max_output_tokens=32)
        self.assertEqual(quote['max_output_tokens'], 32)
        with self.assertRaises(GMSBudgetError):
            self.manager.quote(task_id='TASK-TEST', objective='draft', max_output_tokens=self.policy['max_output_tokens'] + 1)

    def test_shared_budget_and_restart_keep_both_models(self):
        for difficulty in ('simple', 'complex'):
            quote = self.manager.quote(task_id='TASK-TEST', objective='draft', difficulty=difficulty)
            self.manager.execute(quote['quote_id'], confirmed=True)
        state = self.manager.state()
        self.assertEqual(state['accounted_credits'], 4.2)
        restarted = GMSBudgetManager(self.vault, path=self.manager.path, client=self.client)
        self.assertEqual(restarted.state()['accounted_credits'], 4.2)
        self.assertEqual({row['model'] for row in restarted.state()['calls']}, {'gpt-6.1-sol', 'gpt-6-luna'})

    def test_provider_whole_credit_rounding_fits_reservation(self):
        self.client.inputs, self.client.output, self.client.generation_charge = 498, 600, 70
        quote = self.manager.quote(task_id='TASK-TEST', objective='draft', max_output_tokens=600)
        self.assertEqual(quote['generation_maximum_credits'], 70)
        result = self.manager.execute(quote['quote_id'], confirmed=True)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['estimated_credits'], 69.96)
        self.assertEqual(result['state']['accounted_credits'], 70)
        self.assertTrue(result['state']['policy']['enabled'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = CredentialVault(Path(self.temp.name) / "vault.sqlite3", MemoryKeyStore())
        self.secret = "synthetic-gms-budget-secret"
        folder = self.vault.create_folder("GMS")["id"]
        self.key_id = self.vault.add_credential(folder_id=folder, alias="시험", api_key=self.secret)["id"]
        self.client = FakeClient()
        self.manager = GMSBudgetManager(self.vault, client=self.client)
        self.policy = {"credential_id": self.key_id, "enabled": True, "reserve_credits": 5000,
                       "max_total_credits": 500, "max_total_tokens": 10000, "max_input_tokens": 4000,
                       "max_output_tokens": 2000, "expected_output_tokens": 1000, "max_call_credits": 280}
        self.manager.save_policy(self.policy)
    def quote(self):
        return self.manager.quote(task_id="TASK-GMS-BUDGET-001", objective="Write boundary tests.", context="def add(a,b): return a+b")
    def test_policy_quote_and_actual_usage_settlement(self):
        quote = self.quote()
        self.assertEqual(quote["estimated_credits"], 102)
        self.assertEqual(quote["maximum_credits"], 202)
        self.assertEqual(self.client.generated, 0)
        result = self.manager.execute(quote["quote_id"], confirmed=True)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["estimated_credits"], 4)
        self.assertEqual(result["state"]["accounted_tokens"], 120)
        self.assertEqual(result["state"]["held_credits"], 0)
        payload = self.client.requests[-1][2]
        self.assertFalse(payload["store"])
        self.assertEqual(payload["max_output_tokens"], 2000)
        self.assertEqual(payload["truncation"], "disabled")
        with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=True)
        self.assertEqual(self.client.generated, 1)
    def test_reserve_cost_and_token_caps_block_generation(self):
        for change in ({"max_input_tokens": 99}, {"max_call_credits": 201.99},
                       {"max_total_credits": 201.99}, {"max_total_tokens": 2099}, {"enabled": False}):
            self.manager.save_policy({**self.policy, **change})
            with self.assertRaises(GMSBudgetError): self.quote()
        self.manager.save_policy(self.policy)
        self.client.remaining = 5201.99
        with self.assertRaises(GMSBudgetError): self.quote()
        self.assertEqual(self.client.generated, 0)
        self.client.remaining = 5202
        self.assertEqual(self.quote()["maximum_credits"], 202)
    def test_expiry_count_failure_and_changed_balance_block(self):
        self.client.expired = True
        with self.assertRaises(GMSBudgetError): self.quote()
        self.assertFalse(self.client.requests)
        self.client.expired = False
        self.client.count_error = True
        with self.assertRaises(GMSBudgetError): self.quote()
        self.client.count_error = False
        quote = self.quote()
        self.client.remaining = 5000
        with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=True)
        self.assertEqual(self.client.generated, 0)
    def test_quotes_invalidated_by_key_policy_expiry_and_confirmation(self):
        quote = self.quote()
        with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=1)
        self.vault.update_credential(self.key_id, api_key="synthetic-rotated-key")
        with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=True)
        quote = self.quote()
        self.manager.save_policy(self.policy)
        with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=True)
        quote = self.quote()
        self.manager._quotes[quote["quote_id"]]["expires"] = 0
        with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=True)
        self.assertEqual(self.client.generated, 0)
    def test_uncertain_reservation_survives_restart(self):
        for failure in ("error", "missing_usage"):
            setattr(self.client, failure, True)
            quote = self.quote()
            result = self.manager.execute(quote["quote_id"], confirmed=True)
            self.assertEqual(result["status"], "uncertain")
            self.assertNotIn(self.secret, json.dumps(result))
            setattr(self.client, failure, False)
        restarted = GMSBudgetManager(self.vault, client=self.client)
        self.assertEqual(restarted.state()["accounted_credits"], 404)
        self.assertEqual(restarted.state()["accounted_tokens"], 4200)
        with self.assertRaises(GMSBudgetError): restarted.quote(task_id="TASK-X", objective="More code")
        restarted.save_policy(self.policy)
        self.assertEqual(restarted.state()["accounted_credits"], 404)
    def test_provider_limit_violation_disables_future_work(self):
        quote = self.quote()
        self.client.output = 2001
        result = self.manager.execute(quote["quote_id"], confirmed=True)
        self.assertEqual(result["status"], "limit_violation")
        self.assertFalse(result["state"]["policy"]["enabled"])
        with self.assertRaises(GMSBudgetError): self.quote()
    def test_account_charge_over_reservation_is_not_hidden_by_small_usage(self):
        quote = self.quote()
        self.client.generation_charge = 250
        result = self.manager.execute(quote["quote_id"], confirmed=True)
        self.assertEqual(result["status"], "limit_violation")
        self.assertEqual(result["account_delta_credits"], 250)
        self.assertEqual(result["state"]["accounted_credits"], 250)
        self.assertFalse(result["state"]["policy"]["enabled"])
    def test_usage_known_but_balance_unavailable_keeps_maximum_credit_hold(self):
        quote=self.quote()
        balance=self.client.balance
        def unavailable_after_generation(key):
            if self.client.generated:raise GMSBudgetError("잔액 미확인")
            return balance(key)
        with patch.object(self.client,"balance",side_effect=unavailable_after_generation):
            result=self.manager.execute(quote["quote_id"],confirmed=True)
        self.assertEqual(result["status"],"balance_unverified")
        self.assertEqual(result["state"]["held_credits"],202)
        self.assertEqual(result["state"]["accounted_tokens"],120)
    def test_parallel_execution_and_ledger_change_do_not_duplicate(self):
        first, second = self.quote(), self.quote()
        self.manager.execute(second["quote_id"], confirmed=True)
        with self.assertRaises(GMSBudgetError): self.manager.execute(first["quote_id"], confirmed=True)
        self.assertEqual(self.client.generated, 1)
        quote = self.quote()
        started, release = Event(), Event()
        request = self.client.request
        def slow(*args):
            started.set(); release.wait(2); return request(*args)
        with patch.object(self.client, "request", side_effect=slow):
            thread = Thread(target=lambda: self.manager.execute(quote["quote_id"], confirmed=True))
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                with self.assertRaises(GMSBudgetError): self.manager.execute(quote["quote_id"], confirmed=True)
                with self.assertRaises(GMSBudgetError): self.manager.save_policy(self.policy)
            finally:
                release.set(); thread.join(2)
        self.assertEqual(self.client.generated, 2)
    def test_no_prompt_or_secret_in_ledger_and_secret_context_blocked(self):
        with self.assertRaises(GMSBudgetError):
            self.manager.quote(task_id="TASK-X", objective=self.secret)
        with self.assertRaises(GMSBudgetError):
            self.manager.quote(task_id="TASK-X", objective="Code", context="Bearer " + "a" * 30)
        quote = self.quote()
        self.manager.execute(quote["quote_id"], confirmed=True)
        raw = self.manager.path.read_bytes()
        self.assertNotIn(self.secret.encode(), raw)
        self.assertNotIn(b"def add", raw)
        self.assertNotIn(b"Write boundary tests.", raw)
    def test_default_policy_and_invalid_settings_are_closed(self):
        empty = GMSBudgetManager(self.vault, path=Path(self.temp.name)/"empty.sqlite3", client=self.client)
        with self.assertRaises(GMSBudgetError): empty.quote(task_id="TASK-X", objective="Code")
        for change in ({"max_call_credits": float("nan")}, {"reserve_credits": 0.001},
                       {"max_output_tokens": 15}, {"expected_output_tokens": 2001},
                       {"max_input_tokens": True}, {"enabled": "true"}):
            with self.assertRaises(GMSBudgetError): self.manager.save_policy({**self.policy, **change})
    def test_connection_probe_uses_same_budget_and_policy_cap(self):
        self.manager.save_policy({**self.policy, "max_output_tokens": 32, "expected_output_tokens": 20})
        result = self.manager.check(self.key_id, confirmed=True)
        self.assertEqual(result["status"], "available")
        self.assertEqual(self.client.requests[-1][2]["max_output_tokens"], 32)
        self.assertEqual(self.client.requests[-1][2]["input"], "Reply with OK.")
    def test_count_fee_is_reserved_included_and_not_repeated_at_execution(self):
        self.client.count_charge = 20
        quote = self.quote()
        self.assertEqual(quote["estimated_credits"],122)
        self.assertEqual(quote["maximum_credits"],222)
        self.assertEqual(quote["count_credits"],20)
        self.assertEqual(self.manager.state()["accounted_credits"],20)
        result=self.manager.execute(quote["quote_id"],confirmed=True)
        self.assertEqual(result["total_estimated_credits"],24)
        self.assertEqual(result["state"]["accounted_credits"],24)
        self.assertEqual(sum(request[0]==COUNT_ENDPOINT for request in self.client.requests),1)
    def test_counter_fee_limit_violation_and_counter_budget_stop_before_generation(self):
        self.client.count_charge=21
        with self.assertRaises(GMSBudgetError):self.quote()
        self.assertFalse(self.manager.state()["policy"]["enabled"])
        self.assertEqual(self.manager.state()["accounted_credits"],21)
        self.assertEqual(self.client.generated,0)
        self.manager.save_policy({**self.policy,"max_total_credits":22})
        before=len(self.client.requests)
        with self.assertRaises(GMSBudgetError):self.quote()
        self.assertEqual(len(self.client.requests),before)


class GMSBalanceTests(unittest.TestCase):
    # GMS produced the draft and the host reviewed its error assertion before applying.
    def test_contradictory_suffix_offsets(self):
        for offset in ("+00:00", "-04:00", "Z"):
            with self.subTest(offset=offset):
                with self.assertRaises(GMSBudgetError) as error:
                    _expiry(f"2026-10-16 18:00:00.000{offset} KST")
                self.assertEqual(str(error.exception), "GMS 만료일 형식을 확인할 수 없습니다.")
    def test_consistent_suffix_offset(self):
        expected = datetime(2026, 10, 16, 18, tzinfo=KST)
        for value in ("2026-10-16 18:00:00.000+09:00 KST", "2026-10-16 18:00:00.000 KST"):
            with self.subTest(value=value):
                result = _expiry(value)
                self.assertEqual(result, expected)
                self.assertEqual(result.tzinfo, KST)
    def test_official_balance_fields_and_kst_format(self):
        client = GMSClient()
        value = {"totalCredit": 30000, "usedCredit": .36, "remainCredit": 29999.64,
                 "expiredDate": "2099-10-16 18:00:00.000 KST", "key": "untrusted-never-returned"}
        with patch("baton.gms_budget.build_opener") as factory:
            factory.return_value.open.return_value = io.BytesIO(json.dumps(value).encode())
            result = client.balance("synthetic-key")
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, KEY_INFO_ENDPOINT)
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-key")
            self.assertEqual(result["remain_credit"], 29999.64)
            self.assertEqual(result["expired_date"], "2099-10-16T18:00:00+09:00")
            self.assertNotIn("untrusted-never-returned", json.dumps(result))
    def test_bad_balance_and_count_schemas_fail_closed(self):
        client = GMSClient()
        normal = {"totalCredit": 30000, "usedCredit": 0, "remainCredit": 30000, "expiredDate": "2099-01-01"}
        for change in ({"remainCredit": "30000"}, {"usedCredit": True}, {"remainCredit": -1},
                       {"expiredDate": "bad"}, {"usedCredit": 40000}):
            with patch.object(client, "request", return_value={**normal, **change}):
                with self.assertRaises(GMSBudgetError): client.balance("synthetic-key")
        with patch.object(client, "request", return_value={"object":"response.input_tokens","input_tokens":100}):
            self.assertEqual(client.count("key", {"input":"Hello"}), 100)
        with patch.object(client, "request", return_value={"input_tokens":100}):
            with self.assertRaises(GMSBudgetError): client.count("key", {"input":"Hello"})
    def test_transport_error_does_not_echo_or_retry(self):
        client = GMSClient()
        with patch("baton.gms_budget.build_opener") as factory:
            factory.return_value.open.side_effect = RuntimeError("synthetic-secret")
            with self.assertRaises(GMSBudgetError) as error: client.balance("synthetic-secret")
            self.assertNotIn("synthetic-secret", str(error.exception))
            factory.return_value.open.assert_called_once()


class GMSBudgetHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.vault = CredentialVault(Path(self.temp.name)/"vault.sqlite3", MemoryKeyStore())
        folder = self.vault.create_folder("GMS")["id"]
        self.secret = "synthetic-budget-http-key"
        self.key_id = self.vault.add_credential(folder_id=folder, alias="GMS", api_key=self.secret)["id"]
        self.server = create_credential_server(self.vault, port=0)
        self.client = FakeClient(); self.server.gms_budget.client = self.client
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval":.01}, daemon=True)
        self.thread.start(); self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
    def request(self, path, body, *, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("POST", path, json.dumps(body).encode(), headers={"Content-Type":"application/json",
            "Origin":origin or self.server.origin,"X-Baton-CSRF":self.server.csrf_token})
        response=connection.getresponse(); raw=response.read(); connection.close()
        return response.status, json.loads(raw)
    def policy(self):
        return {"credential_id":self.key_id,"enabled":True,"reserve_credits":5000,"max_total_credits":500,
                "max_total_tokens":10000,"max_input_tokens":4000,"max_output_tokens":2000,
                "expected_output_tokens":1000,"max_call_credits":280}
    def test_balance_policy_quote_execute_http_and_cli(self):
        status,result=self.request("/api/gms/balance",{"credential_id":self.key_id})
        self.assertEqual((status,result["remain_credit"]),(200,30000))
        self.assertEqual(self.client.generated,0)
        self.assertEqual(self.request("/api/gms/policy",self.policy())[0],200)
        worker=LocalGMSWork(self.server.server_port)
        task={"task_id":"TASK-X","objective":"Write boundary tests.","context":"def add(a,b):return a+b"}
        self.assertEqual(worker.work(task)["mode"],"quote_only")
        self.assertEqual(self.client.generated,0)
        result=worker.work(task,execute=True)
        self.assertEqual(result["result"]["status"],"available")
        self.assertNotIn(self.secret,json.dumps(result))
        self.assertEqual(self.client.generated,1)
    def test_guarded_routes_and_unconfigured_execution_are_closed(self):
        for path in ("/api/gms/balance","/api/gms/policy","/api/gms/quote","/api/gms/execute","/api/gms/check"):
            with patch.object(self.vault,"get_secret") as secret:
                self.assertEqual(self.request(path,{"credential_id":self.key_id,"confirm":True},origin="https://evil.example")[0],403)
                secret.assert_not_called()
        self.assertEqual(self.request("/api/gms/check",{"credential_id":self.key_id,"confirm":True})[0],400)
        self.assertEqual(self.client.generated,0)
    def test_large_quote_body_accepted_within_gms_limit_and_secret_blocked(self):
        self.request("/api/gms/policy",self.policy())
        status,_=self.request("/api/gms/quote",{"task_id":"TASK-X","objective":"Write tests","context":"safe code "*2000})
        self.assertEqual(status,200)
        status,result=self.request("/api/gms/quote",{"task_id":"TASK-X","objective":self.secret})
        self.assertEqual(status,400); self.assertNotIn(self.secret,json.dumps(result))


class GMSWorkTests(unittest.TestCase):
    def test_scoped_code_context_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"src").mkdir()
            (root/"src/example.py").write_text("def add(a,b): return a+b", encoding="utf-8")
            request = root/"request.json"
            values = {"task_id":"TASK-X", "objective":"Write a test", "acceptance_criteria":["Boundary cases"], "files":["src/example.py"]}
            request.write_text(json.dumps(values), encoding="utf-8")
            result = prepare_work(request, app_root=root)
            self.assertIn("def add", result["context"])
            for name in ("../other.py", "data/real.sqlite3", ".env", str(root.parent/"outside.py")):
                request.write_text(json.dumps({**values,"files":[name]}),encoding="utf-8")
                with self.assertRaises(GMSBudgetError): prepare_work(request, app_root=root)
    def test_cli_quote_default_and_explicit_execution(self):
        worker = LocalGMSWork()
        with patch.object(worker, "_request", side_effect=[None,{"quote_id":"opaque"}]) as request:
            self.assertEqual(worker.work({"task_id":"TASK-X"})["mode"], "quote_only")
            self.assertEqual(request.call_count,2)
        with patch.object(worker, "_request", side_effect=[None,{"quote_id":"opaque"},{"status":"available"}]) as request:
            self.assertEqual(worker.work({"task_id":"TASK-X"}, execute=True)["mode"], "executed")
            self.assertEqual(request.call_args.args[1], "/api/gms/execute")
    def test_secret_context_and_non_code_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/"src").mkdir()
            (root/"src/example.py").write_text('key="sk-'+'a'*30+'"', encoding="utf-8")
            request=root/"request.json"
            request.write_text(json.dumps({"task_id":"TASK-X","objective":"Code","acceptance_criteria":["Test"],"files":["src/example.py"]}),encoding="utf-8")
            with self.assertRaises(GMSBudgetError): prepare_work(request,app_root=root)

if __name__ == "__main__": unittest.main()
