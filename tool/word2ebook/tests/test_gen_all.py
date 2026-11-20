"""gen_all.py 預設路徑與設定測試。"""

from pathlib import Path

from gen_all import (
    DOCX_FILE,
    OUTPUT_FOLDER,
    PDF_FILE,
    PDF_FILE_NOV_MAR,
    PDF_FILES,
    REPO_ROOT,
    TOOL_DIR,
    build_config,
    create_argument_parser,
    run,
    verify_published_output,
)


def test_gen_all_repo_layout():
    assert TOOL_DIR.name == "word2ebook"
    assert REPO_ROOT == TOOL_DIR.parent.parent
    assert DOCX_FILE.parent.name == "問答錄2"
    assert PDF_FILE.parent == DOCX_FILE.parent
    assert PDF_FILE_NOV_MAR.parent == DOCX_FILE.parent
    assert PDF_FILES == [PDF_FILE, PDF_FILE_NOV_MAR]
    assert OUTPUT_FOLDER.name == "wenda2_ebook"


def test_build_config_full_rebuild():
    config = build_config()
    assert config.input_file == DOCX_FILE
    assert config.output_folder == OUTPUT_FOLDER
    assert config.pdf_files == PDF_FILES
    assert config.pdf_file == PDF_FILE  # 相容：第一份
    assert config.qa_folder is None
    assert config.generate_search is True
    assert config.generate_traditional is True
    assert config.generate_simplified is True
    assert config.only_word is False
    assert config.only_pdf is False
    assert config.only_qa is False


def test_gen_all_source_paths_exist():
    """在正式 repo 中，預設來源路徑應存在。"""
    assert DOCX_FILE.exists(), f"missing {DOCX_FILE}"
    assert PDF_FILE.exists(), f"missing {PDF_FILE}"
    assert PDF_FILE_NOV_MAR.exists(), f"missing {PDF_FILE_NOV_MAR}"


# ---------------------------------------------------------------------------
# 發布版固定 12 章：預設三段全跑；--draft-only 只供重新分類。
# ---------------------------------------------------------------------------


def _stub_conversion(monkeypatch, calls):
    monkeypatch.setattr("gen_all.reexec_into_venv", lambda *a, **k: None)
    monkeypatch.setattr("gen_all.ensure_locked_pymupdf", lambda: None)
    monkeypatch.setattr("gen_all.validate_paths", lambda: True)

    class DummyConverter:
        def __init__(self, config, settings):
            pass

        def convert(self):
            calls.append("convert")

    monkeypatch.setattr("main.Word2EBookConverter", DummyConverter)


def test_run_defaults_to_full_three_stage_pipeline(monkeypatch):
    calls = []
    _stub_conversion(monkeypatch, calls)
    monkeypatch.setattr(
        "gen_all.run_classified_stages",
        lambda: calls.append("classified") or 0,
    )
    monkeypatch.setattr("gen_all.verify_published_output", lambda: True)

    assert run() == 0
    assert calls == ["convert", "classified"]


def test_run_draft_only_stops_before_classification(monkeypatch):
    calls = []
    _stub_conversion(monkeypatch, calls)
    monkeypatch.setattr(
        "gen_all.run_classified_stages",
        lambda: calls.append("classified") or 0,
    )

    assert run(draft_only=True) == 0
    assert calls == ["convert"]


def test_run_fails_when_published_shape_is_wrong(monkeypatch):
    calls = []
    _stub_conversion(monkeypatch, calls)
    monkeypatch.setattr("gen_all.run_classified_stages", lambda: 0)
    monkeypatch.setattr("gen_all.verify_published_output", lambda: False)

    assert run() == 1


def test_draft_only_flag():
    parser = create_argument_parser()
    assert parser.parse_args([]).draft_only is False
    assert parser.parse_args(["--draft-only"]).draft_only is True


def test_verify_published_output_requires_twelve_chapters(monkeypatch, tmp_path):
    out = tmp_path / "wenda2_ebook"
    out.mkdir()
    for ch in range(1, 13):
        for suffix in ("", "_trad"):
            (out / f"{ch:02d}{suffix}.html").write_text("<html></html>", encoding="utf-8")
    for ch in range(13, 22):
        for suffix in ("", "_trad"):
            (out / f"{ch:02d}{suffix}.html").write_text("此章節已重新分類", encoding="utf-8")
    (out / "index.html").write_text('<a href="12.html"></a>', encoding="utf-8")
    (out / "index_trad.html").write_text('<a href="12_trad.html"></a>', encoding="utf-8")

    monkeypatch.setattr("gen_all.OUTPUT_FOLDER", out)
    assert verify_published_output() is True

    # 13.html 變回完整月度章 → 必須被擋下
    (out / "13.html").write_text("完整章節", encoding="utf-8")
    assert verify_published_output() is False

    # 目錄又列出 13 章 → 必須被擋下
    (out / "13.html").write_text("此章節已重新分類", encoding="utf-8")
    (out / "index.html").write_text('<a href="13.html"></a>', encoding="utf-8")
    assert verify_published_output() is False
