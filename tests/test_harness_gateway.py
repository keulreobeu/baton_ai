from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from baton.contracts import HarnessError
from baton.gateway import Gateway, MockProvider, Policy, Request, DisabledGMSProvider
from baton.state import Store


class SlowCommitStore(Store):
    """Stands in for a slow Windows runner: every write holds the ledger lock a little longer."""

    hold_seconds = 0.05

    @contextmanager
    def transaction(self):
        with super().transaction() as c:
            yield c
            time.sleep(self.hold_seconds)


class HarnessGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "runs.db", self.root)
        self.provider = MockProvider()
        self.gateway = Gateway(self.store, self.provider)
        self.req = Request(request_id="REQUEST-ONE", text="offline synthetic task")

    def test_usage_cache_restart_and_request_identity(self):
        first = self.gateway.complete(self.req)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(self.gateway.complete(self.req)["status"], "cached")
        self.assertEqual(self.gateway.complete(replace(self.req, request_id="REQUEST-TWO"))["status"], "cached")
        self.assertEqual(self.provider.calls, 1)
        reopened = Gateway(self.store, self.provider)
        self.assertEqual(reopened.complete(self.req)["status"], "already_completed")
        self.assertEqual(reopened.complete(replace(self.req, request_id="REQUEST-TWO"))["status"], "already_completed")
        with self.assertRaises(HarnessError):
            self.gateway.complete(replace(self.req, text="different"))
        self.assertEqual(self.gateway.budget()["calls"], 1)

    def test_ambiguous_failures_hold_budget_and_fallback(self):
        for mode in ("500", "timeout", "missing_usage", "bad_usage", "overrun"):
            with self.subTest(mode=mode):
                provider = MockProvider(mode)
                g = Gateway(Store(self.root / (mode + ".db"), self.root), provider)
                result = g.complete(self.req)
                self.assertEqual(result["status"], "fallback")
                self.assertGreater(g.budget()["held_tokens"], 0)
                self.assertEqual(g.complete(self.req)["status"], "fallback")
                self.assertEqual(provider.calls, 1)
                self.assertNotIn("provider-secret", str(result))

    def test_definite_429_bounded_retry_and_persistent_circuit(self):
        p = MockProvider("429_once")
        g = Gateway(self.store, p)
        self.assertEqual(g.complete(self.req)["status"], "ok")
        self.assertEqual(p.calls, 2)
        self.assertEqual(g.budget()["held_tokens"], 0)
        self.assertEqual(g.budget()["calls"], 2)
        p2 = MockProvider("500")
        g2 = Gateway(Store(self.root / "circuit.db", self.root), p2, Policy(circuit_failures=1, cooldown_seconds=60))
        g2.complete(self.req)
        reopened = Gateway(g2.store, p2, g2.policy)
        self.assertEqual(reopened.complete(replace(self.req, request_id="OTHER"))["reason"], "circuit_open")
        self.assertEqual(p2.calls, 1)

    def test_capability_secret_and_live_block_before_call(self):
        for request in (replace(self.req, operation="anthropic_messages"), replace(self.req, model="unknown"),
                        replace(self.req, text="Bearer fixture-secret-value"), replace(self.req, max_output_tokens=999999)):
            with self.assertRaises(HarnessError):
                self.gateway.complete(request)
        self.assertEqual(self.provider.calls, 0)
        with self.assertRaises(HarnessError):
            Gateway(self.store, DisabledGMSProvider()).complete(self.req)
        data = self.store.path.read_bytes()
        self.assertNotIn(b"fixture-secret-value", data)
        self.assertNotIn(self.req.text.encode(), data)

    def test_concurrent_ten_reservations_respect_27000_limit(self):
        policy = Policy(max_calls=20, max_input_tokens=4000, max_output_tokens=3000,
                        category_limits=(("development", 27000),))
        p = MockProvider("missing_usage")
        # Nine reservations of 3000 fit; the tenth cannot start. Disable failure circuit here.
        policy = replace(policy, circuit_failures=100)
        # Policy cannot be changed on an existing ledger.
        store = Store(self.root / "concurrent.db", self.root)
        g = Gateway(store, p, policy)
        requests = [replace(self.req, request_id=f"REQ-{i}", text="x" * 4000, max_output_tokens=2000) for i in range(10)]
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(g.complete, requests))
        self.assertEqual(g.budget()["held_tokens"], 27000)
        self.assertEqual(g.budget()["available_tokens"], 0)
        self.assertEqual(p.calls, 9)
        self.assertEqual(sum(r.get("reason") == "budget_exhausted" for r in results), 1)

    def test_thread_queue_wait_does_not_spend_the_storage_busy_timeout(self):
        # Regression for CI run 42777183109: ten threads spent one 5 s busy timeout waiting for
        # all other writers. Here 21 slow writes (~1 s serialized) exceed a 0.3 s busy timeout,
        # which failed with storage_unavailable_or_busy before the in-process writer queue.
        policy = Policy(max_calls=20, max_input_tokens=4000, max_output_tokens=3000,
                        category_limits=(("development", 27000),), circuit_failures=100)
        p = MockProvider("missing_usage")
        g = Gateway(SlowCommitStore(self.root / "slow.db", self.root, busy_timeout=0.3), p, policy)
        requests = [replace(self.req, request_id=f"SLOW-{i}", text="x" * 4000, max_output_tokens=2000) for i in range(10)]
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(g.complete, requests))
        self.assertEqual(g.budget()["held_tokens"], 27000)
        self.assertEqual(p.calls, 9)
        self.assertEqual(sum(r.get("reason") == "budget_exhausted" for r in results), 1)

    def test_storage_held_by_another_connection_fails_closed_before_call(self):
        store = Store(self.root / "held.db", self.root, busy_timeout=0.2)
        p = MockProvider()
        g = Gateway(store, p)
        other = sqlite3.connect(store.path, isolation_level=None)  # e.g. another process
        self.addCleanup(other.close)
        other.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        with self.assertRaises(HarnessError) as caught:
            g.complete(self.req)
        self.assertEqual(str(caught.exception), "storage_unavailable_or_busy")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(p.calls, 0)
        other.execute("ROLLBACK")
        self.assertEqual(g.complete(self.req)["status"], "ok")
        with self.assertRaises(HarnessError):
            Store(self.root / "bad.db", self.root, busy_timeout=0)

    def test_category_call_cap_cache_invalidation_and_policy_persistence(self):
        p = Policy(max_calls=1, category_limits=(("development", 100),))
        g = Gateway(Store(self.root / "category.db", self.root), self.provider, p)
        self.assertEqual(g.complete(self.req)["reason"], "category_exhausted")
        self.assertEqual(self.provider.calls, 0)
        with self.assertRaises(HarnessError):
            Gateway(g.store, self.provider, replace(p, max_calls=10))
        g = Gateway(Store(self.root / "cap.db", self.root), self.provider, Policy(max_calls=1))
        g.complete(self.req)
        r = g.complete(replace(self.req, request_id="NEXT", snapshot="new-version"))
        self.assertEqual(r["reason"], "call_limit")

    def test_ten_processes_share_one_atomic_budget(self):
        # Each process has its own provider/cache and connects to the same SQLite ledger.
        code = '''
import json,sys
from pathlib import Path
from baton.state import Store
from baton.gateway import Gateway,MockProvider,Policy,Request
root=Path(sys.argv[1])
p=Policy(category_limits=(("development",27000),),circuit_failures=100)
g=Gateway(Store(root/'process.db',root),MockProvider('missing_usage'),p)
print(json.dumps(g.complete(Request(request_id='PROC-'+sys.argv[2],text='x'*4000,max_output_tokens=2000))))
'''
        workers = [subprocess.Popen([sys.executable, "-X", "utf8", "-c", code, str(self.root), str(i)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8") for i in range(10)]
        self.addCleanup(lambda: [p.kill() for p in workers if p.poll() is None])
        results = []
        for process in workers:
            out, err = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, err)
            results.append(json.loads(out))
        policy = Policy(category_limits=(("development", 27000),), circuit_failures=100)
        g = Gateway(Store(self.root / "process.db", self.root), MockProvider(), policy)
        self.assertEqual(g.budget()["held_tokens"], 27000)
        self.assertEqual(g.budget()["calls"], 9)
        self.assertEqual(sum(x["reason"] == "budget_exhausted" for x in results), 1)
