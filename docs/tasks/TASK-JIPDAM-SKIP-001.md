# TASK-JIPDAM-SKIP-001

```toml
kind = "task"
id = "TASK-JIPDAM-SKIP-001"
status = "in_progress"
owner = "Codex"
level = 1
specs = ["docs/specs/SDD-001.md"]
scope = ["tests/test_harness.py", "docs/tasks/TASK-JIPDAM-SKIP-001.md", "docs/sdd/traceability.json"]
acs = ["SDD-001-AC-08", "SDD-001-AC-10"]

[[verification]]
command = "D:/baton_ai/.venv/Scripts/python.exe -X utf8 -m unittest tests.test_harness tests.test_sdd"
result = "passed"
evidence = "docs/tasks/TASK-JIPDAM-SKIP-001.md"
acs = ["SDD-001-AC-08", "SDD-001-AC-10"]
tests_run = 35
failures = 0
errors = 0
skipped = 0
expected_failures = 0
```

## Decision and scope

User decision on 2026-11-12: remove the permanently skipped Jipdam-only test from BATON.
Base: `4da562acf579540bae7bd83cd0dc4d16ed97855b`; HEAD matched and tracked,
untracked, staged, and ignored file inventories were empty before editing.

This L1 cleanup reuses approved SDD-001-AC-08 (offline synthetic tests) and
SDD-001-AC-10 (accurate execution/skip/scope reporting), as existing L1 test
maintenance does. No new Spec, AC, or test symbol is introduced; existing
traceability test references remain intact.

Delete only `HarnessStateTests.test_native_configuration_and_cli_json` and its
now-unused `tomllib` import. Its assertions inspect Jipdam's `.codex/` configuration
and `scripts/agent_harness.py`, outside BATON's test contract. Jipdam remains
read-only and untouched. Preserve all other tests, conditional skips, historical
evidence, verification entry points, and CI configuration.

Follow-up user decision on 2026-11-12: the lifecycle snapshot scanner rejected
the pre-existing literal synthetic fixture in the changed test module with
`secret_in_commit` (introduced before this Task at `2705fd3`). Build that same
dictionary from `field_name` and `fixture_value` variables, neither of which is
in `contracts.SENSITIVE_FIELDS`. Runtime values, rejection assertions, and all
other fixtures stay the same; `autocommit.py` and `contracts.py` remain unchanged.

## Validation

Use the existing external Python with `PYTHONPATH=src`,
`PYTHONDONTWRITEBYTECODE=1`, and a temporary `BATON_HOME` outside this workspace.
Run only `tests.test_harness` and `tests.test_sdd`, the base-scoped SDD checker,
`git diff --check`, skip inventory, and UTF-8/replacement-character checks.
No workspace `.venv`, model/GMS calls, commits, push, PR, or merge.

### Results (2026-11-12)

- Target modules: 35 tests run, failures 0, errors 0, skips 0, exit 0.
- `D:/baton_ai/.venv/Scripts/python.exe -X utf8 scripts/check_sdd.py --base 4da562acf579540bae7bd83cd0dc4d16ed97855b`: exit 0, JSON below.
- `git diff --check`: PASS after removing the trailing blank line left by the
  deleted final method. UTF-8 strict decoding and checks for newly introduced
  question marks/replacement characters: PASS for all three written files.
- Ignored files: 0; staged files: 0; HEAD unchanged from the Task base.

```json
{"acs": 55, "basis": {"effective_base": "4da562acf579540bae7bd83cd0dc4d16ed97855b", "pre_adoption_history_excluded": false, "requested_base": "4da562acf579540bae7bd83cd0dc4d16ed97855b"}, "changed_paths": 3, "documents": 45, "features": 9, "meaning": "static_contract_check_only", "provider_calls": 0, "status": "PASS", "tasks": 15}
```

### Remaining skip inventory (unchanged)

Anchored search `rg -n '^\s*@unittest\.skip\(' tests` finds 0 unconditional
decorators. Skip syntax inside synthetic source strings is fixture data, not a
decorator on a BATON test.

- `tests/test_credentials.py:298`: `skipUnless(sys.platform == "win32")`, Windows
  Credential Manager integration only.
- `tests/test_credentials.py:309`: runtime `skipTest` only when
  `SecureStorageUnavailable` contains Windows error `1312` (no logon credential
  session).
- `tests/test_credential_regressions.py:15`, `tests/test_credentials.py:16`,
  `tests/test_credential_server.py:14`, `tests/test_gms.py:16`,
  `tests/test_gms_budget.py:15`, `tests/test_gms_switch.py:16`: module-level
  `SkipTest` only when importing optional `cryptography` raises `ImportError`.
- `tests/test_managed_providers.py:47`: `require_gms` calls `skipTest` only when
  importing optional `cryptography` raises `ImportError`.

This targeted run does not establish full-suite skip counts or V3 eligibility.

### Follow-up validation (2026-11-12)

- Direct `baton.autocommit.scan_content` call on the bytes of
  `tests/test_harness.py`, with that filename: returned `None`, no
  `secret_in_commit`; variable names checked against `SENSITIVE_FIELDS`.
- Reran the same target modules: 35 tests run, failures 0, errors 0, skips 0,
  expected failures 0, exit 0.
- Reran the base-scoped SDD checker: PASS with the same JSON reported above;
  `git diff --check`: PASS.
- Follow-up additions are ASCII only; all three candidate files strictly decode
  as UTF-8. Scanner source and sensitive-field definitions remain unchanged.
- Candidate file SHA-256 values are returned in the worker completion report;
  HEAD remains the original base and there is no commit.

## Open items

Independent review (Claude): NOT_RUN; official V3 and CI: NOT_RUN.
The coordinator schedules those checks; this Task remains in_progress.
