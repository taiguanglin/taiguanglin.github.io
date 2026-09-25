"""Tests for utils/text_utils.py"""

import re

import pytest
from utils.text_utils import normalize_text_for_id, simple_hash, TextProcessor, IDGenerator
from config.settings import Settings


@pytest.fixture
def settings():
    return Settings(
        id_content_length=50,
        favicon_search_patterns=["favicon.ico"],
    )


@pytest.fixture
def text_proc(settings):
    return TextProcessor(settings)


@pytest.fixture
def id_gen(settings):
    return IDGenerator(settings)


# ---------------------------------------------------------------------------
# normalize_text_for_id
# ---------------------------------------------------------------------------

class TestNormalizeTextForId:
    def test_empty_string(self):
        assert normalize_text_for_id("") == ""

    def test_none_like_falsy(self):
        assert normalize_text_for_id("") == ""

    def test_strips_whitespace(self):
        assert normalize_text_for_id("  hello  ") == "hello"

    def test_replaces_newlines(self):
        result = normalize_text_for_id("line1\nline2\rline3\t")
        assert "\n" not in result
        assert "\r" not in result
        assert "\t" not in result

    def test_html_entities_decoded(self):
        result = normalize_text_for_id("&nbsp;a&lt;b&gt;c&amp;d")
        assert result == " a<b>c&d"


# ---------------------------------------------------------------------------
# simple_hash
# ---------------------------------------------------------------------------

class TestSimpleHash:
    def test_returns_12_chars(self):
        assert len(simple_hash("hello")) == 12

    def test_deterministic(self):
        assert simple_hash("test") == simple_hash("test")

    def test_different_inputs_give_different_hashes(self):
        assert simple_hash("abc") != simple_hash("xyz")

    def test_empty_string(self):
        h = simple_hash("")
        assert len(h) == 12


# ---------------------------------------------------------------------------
# TextProcessor.process_line_breaks
# ---------------------------------------------------------------------------

class TestProcessLineBreaks:
    def test_newline_to_br(self, text_proc):
        result = text_proc.process_line_breaks("line1\nline2")
        assert "<br>" in result

    def test_windows_newline(self, text_proc):
        result = text_proc.process_line_breaks("line1\r\nline2")
        assert "<br>" in result

    def test_collapses_triple_br(self, text_proc):
        result = text_proc.process_line_breaks("a\n\n\n\nb")
        # More than 2 consecutive <br> should be collapsed
        assert "<br><br><br>" not in result

    def test_preserves_first_line_strips_leading_br(self, text_proc):
        result = text_proc.process_line_breaks("\n\nContent", preserve_first_line=True)
        assert not result.startswith("<br>")

    def test_no_preserve_keeps_leading_br(self, text_proc):
        result = text_proc.process_line_breaks("\nContent", preserve_first_line=False)
        assert result.startswith("<br>")


# ---------------------------------------------------------------------------
# TextProcessor.extract_time_from_text
# ---------------------------------------------------------------------------

class TestExtractTimeFromText:
    def test_standard_datetime(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("2024-02-18 10:47 問題內容")
        assert time == "2024-02-18 10:47"
        assert "問題內容" in remaining

    def test_date_only(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("2024-02-18 問題")
        assert time is not None
        assert "2024" in time

    def test_no_time_returns_none(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("純文字沒有時間")
        assert time is None
        assert remaining == "純文字沒有時間"

    def test_slash_separator(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("2024/02/18 09:00 內容")
        assert time is not None
        assert "-" in time  # normalized to dash


# ---------------------------------------------------------------------------
# TextProcessor.extract_questioner_info
# ---------------------------------------------------------------------------

class TestExtractQuestionerInfo:
    def test_colon_separator(self, text_proc):
        name, content = text_proc.extract_questioner_info("學生甲：這是問題")
        assert name == "學生甲"
        assert content == "這是問題"

    def test_ascii_colon(self, text_proc):
        name, content = text_proc.extract_questioner_info("Student: content here")
        assert name == "Student"
        assert content == "content here"

    def test_no_match(self, text_proc):
        name, content = text_proc.extract_questioner_info("沒有分隔符的文字")
        assert name is None

    # -- 「名字 日期 HH:MM」空格分隔提問頭（2025-05-14 貼吧 恒河沙丫）-----------
    # Word 偶發名字與時間戳之間只有空格、名字後無冒號。時間裡的冒號（19:28）
    # 不可被當成名字分隔符，否則日期與小時會被併進名字、分鐘（28）漏成內文。

    def test_space_separated_header(self, text_proc):
        name, content = text_proc.extract_questioner_info(
            "恒河沙丫 2025-05-14 19:28<br>师父曾讲过极乐世界分九品，分别与娑婆世界的哪些道相对应呢？")
        assert name == "恒河沙丫"
        assert content == "2025-05-14 19:28<br>师父曾讲过极乐世界分九品，分别与娑婆世界的哪些道相对应呢？"

    def test_space_header_time_not_leaked_into_content(self, text_proc):
        # 下游契約：時間戳留在內容開頭，extract_time_from_text 抽出完整時間，
        # 「28」歸入分鐘、不出現在內文（2025-05-14 恒河沙丫回歸問題）。
        _, content = text_proc.extract_questioner_info(
            "恒河沙丫 2025-05-14 19:28<br>师父曾讲过极乐世界分九品，分别与娑婆世界的哪些道相对应呢？")
        time, remaining = text_proc.extract_time_from_text(content)
        assert time == "2025-05-14 19:28"
        assert remaining == "<br>师父曾讲过极乐世界分九品，分别与娑婆世界的哪些道相对应呢？"
        assert not remaining.startswith("28")

    def test_space_header_timestamp_only(self, text_proc):
        # 名字＋時間戳後無內文（問題在後續段落）：時間仍可被抽出
        name, content = text_proc.extract_questioner_info("恒河沙丫 2025-05-14 19:28")
        assert name == "恒河沙丫"
        time, remaining = text_proc.extract_time_from_text(content)
        assert time == "2025-05-14 19:28"
        assert remaining == ""

    def test_space_header_multiple_spaces(self, text_proc):
        name, content = text_proc.extract_questioner_info("苏七念1  2025-01-15 19:26 师父您好")
        assert name == "苏七念1"
        assert content == "2025-01-15 19:26 师父您好"

    def test_colon_header_not_treated_as_space_header(self, text_proc):
        # 標準「名字：日期 HH:MM」仍走冒號切分，不受新格式影響
        name, content = text_proc.extract_questioner_info("學生甲：2024-01-15 10:30 問題內容")
        assert name == "學生甲"
        assert content == "2024-01-15 10:30 問題內容"

    def test_prose_with_date_not_questioner(self, text_proc):
        # 一般段落：名字後接日期但無完整時間戳 → 不誤判為提問人
        name, _ = text_proc.extract_questioner_info("参见 2025-05-14 的开示")
        assert name is None

    def test_prose_no_timestamp_after_name(self, text_proc):
        # 名字開頭但時間不完整（缺分鐘）→ 不誤判為提問人
        name, _ = text_proc.extract_questioner_info("恒河沙丫 2025-05-14 19 请问")
        assert name is None


# ---------------------------------------------------------------------------
# IDGenerator
# ---------------------------------------------------------------------------

class TestIDGenerator:
    def test_stable_qa_id_deterministic_across_instances(self, settings):
        # 「稳定」指跨重建稳定：每次构建都新建解析器/IDGenerator，
        # 首次出现永远得到基底 id。
        id1 = IDGenerator(settings).generate_stable_qa_id("甲", "問題內容", "2024-01-15 10:30", "question")
        id2 = IDGenerator(settings).generate_stable_qa_id("甲", "問題內容", "2024-01-15 10:30", "question")
        assert id1 == id2

    def test_stable_qa_id_has_prefix(self, id_gen):
        qa_id = id_gen.generate_stable_qa_id("甲", "Q", "2024-01-01", "question")
        assert qa_id.startswith("question-")

    def test_stable_qa_id_different_questioner(self, id_gen):
        id1 = id_gen.generate_stable_qa_id("甲", "相同問題", "2024-01-15", "question")
        id2 = id_gen.generate_stable_qa_id("乙", "相同問題", "2024-01-15", "question")
        assert id1 != id2

    def test_generate_content_id_has_prefix(self, id_gen):
        cid = id_gen.generate_content_id("some text content", "content")
        assert cid.startswith("content-")

    def test_generate_content_id_deterministic_across_instances(self, settings):
        a = IDGenerator(settings).generate_content_id("abc", "heading")
        b = IDGenerator(settings).generate_content_id("abc", "heading")
        assert a == b


# ---------------------------------------------------------------------------
# IDGenerator duplicate-id de-duplication
# ---------------------------------------------------------------------------

class TestIDGeneratorDedup:
    def test_first_occurrence_keeps_base_hash(self, id_gen):
        qid = id_gen.generate_stable_qa_id("甲", "問題內容", "2024-01-15 10:30", "question")
        assert re.fullmatch(r"question-[0-9a-f]+", qid)

    def test_duplicate_qa_inputs_get_numeric_suffix(self, id_gen):
        args = ("甲", "問題內容", "2024-01-15 10:30", "question")
        first = id_gen.generate_stable_qa_id(*args)
        second = id_gen.generate_stable_qa_id(*args)
        third = id_gen.generate_stable_qa_id(*args)
        assert second == f"{first}-2"
        assert third == f"{first}-3"

    def test_distinct_content_keeps_distinct_base_ids(self, id_gen):
        a = id_gen.generate_stable_qa_id("甲", "問題一內容", "2024-01-15", "question")
        b = id_gen.generate_stable_qa_id("甲", "問題二內容", "2024-01-15", "question")
        assert a != b
        assert not a.endswith("-2") and not b.endswith("-2")

    def test_duplicate_content_id_gets_suffix(self, id_gen):
        first = id_gen.generate_content_id("同一段內容", "content")
        second = id_gen.generate_content_id("同一段內容", "content")
        assert second == f"{first}-2"

    def test_registry_is_per_instance(self, settings):
        # 登记表跟随实例：新实例（新解析器）重新计数 → 跨重建输出一致
        g1, g2 = IDGenerator(settings), IDGenerator(settings)
        args = ("甲", "問題內容", "2024-01-15 10:30", "question")
        assert g1.generate_stable_qa_id(*args) == g2.generate_stable_qa_id(*args)
        assert g1.generate_stable_qa_id(*args).endswith("-2")
