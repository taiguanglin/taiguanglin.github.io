"""Tests for utils/config_utils.py"""

import pytest
from pathlib import Path
from unittest.mock import patch

from utils.config_utils import ConfigManager


class TestConfigManager:
    def test_get_book_title_simplified(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        title = mgr.get_book_title(is_traditional=False)
        assert "簡體" in title

    def test_get_book_title_traditional(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        title = mgr.get_book_title(is_traditional=True)
        assert "繁體" in title

    def test_get_book_title_default_when_missing(self, tmp_path):
        empty_cfg = tmp_path / "empty.yaml"
        empty_cfg.write_text("", encoding="utf-8")
        mgr = ConfigManager(config_path=empty_cfg)
        assert mgr.get_book_title(default_title="Fallback") == "Fallback"

    def test_get_i18n_text_simplified(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        text = mgr.get_i18n_text("navigation.home", is_traditional=False)
        assert text == "首页"

    def test_get_i18n_text_traditional(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        text = mgr.get_i18n_text("navigation.home", is_traditional=True)
        assert text == "首頁"

    def test_get_i18n_text_missing_key_returns_default(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        text = mgr.get_i18n_text("nonexistent.key", default="default_val")
        assert text == "default_val"

    def test_missing_config_file_uses_empty_config(self, tmp_path):
        mgr = ConfigManager(config_path=tmp_path / "no_such_file.yaml")
        assert mgr.get_book_title(default_title="X") == "X"

    def test_get_generation_config(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        val = mgr.get_generation_config("generate_traditional")
        assert val is True

    def test_get_generation_config_missing_key(self, config_yaml_path):
        mgr = ConfigManager(config_path=config_yaml_path)
        val = mgr.get_generation_config("no_key", default="fallback")
        assert val == "fallback"

    def test_reload_config(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("book_title:\n  simplified: 'Title1'\n", encoding="utf-8")
        mgr = ConfigManager(config_path=cfg_path)
        assert mgr.get_book_title(is_traditional=False) == "Title1"

        cfg_path.write_text("book_title:\n  simplified: 'Title2'\n", encoding="utf-8")
        mgr.reload_config()
        assert mgr.get_book_title(is_traditional=False) == "Title2"
