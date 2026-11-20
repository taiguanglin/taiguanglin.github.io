"""發布版固定 12 章：PDF 條目覆蓋率守門。

stage 2 抽出的每一則 PDF 問答都必須在版控分類結果
（``classified/batch_*.jsonl``）中有紀錄。新 PDF 月份若尚未分類，
stage 3 必須失敗，不能靜默漏掉——否則線上電子書會少幾個月。
"""

import json

import pytest

import gen_classified as gc


def _write_items(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_batches(directory, rows):
    (directory / "batch_001.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_unclassified_pdf_item_aborts(monkeypatch, tmp_path):
    build = tmp_path / "build"
    classified = tmp_path / "classified"
    build.mkdir()
    classified.mkdir()
    _write_items(build / "items.jsonl", [{"seq": 1, "qid": "question-new"}])
    _write_batches(classified, [{"i": 2, "ch": 12}])

    monkeypatch.setattr(gc, "BUILD", build)
    monkeypatch.setattr(gc, "CLASSIFIED_DIR", classified)

    with pytest.raises(SystemExit) as exc:
        gc.extract_pdf_items({})
    assert exc.value.code == 1


def test_all_pdf_items_classified_are_merged(monkeypatch, tmp_path):
    build = tmp_path / "build"
    classified = tmp_path / "classified"
    build.mkdir()
    classified.mkdir()
    _write_items(
        build / "items.jsonl",
        [
            {
                "seq": 1,
                "qid": "question-1",
                "aid": "answer-1",
                "q_parts": ["問"],
                "a_parts": ["答"],
                "time": "2025-06-09",
                "who": "某某",
            }
        ],
    )
    _write_batches(classified, [{"i": 1, "ch": 12, "l2": 1, "l3": 13}])

    monkeypatch.setattr(gc, "BUILD", build)
    monkeypatch.setattr(gc, "CLASSIFIED_DIR", classified)

    items = gc.extract_pdf_items({})
    assert len(items) == 1
    assert items[0]["qid"] == "question-1"
    assert items[0]["path"] == "12-01-13"
