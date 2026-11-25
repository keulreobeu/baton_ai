"""ADAPT-001 AC-01/02/03/07/08/09: route, replan and coordinator rules are present where agents read them."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDD = "docs/sdd.md"
SPEC = "docs/specs/ADAPT-001.md"
HEADING = "## 작업 준비 Route와 재계획 (ADAPT-001)"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(name, heading=HEADING):
    text = read(name)
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end < 0 else text[start:end]


REQ_OF_AC = {1: 1, 2: 1, 3: 1, 7: 1, 8: 1, 9: 1, 4: 2, 5: 2, 6: 2}


# Only backtick fences forbid a backtick anywhere in the opening line's info string.
FENCE = re.compile(r" {0,3}(`{3,}(?=[^`]*$)|~{3,})")


def closes(line, fence):
    """A closing fence: same character, at least as long as the opening, only whitespace after."""
    match = re.fullmatch(r" {0,3}(%s{%d,})[ \t]*" % (re.escape(fence[0]), len(fence)), line)
    return match is not None


def outside_fences(text):
    """The text with every fenced code block blanked (line count kept): a heading inside one is not a heading."""
    lines, fence = [], None
    for line in text.split("\n"):
        marker = FENCE.match(line)
        if fence is None and marker:
            fence = marker.group(1)
            lines.append("")
        elif fence is not None:
            lines.append("")
            if closes(line, fence):
                fence = None
        else:
            lines.append(line)
    return "\n".join(lines)


def headed_block(text, heading, label):
    """The block from the single line that is exactly `heading` (optionally followed by a title) up to the
    next heading of the same or a higher level. Fenced code blocks are ignored."""
    text = outside_fences(text)
    level = len(heading.split(" ", 1)[0])
    found = list(re.finditer(r"(?m)^" + re.escape(heading) + r"(?:[ \t].*)?$", text))
    if len(found) != 1:
        raise ValueError("Spec %s missing or repeated" % label)
    end = re.compile(r"(?m)^#{1,%d} " % level).search(text, found[0].end())
    return text[found[0].start():] if end is None else text[found[0].start():end.start()]


def spec_req(number, text):
    """The `## ADAPT-001-REQ-NN` section of the Spec, up to the next level-2 heading."""
    return headed_block(text, "## ADAPT-001-REQ-%02d" % number, "REQ-%02d section" % number)


def spec_ac(number, text=None):
    """The body of one Spec AC item: an exact `### ADAPT-001-AC-NN` line heading, outside any fenced code
    block, inside the REQ section that owns it."""
    text = read(SPEC) if text is None else text
    heading, label = "### ADAPT-001-AC-%02d" % number, "AC-%02d item" % number
    headed_block(text, heading, label)  # exactly one real heading in the whole Spec
    try:
        return headed_block(spec_req(REQ_OF_AC[number], text), heading, label)
    except ValueError:
        raise ValueError("Spec AC-%02d item is not inside REQ-%02d" % (number, REQ_OF_AC[number])) from None


def move_spec_ac_to_appendix(number, text):
    """A Spec copy where the whole AC item (heading and body) moved to an appendix at the end."""
    body = spec_ac(number, text)
    return text.replace(body, "").rstrip("\n") + "\n\n## 부록\n\n" + body.rstrip("\n") + "\n"


def fence_spec_ac(number, text, level="###", fence=("```markdown", "```")):
    """A Spec copy where the AC item stays inside its REQ section but is wrapped in a fenced code block
    (optionally with another heading level or fence lines), so it is no longer a real heading."""
    body = spec_ac(number, text)
    item = body.rstrip("\n").replace("### ", level + " ", 1)
    return text.replace(body, fence[0] + "\n" + item + "\n" + fence[1] + "\n\n", 1)


def drop_spec_ac(number, text, keep_text_elsewhere=True):
    """A Spec copy without the AC item; optionally its sentences moved into the revision history."""
    body = spec_ac(number, text)
    copy = text.replace(body, "")
    if keep_text_elsewhere:
        moved = body.split("\n", 1)[1]
        copy = copy.replace("## Revision 이력\n", "## Revision 이력\n\n" + moved + "\n", 1)
    return copy


AGENTS_HEADING = "## 작업 준비 Route와 재계획 — ADAPT-001"
COORDINATOR = "코디네이터"
ACTS = ("구현", "수정", "편집", "작성", "커밋")
NEGATIONS = ("않", "금지", "못", "없")
PERMITS = ("직접", "local", "로컬", "예외적", "할 수 있", "해도 된", "해도 좋", "가능", "허용", "단독",
           # assignment/responsibility and plain direct assertion ("...을 담당한다", "...을 한다")
           "담당", "맡", "책임", "수행", "한다")


# Only an explicit assignment of the act itself to the Worker: "<act>[·<act>]은/는 Worker가/이 ...".
# "코드 수정 후 Worker에게 인계한다" does not assign the act and stays a coordinator sentence (ADAPT-R4-03).
# A comma is not a list joiner: "코디네이터가 직접 구현, 수정은 Worker가 한다" keeps its own coordinator act (ADAPT-R5-02).
WORKER_OWNS_ACT = re.compile(r"(?:\s*[·와과]\s*(?:%s))*(?:은|는)\s+Worker(?:가|이)\s" % "|".join(ACTS))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def coordinator_implementation_sentences(text):
    """Sentences where the coordinator, with a permission/direct marker, performs a non-negated change act."""
    hits = []
    for sentence in sentences(text):
        if COORDINATOR not in sentence or not any(p in sentence for p in PERMITS):
            continue
        for match in re.finditer("|".join(ACTS), sentence):
            tail = sentence[match.end():]
            if WORKER_OWNS_ACT.match(tail):
                continue  # the sentence assigns this act to the Worker ("수정은 Worker가 한다")
            if not any(n in tail[:10] for n in NEGATIONS):
                hits.append(sentence)
                break
    return hits


def adapt_rule_texts():
    """Every ADAPT rule location agents read: the SDD section, the AGENTS pointer section and the Spec."""
    return {SDD: section(SDD), "AGENTS.md": section("AGENTS.md", AGENTS_HEADING), SPEC: read(SPEC)}


class AdaptRouteDocsTests(unittest.TestCase):
    TERMS = (
        "Route는 위험 등급이 아니라 구현 준비 절차다",
        "Route는 L을 낮추지 않는다",
        "L3는 항상 A이고 L2 이상은 C가 될 수 없다",
        "필수 검증·독립 검토·사용자 승인을 바꾸지 않는다",
        "Task 본문 `## Route` 절",
        "Worker 호출마다 반복하지 않는다",
        "승인된 Plan/ADR이 이번 설계를 덮지 못하거나 재계획이 발동했을 때",
        "생략 근거를 남긴다",
    )

    def test_route_terms_present_in_sdd(self):
        text = section(SDD)
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_agents_points_to_the_single_rule_location(self):
        agents = read("AGENTS.md")
        self.assertIn("## 작업 준비 Route와 재계획 — ADAPT-001 (2026-11-22)", agents)
        self.assertIn("L을 낮추지 않고 필수 검증·독립 검토·사용자 승인을 바꾸지 않는다", agents)
        self.assertIn('"작업 준비 Route와 재계획" 절', agents)
        template = read("docs/templates/task.md")
        self.assertIn("`## Route`", template)
        self.assertIn("Route는 L을 낮추지 않는다", template)


class AdaptReplanDocsTests(unittest.TestCase):
    TERMS = (
        "같은 근본 원인의 차단 결함이 두 회차 연속",
        "여러 모듈의 공통 불변식 위반 반복",
        "독립 검토 PASS 뒤 공식 검증에서 설계 가정이 깨짐",
        "`원인:` 태그",
        "`### 재계획 판단`",
        "재계획하지 않기로 해도 근거를 남긴다",
        "검토자의 PASS/FAIL 판정이 재계획 판단을 대체하지 않는다",
        "범위 축소·기능 분리는 사용자 결정이며 이력을 지우지 않는다",
        "두 회차는 운영 가설이다",
    )

    def test_replan_terms_present_in_sdd(self):
        text = section(SDD)
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)


class AdaptCoordinatorDocsTests(unittest.TestCase):
    TERMS = (
        "코디네이터는 모든 Route·runtime에서 구현하지 않는다",
        "코디네이터는 Worker 소유 worktree·scope에 쓰지 않고 위임·검증·통합만 한다",
        "저비용/고성능 모드는 기본값 묶음일 뿐 별도 승인 체계가 아니다",
        "모델 ID는 문서에 고정하지 않고 설치된 CLI·Orca에서 확인하며 임의로 대체하지 않는다",
        "독립 검토는 다른 provider를 우선한다",
        "기본 작성자 1명과 검토자 1명",
        "HANDOFF resume → current.md 해당 절 → Task TOML과 최신 절",
        "스킬·Hook 파일 존재는 실행 가능을 뜻하지 않는다",
        "Memory(untrusted)",
    )

    def test_coordinator_model_and_loading_terms_present_in_sdd(self):
        text = section(SDD)
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_skill_guide_limits_large_planning_skill(self):
        text = read("docs/development-skills.md")
        self.assertIn("B·C는 대형 계획 스킬을 로드하지 않는다", text)
        self.assertIn("파일 존재는 실행 가능을 뜻하지 않으며", text)


class AdaptCoordinatorNoImplementationTests(unittest.TestCase):
    """rev2 decision 2: no ADAPT rule sentence lets the coordinator implement (removed rev1 wording or a new one)."""

    REMOVED = (
        "local Task는 단일 작성자인 코디네이터가 구현할 수 있다",
        "코디네이터가 구현할 수 있다",
        "코디네이터가 직접 구현",
    )
    FILES = ("AGENTS.md", SDD, SPEC, "docs/templates/task.md", "docs/development-skills.md")

    INSERTED = (
        "local Task는 단일 작성자인 코디네이터가 구현할 수 있다.",
        "긴급한 경우 코디네이터가 예외적으로 테스트를 직접 수정한다.",
        "코디네이터는 local runtime에서 설정 파일을 편집해도 된다.",
        "Route C에서는 코디네이터가 Spec을 직접 작성하고 커밋한다.",
        "코디네이터의 직접 구현은 L1에서 허용한다.",
        "코디네이터가 코드 수정을 담당한다.",
        "테스트 작성과 커밋은 코디네이터가 맡는다.",
        "Spec 편집 책임은 코디네이터에게 있으며 코디네이터가 이를 수행한다.",
        "코디네이터가 코드 수정 후 Worker에게 인계한다.",  # ADAPT-R4-03: Worker named, act not assigned to it
        "코디네이터가 구현하고 검토는 Worker가 한다.",
    )
    ALLOWED = (
        "코디네이터는 판단만 하고 수정은 Worker가 한다.",
        "코디네이터는 기록만 하며 구현·수정은 Worker가 한다.",
        "코디네이터는 판단만 하고 구현 · 수정은 Worker가 한다.",
        "코디네이터는 기록만 하며 구현· 수정은 Worker가 한다.",
        "코디네이터는 판단만 하고 편집과 작성은 Worker가 한다.",
    )

    def test_removed_coordinator_implementation_wording_is_absent(self):
        for name in self.FILES:
            text = read(name)
            for phrase in self.REMOVED:
                with self.subTest(file=name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_no_sentence_lets_the_coordinator_implement(self):
        for name, text in adapt_rule_texts().items():
            with self.subTest(file=name):
                self.assertEqual(coordinator_implementation_sentences(text), [])

    def test_detector_fails_on_copies_with_an_inserted_permission_sentence(self):
        for name, text in adapt_rule_texts().items():
            for inserted in self.INSERTED:
                copy = text.rstrip("\n") + "\n" + inserted + "\n"
                with self.subTest(file=name, inserted=inserted):
                    self.assertEqual(coordinator_implementation_sentences(copy), [inserted])

    def test_worker_exception_needs_an_explicit_assignment(self):
        for sentence in self.ALLOWED:
            with self.subTest(allowed=sentence):
                self.assertEqual(coordinator_implementation_sentences(sentence), [])
        for sentence in self.INSERTED[-2:] + self.COMMA_JOINED:
            with self.subTest(detected=sentence):
                self.assertEqual(coordinator_implementation_sentences(sentence), [sentence])

    # ADAPT-R5-02: a comma does not join a separate coordinator act into the Worker assignment.
    COMMA_JOINED = ("코디네이터가 직접 구현, 수정은 Worker가 한다.",)

    def test_comma_joined_coordinator_act_is_detected_in_rule_texts(self):
        for name, text in adapt_rule_texts().items():
            for inserted in self.COMMA_JOINED:
                copy = text.rstrip("\n") + "\n" + inserted + "\n"
                with self.subTest(file=name, inserted=inserted):
                    self.assertEqual(coordinator_implementation_sentences(copy), [inserted])

    def test_spec_routes_never_let_the_coordinator_implement(self):
        self.assertIn("어느 Route에서도 코디네이터는 구현하지 않는다", spec_ac(1))
        self.assertIn("재계획 판단은 기록이며 그 뒤 수정은 Worker가 한다", spec_ac(2))
        self.assertIn("코디네이터는 모든 Route·runtime에서 구현하지 않고", spec_ac(3))
        self.assertIn("구현 금지 검사는 문장 단위 문자열 검사", read(SPEC))


class AdaptFenceVariantTests(unittest.TestCase):
    """ADAPT-R5-03: AC-07..09 inside any CommonMark fence (indent 0-3, ``` or ~~~, longer outer fence) are hidden."""

    def test_inline_backticks_before_an_ac_preserve_its_heading(self):
        spec = read(SPEC)
        for number in (7, 8, 9):
            heading = "### ADAPT-001-AC-%02d" % number
            inline = "   ```inline example```\n\n"
            copy = spec.replace(heading + "\n", inline + heading + "\n", 1)
            with self.subTest(ac=number):
                self.assertEqual(spec_ac(number, copy), spec_ac(number, spec))

    def test_inline_backticks_before_a_duplicate_ac_leave_it_visible(self):
        spec = read(SPEC)
        for number in (7, 8, 9):
            duplicate = "\n\n   ```inline example```\n\n### ADAPT-001-AC-%02d\n\n중복 항목\n" % number
            with self.subTest(ac=number), self.assertRaisesRegex(ValueError, "AC-%02d item missing or repeated" % number):
                spec_ac(number, spec + duplicate)

    def test_indented_backtick_and_tilde_fences_hide_the_item(self):
        spec = read(SPEC)
        for number in (7, 8, 9):
            for indent in range(4):
                for char in "`~":
                    fence = " " * indent + char * 3
                    with self.subTest(ac=number, fence=repr(fence)), self.assertRaises(ValueError):
                        spec_ac(number, fence_spec_ac(number, spec, fence=(fence + "markdown", fence)))

    def test_shorter_or_annotated_inner_fence_does_not_close_the_block(self):
        spec = read(SPEC)
        for number in (7, 8, 9):
            for opening, inner, closing in (("````markdown", "```", "````"), ("~~~~", "~~~", "~~~~"),
                                            ("```", "```not-a-close", "```"), ("~~~", "```", "~~~"),
                                            ("~~~`info`", "```", "~~~")):
                copy = fence_spec_ac(number, spec, fence=(opening + "\n" + inner, closing))
                with self.subTest(ac=number, opening=opening, inner=inner), self.assertRaises(ValueError):
                    spec_ac(number, copy)

    def test_fence_closing_rules(self):
        text = "```\n# a\n````  \n# b\n~~~~\n# c\n~~~\n# d\n~~~~ \n# e"
        self.assertEqual(outside_fences(text).split("\n"), ["", "", "", "# b", "", "", "", "", "", "# e"])


class AdaptCoordinatorRoleTests(unittest.TestCase):
    """AC-07: what the coordinator writes, and what only Workers change."""

    COORDINATOR = "코디네이터가 직접 쓰는 것은 Task 상태·결정 근거·승인 대기·증거 참조·`docs/tasks/current.md`·HANDOFF·브리핑 기록뿐이며 검증·승인 결과를 근거 없이 바꾸지 않는다"
    WORKER = "코드·테스트·설정·Spec·ADR·SDD·AGENTS·Skill·템플릿·traceability 변경은 Worker가 한다"

    def check(self, spec_text):
        item = spec_ac(7, spec_text)
        for term in (self.COORDINATOR, self.WORKER):
            self.assertIn(term, item)

    def test_role_boundary_in_sdd_and_spec(self):
        for term in (self.COORDINATOR, self.WORKER):
            with self.subTest(file=SDD, term=term):
                self.assertIn(term, section(SDD))
        self.check(read(SPEC))

    def test_check_fails_without_the_ac_item(self):
        spec = read(SPEC)
        for keep in (True, False):
            with self.subTest(keep_text_elsewhere=keep), self.assertRaises((AssertionError, ValueError)):
                self.check(drop_spec_ac(7, spec, keep))

    def test_check_fails_when_the_whole_item_moves_to_an_appendix(self):
        with self.assertRaises(ValueError):
            self.check(move_spec_ac_to_appendix(7, read(SPEC)))

    def test_check_fails_when_the_item_moves_into_a_code_block(self):
        spec = read(SPEC)
        for level in ("###", "####"):
            with self.subTest(level=level), self.assertRaises(ValueError):
                self.check(fence_spec_ac(7, spec, level))
        with self.subTest(level="#### heading"), self.assertRaises(ValueError):
            self.check(spec.replace("### ADAPT-001-AC-07\n", "#### ADAPT-001-AC-07\n", 1))

    def test_agents_pointer_names_role_scope(self):
        self.assertIn("코디네이터 역할 범위(구현하지 않음)", read("AGENTS.md"))


class AdaptBatchApprovalTests(unittest.TestCase):
    """AC-08: Worker runs are approved per Task scope; anything wider needs a separate approval."""

    TERMS = (
        "Worker 실행은 Task별 승인 scope 안에서 일괄 승인하며 그 안의 Worker 배정마다 다시 승인받지 않는다",
        "scope 확대·새 비용/권한·외부 게시·환경 변경은 별도 승인이다",
    )

    def check(self, spec_text):
        item = spec_ac(8, spec_text)
        for term in self.TERMS + ("일괄 승인은 실제 모델 호출·GMS·스케줄러·전원·push 제한을 풀지 않는다",):
            self.assertIn(term, item)

    def test_batch_approval_in_sdd_and_spec(self):
        for term in self.TERMS:
            with self.subTest(file=SDD, term=term):
                self.assertIn(term, section(SDD))
        self.check(read(SPEC))
        self.assertIn("Task별 Worker 일괄 승인", read("AGENTS.md"))

    def test_check_fails_without_the_ac_item(self):
        spec = read(SPEC)
        for keep in (True, False):
            with self.subTest(keep_text_elsewhere=keep), self.assertRaises((AssertionError, ValueError)):
                self.check(drop_spec_ac(8, spec, keep))

    def test_check_fails_when_the_whole_item_moves_to_an_appendix(self):
        with self.assertRaises(ValueError):
            self.check(move_spec_ac_to_appendix(8, read(SPEC)))

    def test_check_fails_when_the_item_moves_into_a_code_block(self):
        spec = read(SPEC)
        for level in ("###", "####"):
            with self.subTest(level=level), self.assertRaises(ValueError):
                self.check(fence_spec_ac(8, spec, level))
        with self.subTest(level="#### heading"), self.assertRaises(ValueError):
            self.check(spec.replace("### ADAPT-001-AC-08\n", "#### ADAPT-001-AC-08\n", 1))


class AdaptModelMismatchTests(unittest.TestCase):
    """AC-09: mismatches are recorded only; Orca-reported and provider-verified models stay separate."""

    TERMS = (
        "모델 불일치는 기록만 하며 실행을 막거나 모델을 바꾸지 않는다",
        "Orca 보고 모델과 Provider 세션 검증 모델을 구분해 적",
    )

    def check(self, spec_text):
        item = spec_ac(9, spec_text)
        for term in self.TERMS + ("확인할 수 없는 값은 unknown이며 추정으로 채우지 않는다",):
            self.assertIn(term, item)

    def test_mismatch_rule_in_sdd_and_spec(self):
        for term in self.TERMS:
            with self.subTest(file=SDD, term=term):
                self.assertIn(term, section(SDD))
        self.assertIn("확인할 수 없는 값은 unknown이다", section(SDD))
        self.check(read(SPEC))

    def test_check_fails_without_the_ac_item(self):
        spec = read(SPEC)
        for keep in (True, False):
            with self.subTest(keep_text_elsewhere=keep), self.assertRaises((AssertionError, ValueError)):
                self.check(drop_spec_ac(9, spec, keep))

    def test_check_fails_when_the_whole_item_moves_to_an_appendix(self):
        with self.assertRaises(ValueError):
            self.check(move_spec_ac_to_appendix(9, read(SPEC)))

    def test_check_fails_when_the_item_moves_into_a_code_block(self):
        spec = read(SPEC)
        for level in ("###", "####"):
            with self.subTest(level=level), self.assertRaises(ValueError):
                self.check(fence_spec_ac(9, spec, level))
        with self.subTest(level="#### heading"), self.assertRaises(ValueError):
            self.check(spec.replace("### ADAPT-001-AC-09\n", "#### ADAPT-001-AC-09\n", 1))
