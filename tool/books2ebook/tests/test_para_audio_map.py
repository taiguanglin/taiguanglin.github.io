"""`para_audio_map` — 段落時間注入的閘門規則（純邏輯單元測試）。

被測契約（見 `audio_map3/AGENTS.md`）：
1. 只有**講次** `reviewed=true` 的段落才注入（人工校對完成才啟用跟播）。
2. `zero: true`（師父沒念，音檔長度為零）不注入。
3. `end <= start`（零寬／缺時間）不注入。
4. 注入格式為 `data-start`／`data-end`，三位小數。
"""

import json

import pytest

import para_audio_map


@pytest.fixture(autouse=True)
def clear_cache():
    """每個測試都從乾淨的 module cache 開始（load_series 會快取結果）。"""
    para_audio_map._CACHE.clear()
    yield
    para_audio_map._CACHE.clear()


# ``para_audio_map`` 以 module 內的 REPO_ROOT 讀檔；單元測試需要指向 tmp 產物
@pytest.fixture
def series_repo(tmp_path, monkeypatch):
    """造一個假的 <repo>/audio_map3/<series>.json，回傳 (series, 檔案路徑)。"""
    root = tmp_path / "repo"
    (root / "audio_map3").mkdir(parents=True)
    series = "lengqie"
    data = {
        "series": series,
        "lectures": {
            "1": {  # 已校對：有效段落應該注入
                "reviewed": True,
                "paragraphs": [
                    {"pid": "p-saaa0001", "start": 10.0, "end": 20.5},
                    {"pid": "p-saaa0002", "start": 30.25, "end": 45.0},
                    {"pid": "p-saaa0003", "start": 50.0, "end": 50.0},      # 零寬
                    {"pid": "p-saaa0004", "start": 60.0, "end": 70.0,
                     "zero": True},                                          # 零長度
                    {"pid": "p-saaa0005"},                                    # 無時間
                ],
            },
            "2": {  # 未校對：整講都不注入
                "reviewed": False,
                "paragraphs": [
                    {"pid": "p-sbbb0001", "start": 5.0, "end": 15.0},
                ],
            },
        },
    }
    path = root / "audio_map3" / ("%s.json" % series)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(para_audio_map, "REPO_ROOT", str(root))
    para_audio_map._CACHE.clear()
    return series, path


def test_only_reviewed_and_playable_paragraphs_are_injected(series_repo):
    series, _ = series_repo
    got = para_audio_map.load_series(series)
    assert set(got) == {"p-saaa0001", "p-saaa0002"}, (
        "只有 reviewed 講次內 end>start、且未標 zero 的段落可注入")
    assert got["p-saaa0001"] == (10.0, 20.5)
    assert got["p-saaa0002"] == (30.25, 45.0)
    assert "p-saaa0003" not in got, "零寬（end<=start）段落不可注入"
    assert "p-saaa0004" not in got, "zero:true 段落不可注入"
    assert "p-saaa0005" not in got, "沒有時間的段落不可注入"
    assert "p-sbbb0001" not in got, "reviewed=false 的講次不可注入"


def test_zero_width_and_negative_spans_skipped(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "audio_map3").mkdir(parents=True)
    (root / "audio_map3" / "s.json").write_text(json.dumps({
        "lectures": {"1": {"reviewed": True, "paragraphs": [
            {"pid": "p-sneg0001", "start": 30.0, "end": 20.0},   # 負長度
            {"pid": "p-szer0001", "start": -5.0, "end": 10.0},   # 負起點
            {"pid": "p-sstr0001", "start": "x", "end": 10.0},    # 非法型別
            {"pid": "p-sok00001", "start": 0.0, "end": 0.001},   # 合法
        ]}}}
    ), encoding="utf-8")
    monkeypatch.setattr(para_audio_map, "REPO_ROOT", str(root))
    para_audio_map._CACHE.clear()
    assert set(para_audio_map.load_series("s")) == {"p-sok00001"}


def test_flat_shapes_are_accepted(tmp_path, monkeypatch):
    """寬鬆解析：pid→{start,end}、pid→[start,end]、頂層 paragraphs 都要能用。"""
    root = tmp_path / "repo"
    (root / "audio_map3").mkdir(parents=True)
    (root / "audio_map3" / "flat.json").write_text(json.dumps({
        "p-sflat001": {"start": 1.0, "end": 2.0},
        "p-sflat002": [3.0, 4.0],
        "p-sflat003": {"start": 5.0, "end": 5.0, "zero": True},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(para_audio_map, "REPO_ROOT", str(root))
    para_audio_map._CACHE.clear()
    got = para_audio_map.load_series("flat")
    assert got == {"p-sflat001": (1.0, 2.0), "p-sflat002": (3.0, 4.0)}


def test_missing_file_and_bad_json_degrade_to_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(para_audio_map, "REPO_ROOT", str(tmp_path))
    para_audio_map._CACHE.clear()
    assert para_audio_map.load_series("nope") == {}
    (tmp_path / "audio_map3").mkdir()
    (tmp_path / "audio_map3" / "bad.json").write_text("{ not json", encoding="utf-8")
    para_audio_map._CACHE.clear()
    assert para_audio_map.load_series("bad") == {}
    assert para_audio_map.load_series("") == {}


def test_para_time_attrs_format(series_repo):
    series, _ = series_repo
    assert para_audio_map.para_time_attrs(series, "p-saaa0001") == \
        ' data-start="10.000" data-end="20.500"'
    assert para_audio_map.para_time_attrs(series, "p-saaa0003") == ""  # 零寬
    assert para_audio_map.para_time_attrs(series, "p-unknown0001") == ""
    assert para_audio_map.para_time_attrs("", "p-saaa0001") == ""


# 小說明：conftest 的 autouse fixture 會清 cache，這裡再確認清乾淨
def test_cache_is_reused(series_repo):
    series, path = series_repo
    first = para_audio_map.load_series(series)
    path.write_text('{"lectures": {}}', encoding="utf-8")
    assert para_audio_map.load_series(series) == first, "同一次執行應命中 _CACHE"