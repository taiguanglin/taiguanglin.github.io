"""推送前守門：wenda2_ebook/ 必須是固定 12 章的發布版。

``gen_all_and_push.py`` 會 ``git add :/`` 提交整個 repo；若 wenda2_ebook/
只是 21 章底稿，會連同 ebook/ 一起推上線。此守門必須在 commit 前擋下。
"""

from unittest.mock import patch

import gen_all_and_push as gap


def _write_published(directory):
    for ch in range(1, 13):
        for suffix in ("", "_trad"):
            (directory / f"{ch:02d}{suffix}.html").write_text("<html></html>", encoding="utf-8")
    for ch in range(13, 22):
        for suffix in ("", "_trad"):
            (directory / f"{ch:02d}{suffix}.html").write_text("此章節已重新分類", encoding="utf-8")


def test_published_shape_passes(monkeypatch, tmp_path):
    _write_published(tmp_path)
    monkeypatch.setattr(gap, "WENDA2_EBOOK_DIR", tmp_path)
    assert gap.verify_wenda2_ebook_published() is True


def test_draft_chapter_is_rejected(monkeypatch, tmp_path):
    _write_published(tmp_path)
    (tmp_path / "13.html").write_text("<html>完整月度章</html>", encoding="utf-8")
    monkeypatch.setattr(gap, "WENDA2_EBOOK_DIR", tmp_path)
    assert gap.verify_wenda2_ebook_published() is False


def test_main_aborts_before_commit_when_wenda2_is_draft(monkeypatch):
    monkeypatch.setattr(gap, "_load_env_guard", lambda: type("G", (), {
        "reexec_into_venv": staticmethod(lambda *a, **k: None),
    })())
    monkeypatch.setattr("sys.argv", ["gen_all_and_push.py"])
    monkeypatch.setattr(gap, "sync_to_local", lambda: 0)
    monkeypatch.setattr(gap, "rebuild", lambda: 0)
    monkeypatch.setattr(gap, "verify_wenda2_ebook_published", lambda: False)

    with patch.object(gap, "commit_and_push") as commit:
        assert gap.main_entry() == 1
        commit.assert_not_called()
