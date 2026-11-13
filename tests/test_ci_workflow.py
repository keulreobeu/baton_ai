"""CI-OPT-001 static text checks. Stdlib only: no YAML library, network or model calls."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_DOCS = ("AGENTS.md", "README.md", "docs/sdd.md")
TASK_DOC = "docs/tasks/TASK-CI-OPT-001.md"
PUSH_HEADING = "## Git 작업 완료와 push — 2026-11-04 사용자 승인"
# SHA256 of the first four push bullets (LF-joined) at b3c9aad.
PUSH_FIRST_FOUR_SHA256 = "56f447a7ad314ae87a3afae93fe561809a496908619a31a6584f19432ac7fc53"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(text, heading):
    start = text.index(heading)
    rest = text[start:]
    end = rest.find("\n## ", 1)
    return (rest if end < 0 else rest[:end]).rstrip("\n")


class MethodologyDocsTests(unittest.TestCase):
    """CI-OPT-001-AC-01: verification ladder shared by AGENTS/README/sdd."""

    LADDER_TERMS = (
        "편집 중(in_progress/debugging)=V1 `graph_affected`",
        "작업 단위/checkpoint=V2 `affected_modules`", "Task 시작 base 기준 `check_sdd.py --base",
        "리뷰 반영", "지적을 묶은 뒤 V2 1회", "회차마다 push하지 않",
        "최종 L2/L3 후보(task_complete/pre_merge)=V3 `full`",
        "공식 순차 `verify_environment.py` 1회", "필수 독립 검토·CI",
        "통합·충돌 반영", "영향 파일 검사", "최종 증거 갱신",
        "freshness/coverage", "stale incremental index", "graph stale/failed/partial",
        "draft PR=V2 범위, ready/main=V3 Windows 전체 2 matrix",
        "worker 실행은 V1, 명시 `validate --stage checkpoint`는 V2, 기본 완료 validate/verify는 V3다",
        "V1/V2 결과는 Task 완료 상태를 올리지 않는다",
    )
    NEGATIVE_TERMS = (
        "같은 SHA만으로 검증 재사용을 결정하지 않는다",
        "코드 상태·commit SHA·target base·Task/AC·정책·테스트 설정·의존성·환경·필수 검사 목록/성공 결과",
        "unknown/partial이면 재실행",
        "후보 파일/index·base·Task/AC·검증 설정·정책·환경이 바뀌면 관련 증거는 무효",
        "최근 1~3개 커밋 조회는 빠른 파악용",
        "최종 diff 범위는 Task base 또는 통합 대상",
        "새 검증 DB·두 번째 정책 엔진은 금지",
        "graph 실패가 검사를 생략하지 않는다", "`not_configured`이며 passed가 아니다",
        "`evidence.py`의", "전체 AC·nonzero·no-skip", "바뀌지 않는다",
    )

    def test_ladder_terms_present_in_all_docs(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in self.LADDER_TERMS:
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)

    def test_reuse_and_cache_negatives_present_in_all_docs(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in self.NEGATIVE_TERMS:
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)

    def test_readme_documents_implemented_dispatch_ci_full_and_unproven_savings(self):
        # Renamed from the inverted historical name; not AC-mapped. Dispatch/ci:full are implemented.
        text = read("README.md")
        self.assertIn("workflow_dispatch", text)
        self.assertIn("ci:full", text)
        self.assertIn("CBM", text)
        self.assertIn("절감", text)

    def test_guidance_qualifies_current_wiring_reuse_and_partial_rerun_limits(self):
        # Truthfulness: current implementation limits, not a newly approved permanent policy.
        for name in GUIDANCE_DOCS + ("docs/plans/ci-optimization.md",):
            text = read(name)
            for term in ("worker V1은 `Orchestrator._run` 직접 실행 피드백",
                         "Orca author settle 경로는 현재 기본 V3로 보수적으로 실행",
                         "`reuse_v3`는 순수 비교 함수만 있고 runtime 수집/저장 호출자가 없어",
                         "현재 모든 V3를 실제 실행하며 재사용 절감을 주장하지 않는다",
                         "부분 재실행(Re-run failed jobs)은 fail-closed", "Re-run all jobs가 필요",
                         "승인된 영구 정책이 아니라", "run id/attempt", "첫 merge parent", "null이다"):
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)
            self.assertNotIn("부분 재실행 지원", text)

    def test_docs_do_not_add_pending_draft_first_practice(self):
        # Revision 2 supersedes P-02: event-based stages do not mandate PR creation practice.
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in ("draft로 열", "ready로 전환"):
                with self.subTest(doc=name, term=term):
                    self.assertNotIn(term, text)


class WorkerIoDocsTests(unittest.TestCase):
    """CI-OPT-001-AC-02: short worker input/output and batched review."""

    TERMS = (
        "Task·base·소유 scope·AC·정책·증거 경로",
        "기능/계약 변화·검증·후보 SHA·미해결·다음 행동",
        "raw transcript를 재전달하지 않",
        "가까운 수정·리뷰 지적은 묶어서 반영",
        "MetricsStore·Task 증거",
        "`unknown`/`partial`/`null`",
        "0으로 바꾸지 않는다",
        "모델 호출·Orca 배정·push를 승인하지 않는다",
    )

    def test_worker_io_terms_present_in_all_docs(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in self.TERMS:
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)

    def test_uncollectable_values_are_never_documented_as_zero(self):
        for name in GUIDANCE_DOCS:
            with self.subTest(doc=name):
                text = read(name)
                self.assertNotIn("수집 불가 값은 0", text)
                self.assertNotIn("미수집은 0", text)

    def test_agents_push_section_unchanged(self):
        # P-01: only the final bullet changes to the confirmed wording.
        agents = read("AGENTS.md")
        body = section(agents, PUSH_HEADING)
        bullets = [line for line in body.splitlines() if line.startswith("- ")]
        self.assertEqual(len(bullets), 5)
        first_four = "\n".join(bullets[:4])
        self.assertEqual(
            hashlib.sha256(first_four.encode("utf-8")).hexdigest(),
            PUSH_FIRST_FOUR_SHA256,
        )
        self.assertEqual(bullets[-1], (
            "- PR(draft 포함)의 첫 CI는 push 전 로컬 검증과 구분하고 결과 확인 전 Task/Jira 완료로 승격하지 않는다. "
            "CI가 실행되지 않은 push는 CI 증거가 아니다. "
            "이 지시는 PR 생성·main 병합·타인 branch 정리·강제 갱신·실모델·GMS·전원 실행 승인으로 확대하지 않는다."
        ))
        self.assertNotIn("최초 push로 실행되는 실제 CI", agents)
        for term in ("draft로 열", "ready로 전환"):
            with self.subTest(term=term):
                self.assertNotIn(term, agents)

    def test_p01_recorded_in_task_as_confirmed_and_applied(self):
        draft = section(read(TASK_DOC), "## P-01 AGENTS 문안 초안")
        status = next(line for line in draft.splitlines() if line.startswith("상태:"))
        self.assertIn("사용자 확인", status)
        self.assertIn("AGENTS.md 반영됨", status)
        self.assertIn("TASK-CI-OPT-001-P01-R2", status)
        self.assertNotIn("사용자 확인 전", status)
        self.assertNotIn("미반영", status)
        quoted = draft.split("초안 문구:", 1)[1].split("메모:", 1)[0]
        draft_text = next(line for line in quoted.splitlines() if line.startswith("> "))[2:]
        bullets = [line for line in section(read("AGENTS.md"), PUSH_HEADING).splitlines()
                   if line.startswith("- ")]
        self.assertEqual(bullets[-1], "- " + draft_text)


class PrMainWorkflowTests(unittest.TestCase):
    """CI-OPT-001-AC-03/04: exact events and per-event concurrency policy."""

    def test_only_supported_pr_activities_and_main_push(self):
        text = read(".github/workflows/verify.yml")
        for term in ("types: [opened, synchronize, reopened, ready_for_review]",
                     "branches: [main]", "workflow_dispatch:", "options: [full]",
                     "base:\n        description: Explicit comparison base (commit or ref)\n        required: true"):
            self.assertIn(term, text)
        for forbidden in ("labeled", "unlabeled", "[skip ci]", "paths:", "paths-ignore:"):
            self.assertNotIn(forbidden, text)

    def test_pr_number_group_cancels_pr_only_and_main_sha_is_retained(self):
        text = read(".github/workflows/verify.yml")
        for term in ("format('verify-pr-{0}', github.event.pull_request.number)",
                     "format('verify-main-{0}', github.sha)",
                     "format('verify-dispatch-{0}-{1}', github.ref, github.run_id)",
                     "cancel-in-progress: ${{ github.event_name == 'pull_request' }}"):
            self.assertIn(term, text)

    def test_fixed_matrix_timeout_and_verification_steps_unchanged(self):
        text = read(".github/workflows/verify.yml")
        offline = text.split("  offline:\n", 1)[1].split("  gate:\n", 1)[0]
        for term in ("fail-fast: false", "os: [windows-latest]",
                     "python: ['3.11', '3.12']", "timeout-minutes: 25", "fetch-depth: 0",
                     "PYTHONPATH: src", "PYTHONDONTWRITEBYTECODE: '1'",
                     "python -X utf8 -m unittest tests.test_gms_optional tests.test_managed_providers",
                     'python -m pip install "cryptography>=42"', "scripts/ci_plan.py --remote run",
                     "BATON_CI_PLAN: ${{ needs.plan.outputs.plan }}",
                     "BATON_CI_DIGEST: ${{ needs.plan.outputs.digest }}"):
            self.assertIn(term, offline)
        self.assertEqual(text.count("matrix:\n"), 1)
        self.assertEqual(text.count("fetch-depth: 0"), 3)
        self.assertEqual(text.count("contents: read"), 1)
        self.assertNotIn("ubuntu", text.lower())
        self.assertNotIn("linux", text.lower())
        self.assertEqual(text.count("runs-on: windows-latest"), 2)
        actions = [line.strip() for line in text.splitlines() if "uses:" in line]
        self.assertEqual(set(actions), {"- uses: actions/checkout@v4", "- uses: actions/setup-python@v5"})
        gate = text.split("  gate:\n", 1)[1]
        for term in ("if: always()", "needs: [plan, offline]", "BATON_CI_NEEDS: ${{ toJSON(needs) }}",
                     "scripts/ci_plan.py --remote gate"):
            self.assertIn(term, gate)
        self.assertIn("scripts/ci_plan.py --remote plan", text)
        for term in ("reuse.allowed", "continue-on-error", "fromJSON", "cache@", "upload-artifact", "download-artifact"):
            self.assertNotIn(term, text)

    def test_docs_explain_branch_push_pr_events_and_conflict_gap(self):
        text = read("README.md")
        for term in (
            "PR 없는 branch push는 CI를 실행하지 않는다",
            "CI는 PR의 `opened`/`synchronize`/`reopened`/`ready_for_review` 이벤트와\n`main` push에서 실행한다",
            "충돌이 있는 PR은 merge ref가 없어 PR CI가 실행되지 않으며",
            "충돌 해결 전에는 검증된 것으로 보지 않는다",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)


class VStageContractTests(unittest.TestCase):
    """Static contract boundaries; these do not claim planner or remote E2E success."""

    def ac(self, number):
        text = read("docs/specs/CI-OPT-001.md")
        rest = text.split(f"### CI-OPT-001-AC-{number:02d}\n", 1)[1]
        return rest.split("\n##", 1)[0]

    def test_single_planner_keeps_shared_task_selection_and_pr_regressions(self):
        spec = read("docs/specs/CI-OPT-001.md")
        self.assertIn("revision = 4", spec)
        self.assertIn('approved_at = "2026-11-13"', spec)
        for term in ("ci_plan.py", "두 번째 정책 엔진은 두지 않는다", "T3a~T3c는 로컬 V2 checkpoint"):
            self.assertIn(term, spec)
        self.assertIn("eligible_tasks(item, tasks, changed)", self.ac(5))
        self.assertIn("basis.requested_base == base", self.ac(6))
        self.assertIn("exit 1", self.ac(6))

    def test_stage_defaults_and_automatic_escalations(self):
        ac = self.ac(7)
        for term in ("in_progress / debugging | V1", "checkpoint / 작업 단위 | V2",
                     "task_complete / pre_merge | V3", "graph_affected", "affected_modules",
                     "required_level()", "L3", ".github/workflows/**", "scripts/verify_environment.py",
                     "dependency/lockfile", "CBM config", "skills/**", "매핑 불가", "이전 범위 밖 실패",
                     "빈 diff/선택 0개", "500개 초과", "V3로 자동 상향", "단계를 올릴 수만"):
            with self.subTest(term=term):
                self.assertIn(term, ac)

    def test_draft_v2_and_ready_main_windows_pair_are_contractual(self):
        ac = self.ac(8)
        for term in ("draft PR은 V2", "ready PR·병합 후보·main push는 V3 full",
                     "ready/main은 항상 Windows 전체 2 matrix", "어떤 입력도 2 미만으로 낮추지 않는다",
                     "Windows 2 matrix에서 테스트 범위만 V2", "V3 fallback", "draft-T0 전용 job은 만들지 않는다"):
            with self.subTest(term=term):
                self.assertIn(term, ac)
        spec = read("docs/specs/CI-OPT-001.md")
        self.assertIn("Linux/Ubuntu 검증은 후속 확장", spec)
        self.assertIn("plan과 gate도 windows-latest", spec)

    def test_graph_freshness_mapping_and_fallback_fail_closed(self):
        ac = self.ac(9)
        for term in ("프로젝트별·git worktree별", "하나의 전역 병합 graph를 만들지 않는다",
                     "index_status", "check_index_coverage", "index_repository", "incremental",
                     "TESTS/TESTS_FILE", "Python unittest", "committed 변경을 누락하지 않는다",
                     "부분 LSP", "CBM 없음", "partial coverage", "V3 full", "SDD FAIL/exit1",
                     "필수 검사 skip/PASS", "Git 자동 커밋", "auto_index=false", ".codebase-memory/"):
            with self.subTest(term=term):
                self.assertIn(term, ac)

    def test_v1_graph_limitations_do_not_force_full_and_tiers_are_distinct(self):
        ac7, ac9 = self.ac(7), self.ac(9)
        self.assertIn("그래프 불완전/조회 실패만으로 full fallback하거나 실패하지 않는다", ac7)
        self.assertIn("직접 변경 파일 검사", ac7)
        self.assertIn("검사 없음은 NOT_RUN", ac7)
        self.assertIn("실제 실행 검사 실패는 V1 실패", ac9)
        self.assertIn("잘못된 root/generation/schema 결과를 폐기", ac9)
        self.assertIn("V2에서 CBM 없음", ac9)
        self.assertIn("partial/fast pass", self.ac(12))
        self.assertIn("V1/V2/V3는 상호 대체하지 않는다", self.ac(13))
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in ("V1=L1 Fast Feedback", "V2=L2 Impact Validation", "V3=L3 Full Validation",
                         "SDD 변경 위험 등급", "검사 없음은 NOT_RUN"):
                self.assertIn(term, text)

    def test_v3_gate_and_reuse_require_complete_matching_evidence(self):
        for term in ("if: always()", "draft=V2 이상", "ready/main/dispatch=V3 full Windows 2",
                     "skip/cancel/fail", "not_configured", "passed로 취급하지 않는다", "유효한 V3"):
            self.assertIn(term, self.ac(11))
        ac = self.ac(12)
        for term in ("코드 상태", "commit SHA", "target base", "Task/AC와 정책", "테스트 설정/명령",
                     "실제 의존성 버전", "환경(OS·Python", "필수 검사 목록/결과", "unknown/partial/누락",
                     "같은 SHA만으로", "tests_run=0", "검사 전후", "CI full Windows 2 job을 재사용으로 생략하지 않는다",
                     "merge-ref SHA/tree", "옛 draft 재실행", "not_run", "원격 E2E passed 근거가 아니다"):
            self.assertIn(term, ac)

    def test_measurements_preserve_unknowns_and_no_new_database(self):
        for term in ("MetricsStore", "task / commit / worktree / target_base", "index_id", "freshness",
                     "selected_tests / total_tests", "graph_seconds / ci_seconds", "escalations", "reuse_decision",
                     "v3_only_defects", "measured / measured_calculation / assumed", "unknown/partial/null",
                     "새 verification DB/table"):
            self.assertIn(term, self.ac(12))
        for term in ("새 검증 DB는 금지", "verify_environment.py", "순차 유지", "ON HOLD/pending", "T4"):
            self.assertIn(term, self.ac(13))

    def test_superseded_pending_items_and_implementation_order(self):
        spec = read("docs/specs/CI-OPT-001.md")
        for item in ("P-02", "P-03", "P-08", "P-09"):
            self.assertRegex(spec, rf"\| {item} \| superseded:")
        for item in ("P-04", "P-05", "P-06 (AC-12/13)"):
            self.assertIn(f"| {item} | re-scoped:", spec)
        plan = read("docs/plans/ci-optimization.md")
        positions = [plan.index(f"작업 T3{letter} —") for letter in "abcd"]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("13 AC", plan)
        self.assertIn("ON HOLD", plan)


if __name__ == "__main__":
    unittest.main()
