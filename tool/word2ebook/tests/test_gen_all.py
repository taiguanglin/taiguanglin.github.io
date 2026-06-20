"""gen_all.py 預設路徑與設定測試。"""

from pathlib import Path

from gen_all import (
    DOCX_FILE,
    OUTPUT_FOLDER,
    PDF_FILE,
    QA_FOLDER,
    REPO_ROOT,
    TOOL_DIR,
    build_config,
)


def test_gen_all_repo_layout():
    assert TOOL_DIR.name == "word2ebook"
    assert REPO_ROOT == TOOL_DIR.parent.parent
    assert DOCX_FILE.parent.name == "問答錄2"
    assert PDF_FILE.parent == DOCX_FILE.parent
    assert QA_FOLDER.name == "qa"
    assert OUTPUT_FOLDER.name == "wenda2_ebook"


def test_build_config_full_rebuild():
    config = build_config()
    assert config.input_file == DOCX_FILE
    assert config.output_folder == OUTPUT_FOLDER
    assert config.pdf_file == PDF_FILE
    assert config.qa_folder == QA_FOLDER
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
    assert QA_FOLDER.is_dir(), f"missing {QA_FOLDER}"
