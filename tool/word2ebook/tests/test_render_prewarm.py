"""19-render-prewarm.js（背景預熱）的守門測試。

背景：電子書頁面對 ``.question``/``.answer``/``.para-block``/``article.qa-pair``
設了 ``content-visibility: auto``，視窗外的區塊不排版也不繪製——使用者向下
捲動時要等瀏覽器「跑到附近」才渲染。本模組在背景把視窗下方一段區間的區塊
提前渲染好，讓捲動幾乎不用等待。

本檔鎖住：
* 模組與 CSS 規則確實進入產出的 ``script.js`` / ``style.css``；
* 模組行為（預熱區範圍、進出預熱區、圖片預熱、分批、頁面類別守門）
  ——由 node harness 執行（無 node 時略過）。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from templates.static_assets import StaticAssetsManager

HARNESS = Path(__file__).resolve().parent / "render_prewarm_harness.js"
ASSETS = Path(__file__).resolve().parents[1] / "assets"


class TestRenderPrewarmAssets:

    def test_js_module_exists(self):
        assert (ASSETS / "js" / "modules" / "19-render-prewarm.js").exists()

    def test_css_rule_exists(self):
        css = (ASSETS / "css" / "modules" / "00-base.css").read_text(encoding="utf-8")
        assert ".w2e-prewarmed" in css
        assert "content-visibility: visible" in css

    def test_js_module_in_bundled_output(self):
        manager = StaticAssetsManager(ASSETS)
        js = manager.get_full_js_content()
        assert "19-render-prewarm.js" in js
        assert "w2e-prewarmed" in js
        # 預熱區：視窗下方三屏
        assert "BELOW" in js

    def test_css_rule_in_bundled_output(self):
        manager = StaticAssetsManager(ASSETS)
        css = manager.get_full_css_content()
        assert ".w2e-prewarmed" in css


class TestRenderPrewarmBehaviour:

    @pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 才能執行 JS harness")
    def test_node_harness_passes(self):
        result = subprocess.run(
            ["node", str(HARNESS)],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
