"""Resolve human-maintained routing profiles to the existing Orca launch fields."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
import re
import sysconfig
import tomllib

from .contracts import HarnessError, safe

REFERENCE = Path("skills/baton-flow/references/model-routing.md")
SUPPORT = Path(".local_runtime/routing-support.md")
PRESETS = ("economy", "standard", "accelerated")
EFFORTS = ("default", "low", "medium", "high", "xhigh", "max")
SPEEDS = ("normal", "fast", "direct-fast")
PLANS = {"codex": {"plus", "pro"}, "claude": {"pro", "max", "ultra"},
         "antigravity": {"free", "plus", "trial", "pro", "device-trial", "ultra"}}
GROUPS = {"coordination", "investigation", "design", "writing", "review"}
STATES = {"available", "unverified", "withdrawn", "quota-exhausted"}
CLAUDE_ALIASES = {"default", "best", "fable", "sonnet", "opus", "haiku", "opusplan",
                  "sonnet[1m]", "opus[1m]"}
LATEST_PREFIXES = {"claude": ("claude-",), "antigravity": ("gemini-",), "codex": ("chatgpt-", "gpt-")}
WORD = re.compile(r"[a-z][a-z0-9-]{0,59}")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}")
FENCE = re.compile(r"^(?P<fence>`{3}|~{3})toml[ \t]*\n(.*?)^(?P=fence)[ \t]*$", re.M | re.S)


def profile_path(root):
    local = root / "baton-routing.md"
    if local.exists() or local.is_symlink():
        return local
    module = Path(__file__).resolve()
    for path in (root / REFERENCE, module.parent.parent.parent / REFERENCE,
                 module.parent.parent / "share/baton" / REFERENCE,
                 Path(sysconfig.get_path("data")) / "share/baton" / REFERENCE):
        if path.is_file():
            return path
    raise HarnessError("routing_profile_missing")


def _read(path, *, support=False):
    try:
        if path.is_symlink() or not path.is_file():
            raise HarnessError("routing_support_missing" if support else "invalid_routing_profile")
        raw = path.read_bytes()
        if len(raw) > 128_000:
            raise HarnessError("routing_document_too_large")
        content = raw.decode("utf-8").replace("\r\n", "\n")
        blocks = [m[2] for m in FENCE.finditer(content)]
        if len(blocks) != (1 if support else 2):
            raise HarnessError("invalid_routing_document")
        data = tomllib.loads(blocks[0])
        if type(data.get("schema")) is not int or data["schema"] != 1:
            raise HarnessError("invalid_routing_schema")
        safe(data)
        return content, data, sha256(raw).hexdigest()
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        raise HarnessError("invalid_routing_document") from None


def _words(value, lengths):
    items = value.split() if isinstance(value, str) else []
    if len(items) not in lengths:
        raise HarnessError("invalid_routing_option")
    return items


def _option(provider, value):
    words = _words(value, (2, 3, 4))
    family, effort = words[:2]
    speed = words[2] if len(words) >= 3 else "normal"
    pin = words[3] if len(words) == 4 else None
    if (provider not in PLANS or not WORD.fullmatch(family) or effort not in EFFORTS or speed not in SPEEDS
            or (pin is not None and not MODEL.fullmatch(pin))):
        raise HarnessError("invalid_routing_option")
    return {"provider": provider, "family": family, "effort": effort, "speed": speed, "pin": pin}


def _profile(root):
    path = profile_path(root)
    text, config, fingerprint = _read(path)
    if set(config) - {"schema", "active", "groups", "roles"}:
        raise HarnessError("invalid_routing_profile")
    active = config.get("active", {"provider": "codex", "preset": "standard"})
    if (not isinstance(active, dict) or set(active) != {"provider", "preset"}
            or active["provider"] not in tuple(PLANS) or active["preset"] not in PRESETS):
        raise HarnessError("invalid_routing_active_profile")
    tables = re.findall(r"<!-- routing-table:start -->\n(.*?)\n<!-- routing-table:end -->", text, re.S)
    if len(tables) != 1:
        raise HarnessError("invalid_routing_table")
    header = "| Group | Role | 작업 | Codex 가성비 | Codex 표준 | Codex 가속 속도 | Claude 가성비 | Claude 표준 Pro | Claude 표준 Max | Gemini 가성비 | Gemini 표준 |"
    lines = tables[0].splitlines()
    if lines[:2] != [header, "|---|---|---|---|---|---|---|---|---|---|---|"]:
        raise HarnessError("invalid_routing_table")
    roles = {}
    for line in lines[2:]:
        if not line.startswith("|") or not line.endswith("|"):
            raise HarnessError("invalid_routing_table")
        cells = [item.strip() for item in line[1:-1].split("|")]
        if len(cells) != 11:
            raise HarnessError("invalid_routing_table")
        group, role, label, ce, cs, speed, ae, ap, am, ge, gs = cells
        if group not in GROUPS or not WORD.fullmatch(role) or not label or role in roles or speed not in SPEEDS:
            raise HarnessError("invalid_routing_table")
        standard = _option("codex", cs)
        roles[role] = {"group": group, "label": label,
                       "codex": (_option("codex", ce), standard, {**standard, "speed": speed}),
                       "claude": tuple(_option("claude", value) for value in (ae, ap, am)),
                       "antigravity": tuple(_option("antigravity", value) for value in (ge, gs))}
    if not roles or {entry["group"] for entry in roles.values()} != GROUPS:
        raise HarnessError("invalid_routing_table")
    overrides = {}
    for name, keys in (("groups", GROUPS), ("roles", roles)):
        selected = config.get(name, {})
        if not isinstance(selected, dict) or set(selected) - set(keys):
            raise HarnessError("invalid_routing_override")
        overrides[name] = {}
        for key, value in selected.items():
            provider, *option = _words(value, (4, 5))
            overrides[name][key] = _option(provider, " ".join(option))
    return path, fingerprint, roles, overrides, active


def _proposal(roles, overrides, role, provider, preset, plan):
    row = roles[role]
    if role in overrides["roles"]:
        return overrides["roles"][role], "role"
    if row["group"] in overrides["groups"]:
        return overrides["groups"][row["group"]], "group"
    column = PRESETS.index(preset)
    if provider == "claude":
        column = 0 if not column else 2 if plan in {"max", "ultra"} else 1
    if provider == "antigravity":
        column = min(column, 1)
    return row[provider][column], "preset"


def show(root, provider, preset, plan):
    path, fingerprint, roles, overrides, active = _profile(root)
    provider, preset = provider or active["provider"], preset or active["preset"]
    if plan is not None and plan not in PLANS[provider]:
        raise HarnessError("invalid_routing_plan")
    return {"path": str(path), "sha256": fingerprint, "provider": provider, "preset": preset, "plan": plan,
            "active": active,
            "roles": {role: {"group": row["group"], "label": row["label"], "choice": choice, "source": source}
                      for role, row in roles.items()
                      for choice, source in [_proposal(roles, overrides, role, provider, preset, plan)]}}


def _day(value):
    try:
        result = date.fromisoformat(value)
        if result.isoformat() == value:
            return result
    except (TypeError, ValueError):
        pass
    raise HarnessError("invalid_routing_date")


def _set_of(values, options):
    return (isinstance(values, list) and bool(values) and all(isinstance(v, str) and v in options for v in values)
            and len(set(values)) == len(values))


def _support(root):
    _, data, fingerprint = _read(root / SUPPORT, support=True)
    hosts, models = data.get("hosts"), data.get("models")
    if (set(data) != {"schema", "hosts", "models"} or not isinstance(hosts, dict)
            or not isinstance(models, list) or len(models) > 256):
        raise HarnessError("invalid_routing_support")
    flags = {"subscription_only", "overages_disabled", "normal_speed", "quota_available", "single_model", "plus_astra_ack"}
    for provider, host in hosts.items():
        if (provider not in PLANS or not isinstance(host, dict) or set(host) - flags - {"plan", "confirmed", "expires"}
                or host.get("plan") not in tuple(PLANS[provider])
                or any(type(host[flag]) is not bool for flag in flags & host.keys())):
            raise HarnessError("invalid_routing_host")
        if _day(host.get("expires")) < _day(host.get("confirmed")):
            raise HarnessError("invalid_routing_date")
    ids = set()
    for model in models:
        if not isinstance(model, dict) or set(model) != {"provider", "family", "id", "released", "plans", "efforts", "status"}:
            raise HarnessError("invalid_routing_model")
        provider, family, name = (model[field] for field in ("provider", "family", "id"))
        if (provider not in tuple(PLANS) or not isinstance(family, str) or not WORD.fullmatch(family)
                or not isinstance(name, str) or not MODEL.fullmatch(name)
                or not _set_of(model["plans"], PLANS[provider]) or not _set_of(model["efforts"], EFFORTS)
                or model["status"] not in tuple(STATES) or (provider, name) in ids):
            raise HarnessError("invalid_routing_model")
        _day(model["released"])
        ids.add((provider, name))
    return hosts, models, fingerprint


def _host_reason(provider, family, speed, host, today):
    if speed != "normal":
        return "speed_not_supported_by_orca"
    if not host or not _day(host["confirmed"]) <= today <= _day(host["expires"]):
        return "host_confirmation_missing_or_expired"
    if any(host.get(flag) is not True for flag in ("subscription_only", "overages_disabled", "normal_speed")):
        return "subscription_or_billing_controls_unconfirmed"
    if host.get("quota_available") is not True:
        return "included_quota_unavailable"
    if provider == "codex" and host["plan"] == "plus" and family == "astra" and host.get("plus_astra_ack") is not True:
        return "plus_astra_confirmation_required"
    if provider == "claude" and family == "fable" and host["plan"] == "pro":
        return "fable_not_in_pro_plan"
    if provider == "antigravity":
        if host.get("single_model") is not True:
            return "single_model_channel_required"
        if host["plan"] in {"free", "plus", "trial"} and family != "hydrogen":
            return "family_not_in_plan"
    return None


def _floating_model(provider, name):
    name = name.casefold()
    return ((provider == "claude" and name in CLAUDE_ALIASES)
            or (name.startswith(LATEST_PREFIXES[provider]) and name.endswith("-latest")))


def _approval(value, *, historical=False):
    provider, name, effort, speed = _words(value, (4,))
    if provider in PLANS and _floating_model(provider, name) and not historical:
        raise HarnessError("routing_floating_model_alias")
    if (provider not in PLANS or not MODEL.fullmatch(name) or effort not in EFFORTS
            or speed not in ("normal", "fast")):
        raise HarnessError("invalid_routing_approval")
    return provider, name, effort, speed


def _family_models(choice, models):
    return (m for m in models if m["provider"] == choice["provider"] and m["family"] == choice["family"])


def _candidates(choice, approved, hosts, models, today):
    provider, family, effort, speed, pin = (choice[k] for k in ("provider", "family", "effort", "speed", "pin"))
    host = hosts.get(provider)
    reason = _host_reason(provider, family, speed, host, today)
    if reason:
        return None, [], reason, []
    rows = sorted(_family_models(choice, models), key=lambda m: (m["released"], m["id"]), reverse=True)
    rejected = []
    eligible = []
    for model in rows:
        name = model["id"]
        if _floating_model(provider, name):
            reason = "routing_floating_model_alias"
        elif model["status"] != "available":
            reason = model["status"]
        elif _day(model["released"]) > today:
            reason = "release_not_current"
        elif host["plan"] not in model["plans"]:
            reason = "model_not_in_plan"
        elif effort not in model["efforts"]:
            reason = "effort_not_supported"
        elif (provider, name, effort, speed) not in approved:
            reason = "tuple_not_approved"
        else:
            eligible.append(model)
            continue
        if pin is None or name == pin:
            rejected.append({"model": name, "reason": reason})

    def option(model):
        return {"provider": provider, "model": model["id"], "effort": effort, "speed": speed,
                "plan": host["plan"], "confirmed": host["confirmed"], "expires": host["expires"]}

    if pin is not None:
        selected = next((m for m in eligible if m["id"] == pin), None)
        if selected is not None:
            return option(selected), rejected, None, []
        return None, rejected, "pin_unavailable", [option(m) for m in eligible]
    if not eligible:
        return None, rejected, "no_supported_approved_model", []
    model = eligible[0]
    if len(eligible) > 1 and eligible[1]["released"] == model["released"]:
        return None, rejected, "release_order_ambiguous_pin_required", []
    return option(model), rejected, None, []


def resolve(root, intent):
    _, profile_hash, roles, overrides, active = _profile(root)
    allowed = {"preset", "provider", "author", "reviewer", "review_provider", "approved", "direct_response", "reason"}
    if not isinstance(intent, dict) or set(intent) - allowed:
        raise HarnessError("invalid_routing_request")
    preset, provider = (intent.get(key, active[key]) for key in ("preset", "provider"))
    author, reviewer = intent.get("author"), intent.get("reviewer", "review-final")
    review_provider = intent.get("review_provider")
    direct = intent.get("direct_response", False)
    if (preset not in PRESETS or provider not in tuple(PLANS) or author not in tuple(roles)
            or reviewer not in tuple(roles) or roles[reviewer]["group"] != "review"
            or (review_provider is not None and review_provider not in tuple(PLANS))
            or type(direct) is not bool or not isinstance(intent.get("reason", ""), str)):
        raise HarnessError("invalid_routing_request")
    raw_approved = intent.get("approved")
    if not isinstance(raw_approved, list) or not 1 <= len(raw_approved) <= 128:
        raise HarnessError("routing_task_approval_required")
    approved = {_approval(value) for value in raw_approved}
    hosts, models, fingerprint = _support(root)
    today = date.today()

    def select(role, agent):
        choice, source = _proposal(roles, overrides, role, agent, preset, hosts.get(agent, {}).get("plan"))
        if choice["speed"] == "direct-fast":
            choice = {**choice, "speed": "fast" if direct else "normal"}
        selected, excluded, blocker, replacements = _candidates(choice, approved, hosts, models, today)
        return {"role": role, "source": source, "proposal": choice, "supported": selected,
                "excluded": excluded, "blocker": blocker, "eligible_replacements": replacements}

    author_selection = select(author, provider)
    result = {"profile_sha256": profile_hash, "support_sha256": fingerprint, "provider": provider,
              "preset": preset, "author": author_selection}
    review_selection = select(reviewer, review_provider or provider)
    if review_provider and review_selection["proposal"]["provider"] != review_provider:
        raise HarnessError("routing_reviewer_provider_conflicts_with_override")
    if reviewer == "review-final" and review_provider is None and review_selection["source"] == "preset":
        author_provider = author_selection["proposal"]["provider"]
        alternatives = {p for p, *_ in approved if p != author_provider}
        choices = []
        for agent in sorted(alternatives):
            candidate = select(reviewer, agent)
            choice = candidate["proposal"]
            if any((agent, m["id"], choice["effort"], choice["speed"]) in approved
                   for m in _family_models(choice, models)):
                choices.append(candidate)
        if choices:
            review_selection = next((choice for choice in choices if choice["supported"]), choices[0])
            review_selection = {**review_selection, "alternatives": choices}
        else:
            review_selection = select(reviewer, author_provider)
    result["reviewer"] = review_selection
    return result


def routing_intent(body):
    execution = body["execution"]
    config = execution["orca"] if execution["runtime"] == "orca" else {}
    if (execution["runtime"] != "orca" or any(key in execution for key in ("model", "effort", "routing_selection"))
            or execution["preferred_provider"] != "codex" or any(key.startswith("review_") for key in config)):
        raise HarnessError("routing_conflicts_with_explicit_execution")
    if "routing" not in execution:
        raise HarnessError("routing_request_required")
    return execution["routing"]


def prepare(root, body, previous=None):
    """Resolve before insertion, retaining the original resolved tuple on idempotent submits."""
    intent = routing_intent(body)
    if previous and previous.get("routing") == intent and previous.get("routing_selection"):
        selection = previous["routing_selection"]
    else:
        selection = resolve(root, intent)
    execution = deepcopy(body["execution"])
    execution["routing_selection"] = selection
    for role in ("author", "reviewer"):
        if role not in selection:
            continue
        option = selection[role]["supported"]
        if option is None:
            blocked = selection[role]
            raise RouteBlocked("routing_" + role + "_blocked:" + blocked["blocker"],
                               blocked["eligible_replacements"])
        if role == "author":
            execution.update(preferred_provider=option["provider"], model=option["model"])
            if option["effort"] != "default":
                execution["effort"] = option["effort"]
        else:
            execution["orca"].update(review_provider=option["provider"], review_model=option["model"])
            if option["effort"] != "default":
                execution["orca"]["review_effort"] = option["effort"]
    return {**body, "execution": execution}


class RouteBlocked(HarnessError):
    def __init__(self, code, replacements):
        super().__init__(code)
        self.eligible_replacements = replacements


def _check_pin(choice, approved, hosts, models, fingerprint):
    supported, rejected, blocker, replacements = _candidates(choice, approved, hosts, models, date.today())
    if supported is None:
        raise RouteBlocked("routing_dispatch_blocked:" + (rejected[0]["reason"] if rejected else blocker),
                           replacements)
    return {"requested": {k: supported[k] for k in ("provider", "model", "effort", "speed")},
            "supported": supported, "support_sha256": fingerprint,
            "observed": dict.fromkeys(("provider", "model", "effort", "speed")),
            "effective": dict.fromkeys(("provider", "model", "effort", "speed"))}


def check_registered(root, execution, role):
    """Recheck exactly the registered tuple. Profile edits and refresh cannot reselect it."""
    selection = execution.get("routing_selection", {}).get(role)
    if not selection or not selection["supported"]:
        raise HarnessError("routing_role_not_registered")
    requested = selection["supported"]
    approved = {_approval(value, historical=True) for value in execution.get("routing", {}).get("approved", [])}
    approved.add(tuple(requested[k] for k in ("provider", "model", "effort", "speed")))
    choice = {**selection["proposal"], "pin": requested["model"]}
    return _check_pin(choice, approved, *_support(root))


def recover_reviewer(root, approval):
    """Resolve an explicitly approved tuple for an already frozen author-only route."""
    provider, name, effort, speed = _approval(approval)
    hosts, models, fingerprint = _support(root)
    selected = next((m for m in models if m["provider"] == provider and m["id"] == name), None)
    if selected is None:
        raise RouteBlocked("routing_dispatch_blocked:pin_unavailable", [])
    choice = {"provider": provider, "family": selected["family"], "effort": effort, "speed": speed, "pin": name}
    return _check_pin(choice, {(provider, name, effort, speed)}, hosts, models, fingerprint)
