"""Model routing boundaries use only editable fixtures and a fake Orca runner."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from baton.contracts import HarnessError
from baton.routing import RouteBlocked, check_registered, profile_path, resolve, show
from baton.runtime import OrcaCLI


def host(plan, **settings):
    today = date.today().isoformat()
    fields = {"plan": plan, "confirmed": today, "expires": today, "subscription_only": True,
              "overages_disabled": True, "normal_speed": True, "quota_available": True, **settings}
    return "\n".join(f"{key} = {json.dumps(value)}" for key, value in fields.items())


def model(provider, family, name, plan, *, released="2024-01-01", efforts=("medium", "high"), status="available"):
    fields = {"provider": provider, "family": family, "id": name, "plans": [plan],
              "released": released, "efforts": efforts, "status": status}
    return "[[models]]\n" + "\n".join(f"{key} = {json.dumps(value)}" for key, value in fields.items())


class RoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = profile_path(self.root).read_text(encoding="utf-8")
        self.support = self.root / ".local_runtime/routing-support.md"
        self.support.parent.mkdir()
        self.intent = {"provider": "codex", "preset": "standard", "author": "implement-local",
                       "approved": ["codex older medium normal", "codex newer medium normal"]}
        self.older = model("codex", "sol", "older", "pro")
        self.newer = model("codex", "sol", "newer", "pro", released="2024-02-01")

    def catalog(self, hosts, *models):
        lines = ["~~~toml", "schema = 1"]
        lines.extend(f"[hosts.{key}]\n{value}" for key, value in hosts.items())
        lines.extend(models)
        self.support.write_text("\n".join([*lines, "~~~", ""]), encoding="utf-8")

    def edit(self, replacement):
        (self.root / "baton-routing.md").write_text(self.source.replace("schema = 1", replacement, 1), encoding="utf-8")

    def test_refresh_tracks_latest_compatible_family_and_preserves_registration(self):
        incompatible = model("codex", "sol", "newer", "pro", released="2024-02-01", efforts=("high",))
        self.catalog({"codex": host("pro")}, self.older, incompatible)
        selected = resolve(self.root, self.intent)
        self.assertEqual(selected["author"]["supported"]["model"], "older")
        self.assertEqual(selected["author"]["excluded"], [{"model": "newer", "reason": "effort_not_supported"}])
        self.catalog({"codex": host("pro")}, self.older, self.newer)
        self.assertEqual(resolve(self.root, self.intent)["author"]["supported"]["model"], "newer")
        registered = {"routing_selection": selected}
        self.assertEqual(check_registered(self.root, registered, "author")["requested"]["model"], "older")
        self.catalog({"codex": host("pro")}, self.newer)
        with self.assertRaisesRegex(HarnessError, "routing_dispatch_blocked:pin_unavailable"):
            check_registered(self.root, registered, "author")
        self.edit('schema = 1\n[roles]\nimplement-local = "codex sol medium normal older"')
        self.assertEqual(resolve(self.root, self.intent)["author"]["blocker"], "pin_unavailable")

    def test_saved_active_profile_and_group_edit_preserve_detail(self):
        self.edit('schema = 1\n[active]\nprovider = "claude"\npreset = "accelerated"\n'
                  '[groups]\nwriting = "claude sonnet high normal"\n'
                  '[roles]\nimplement-local = "codex sol medium normal older"')
        self.catalog({"codex": host("pro"), "claude": host("max")}, self.older,
                     model("claude", "sonnet", "sonnet-new", "max"))
        proposed = show(self.root, None, None, "max")
        self.assertEqual(proposed["active"], {"provider": "claude", "preset": "accelerated"})
        self.assertEqual(proposed["roles"]["integrate"]["choice"]["effort"], "high")
        intent = {"author": "implement-local", "approved": ["codex older medium normal", "claude sonnet-new high normal"]}
        self.assertEqual(resolve(self.root, intent)["author"]["source"], "role")
        self.assertEqual(resolve(self.root, {**intent, "author": "integrate"})["author"]["source"], "group")
        self.edit('schema = 1\n[groups]\nwriting = "codex sol high normal"\n')
        self.assertIsNone(resolve(self.root, intent)["author"]["supported"])
        self.edit('schema = 1\n[groups]\nmisspelled = "codex sol high normal"\n')
        with self.assertRaisesRegex(HarnessError, "invalid_routing_override"):
            resolve(self.root, intent)

    def test_cost_speed_quota_and_channel_blockers(self):
        cases = (
            ("codex", "sol", "pro", "fast", {}, "speed_not_supported_by_orca"),
            ("codex", "astra", "plus", "normal", {}, "plus_astra_confirmation_required"),
            ("claude", "fable", "pro", "normal", {}, "fable_not_in_pro_plan"),
            ("claude", "fable", "max", "normal", {"quota_available": False}, "included_quota_unavailable"),
            ("claude", "opus", "pro", "normal", {"normal_speed": False}, "subscription_or_billing_controls_unconfirmed"),
            ("antigravity", "neon", "pro", "normal", {}, "single_model_channel_required"),
            ("antigravity", "neon", "pro", "normal", {"single_model": True, "overages_disabled": False},
             "subscription_or_billing_controls_unconfirmed"),
            ("antigravity", "neon", "free", "normal", {"single_model": True}, "family_not_in_plan"),
        )
        for provider, family, plan, speed, flags, blocker in cases:
            with self.subTest(provider=provider, family=family, blocker=blocker):
                self.edit(f'schema = 1\n[roles]\nimplement-local = "{provider} {family} high {speed}"\n')
                self.catalog({provider: host(plan, **flags)}, model(provider, family, "fixture", plan))
                intent = {**self.intent, "approved": [f"{provider} fixture high {speed}"]}
                self.assertEqual(resolve(self.root, intent)["author"]["blocker"], blocker)

    def test_review_preference_keeps_author_and_explicit_review_distinct(self):
        self.catalog({"codex": host("pro"), "claude": host("max")}, self.older,
                     model("claude", "fable", "claude-fable-5-2", "max"), model("codex", "astra", "astra", "pro"))
        intent = {**self.intent, "reviewer": "review-final",
                  "approved": ["codex older medium normal", "codex astra high normal", "claude claude-fable-5-2 high normal"]}
        self.assertEqual(resolve(self.root, intent)["reviewer"]["supported"]["provider"], "claude")
        self.assertEqual(resolve(self.root, {**intent, "review_provider": "codex"})["reviewer"]["supported"]["model"], "astra")
        self.catalog({"codex": host("pro"), "claude": host("max", quota_available=False)}, self.older,
                     model("claude", "fable", "claude-fable-5-2", "max"), model("codex", "astra", "astra", "pro"))
        self.assertEqual(resolve(self.root, intent)["reviewer"]["blocker"], "included_quota_unavailable")

    def test_adapter_preflight_is_read_only_and_rejects_unsupported_launches(self):
        calls = []
        agents = [{"id": "codex"}]

        def run(argv, **kwargs):
            calls.append(argv[1:])
            output = (json.dumps({"ok": True, "result": {"agents": agents}})
                      if argv[1] == "agent" else "  --model <id>")
            return SimpleNamespace(stdout=output, returncode=0)

        client = OrcaCLI("fixture-orca", runner=run)
        client.check_route({"provider": "codex", "effort": "default"})
        with self.assertRaisesRegex(HarnessError, "routing_orca_option_unavailable"):
            client.check_route({"provider": "codex", "effort": "high"})
        with self.assertRaisesRegex(HarnessError, "routing_agent_not_installed"):
            client.check_route({"provider": "antigravity", "effort": "high"})
        self.assertEqual(calls, [["agent", "installed", "--json"], ["orchestration", "worker-start", "--help"],
                                 ["agent", "installed", "--json"], ["orchestration", "worker-start", "--help"],
                                 ["agent", "installed", "--json"]])

    def test_writing_only_provider_does_not_claim_final_review(self):
        self.catalog({"codex": host("pro"), "claude": host("max")}, self.older,
                     model("codex", "astra", "codex-review", "pro"),
                     model("claude", "sonnet", "claude-sonnet-5-5", "max"))
        intent = {**self.intent, "reviewer": "review-final",
                  "approved": ["codex older medium normal", "codex codex-review high normal",
                               "claude claude-sonnet-5-5 medium normal"]}
        self.assertEqual(resolve(self.root, intent)["reviewer"]["supported"]["model"], "codex-review")
        explicit = resolve(self.root, {**intent, "review_provider": "claude"})["reviewer"]
        self.assertIsNone(explicit["supported"])
        self.assertEqual(explicit["proposal"]["provider"], "claude")

    def test_documented_alias_cannot_be_approved_but_full_version_can(self):
        for alias in ("fable", "FABLE", "best", "opus", "sonnet", "haiku", "opusplan", "default",
                      "sonnet[1m]", "opus[1m]", "claude-3-7-sonnet-latest"):
            with self.subTest(alias=alias):
                self.catalog({"claude": host("max")}, model("claude", "fable", alias, "max"))
                intent = {"provider": "claude", "preset": "standard", "author": "replan",
                          "approved": [f"claude {alias} high normal"]}
                with self.assertRaisesRegex(HarnessError, "routing_floating_model_alias"):
                    resolve(self.root, intent)
        for version in ("claude-fable-5", "claude-fable-5-1", "claude-fable-5-2"):
            with self.subTest(version=version):
                self.catalog({"claude": host("max")}, model("claude", "fable", version, "max"))
                self.assertEqual(resolve(self.root, {**intent, "approved": [f"claude {version} high normal"]})
                                 ["author"]["supported"]["model"], version)

    def test_missing_pin_stays_blocked_and_lists_only_eligible_replacements(self):
        self.edit('schema = 1\n[roles]\nimplement-local = "codex sol medium normal missing"')
        self.catalog({"codex": host("pro")}, self.older, self.newer,
                     model("codex", "astra", "other-family", "pro"))
        intent = {**self.intent, "approved": ["codex missing medium normal", "codex newer medium normal",
                                             "codex other-family medium normal"]}
        author = resolve(self.root, intent)["author"]
        self.assertIsNone(author["supported"])
        self.assertEqual(author["blocker"], "pin_unavailable")
        self.assertEqual([option["model"] for option in author["eligible_replacements"]], ["newer"])

    def test_registered_alias_stays_blocked_and_suggests_exact_version(self):
        self.catalog({"claude": host("max")}, model("claude", "fable", "fable", "max"),
                     model("claude", "fable", "claude-fable-5-2", "max"))
        proposal = {"provider": "claude", "family": "fable", "effort": "high", "speed": "normal", "pin": None}
        old = {"routing": {"approved": ["claude fable high normal", "claude claude-fable-5-2 high normal"]},
               "routing_selection": {"author": {"proposal": proposal, "supported": {**proposal, "model": "fable"}}}}
        with self.assertRaisesRegex(RouteBlocked, "routing_floating_model_alias") as failure:
            check_registered(self.root, old, "author")
        self.assertEqual([option["model"] for option in failure.exception.eligible_replacements], ["claude-fable-5-2"])
