"""Tests for main.py - Word2EBookConverter and argument parsing."""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from main import Word2EBookConverter, create_argument_parser
from models.document_models import ConversionConfig, Chapter
from config.settings import DEFAULT_SETTINGS


# ---------------------------------------------------------------------------
# create_argument_parser
# ---------------------------------------------------------------------------

class TestCreateArgumentParser:
    def test_basic_args(self):
        parser = create_argument_parser()
        args = parser.parse_args(["input.docx", "output/"])
        assert args.input_file == "input.docx"
        assert args.output_folder == "output/"

    def test_skip_index_flag(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--skip-index"])
        assert args.skip_index is True

    def test_skip_traditional_flag(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--skip-traditional"])
        assert args.skip_traditional is True

    def test_skip_simplified_flag(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--skip-simplified"])
        assert args.skip_simplified is True

    def test_fast_flag(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--fast"])
        assert args.fast is True

    def test_defaults_are_false(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/"])
        assert args.skip_index is False
        assert args.skip_traditional is False
        assert args.skip_simplified is False
        assert args.fast is False


# ---------------------------------------------------------------------------
# Word2EBookConverter
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_input_file(tmp_path):
    f = tmp_path / "test.docx"
    f.touch()
    return f


@pytest.fixture
def conversion_config(mock_input_file, tmp_path):
    return ConversionConfig(
        input_file=mock_input_file,
        output_folder=tmp_path / "output",
    )


@pytest.fixture
def sample_chapters():
    return [
        Chapter(title="第一章", filename="01.html"),
        Chapter(title="第二章", filename="02.html"),
    ]


class TestWord2EBookConverter:
    def test_converter_initialises(self, conversion_config):
        converter = Word2EBookConverter(conversion_config, DEFAULT_SETTINGS)
        assert converter.config is conversion_config
        assert converter.settings is DEFAULT_SETTINGS

    def test_setup_output_directory_full_rebuild(self, conversion_config, tmp_path):
        converter = Word2EBookConverter(conversion_config, DEFAULT_SETTINGS)
        converter._setup_output_directory()
        assert conversion_config.output_folder.exists()

    def test_setup_output_directory_incremental(self, conversion_config):
        """Incremental update when skipping some generation."""
        cfg = ConversionConfig(
            input_file=conversion_config.input_file,
            output_folder=conversion_config.output_folder,
            generate_simplified=False,  # skip simplified → incremental
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)
        converter._setup_output_directory()
        assert cfg.output_folder.exists()

    def test_convert_calls_pipeline(self, conversion_config, sample_chapters):
        """Convert should call parse → generate pages → generate index → static assets."""
        converter = Word2EBookConverter(conversion_config, DEFAULT_SETTINGS)

        with (
            patch.object(converter, "_setup_output_directory") as mock_setup,
            patch.object(converter.html_generator, "copy_favicon_after_setup"),
            patch.object(
                converter.document_parser, "parse_document",
                return_value=(sample_chapters, {})
            ) as mock_parse,
            patch.object(converter.html_generator, "generate_chapter_pages") as mock_chapters,
            patch.object(converter.html_generator, "generate_index_pages") as mock_index,
            patch.object(converter.search_generator, "generate_search_indexes") as mock_search,
            patch.object(converter, "_generate_static_assets") as mock_assets,
            patch.object(converter, "_show_completion_info"),
        ):
            converter.convert()

        mock_setup.assert_called_once()
        mock_parse.assert_called_once()
        mock_chapters.assert_called_once()
        mock_index.assert_called_once()
        mock_search.assert_called_once()
        mock_assets.assert_called_once()

    def test_convert_skips_search_when_flag_false(self, tmp_path, mock_input_file, sample_chapters):
        cfg = ConversionConfig(
            input_file=mock_input_file,
            output_folder=tmp_path / "output",
            generate_search=False,
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)

        with (
            patch.object(converter, "_setup_output_directory"),
            patch.object(converter.html_generator, "copy_favicon_after_setup"),
            patch.object(
                converter.document_parser, "parse_document",
                return_value=(sample_chapters, {})
            ),
            patch.object(converter.html_generator, "generate_chapter_pages"),
            patch.object(converter.html_generator, "generate_index_pages"),
            patch.object(converter.search_generator, "generate_search_indexes") as mock_gen,
            patch.object(
                converter.search_generator, "ensure_search_index_files"
            ) as mock_ensure,
            patch.object(converter, "_generate_static_assets"),
            patch.object(converter, "_show_completion_info"),
        ):
            converter.convert()

        mock_gen.assert_not_called()
        mock_ensure.assert_called_once()

    def test_generate_static_assets_writes_css_and_js(self, conversion_config):
        converter = Word2EBookConverter(conversion_config, DEFAULT_SETTINGS)
        conversion_config.output_folder.mkdir(parents=True, exist_ok=True)
        for sub in ["assets/css", "assets/js"]:
            (conversion_config.output_folder / sub).mkdir(parents=True, exist_ok=True)

        with (
            patch.object(converter.file_manager, "write_file") as mock_write,
            patch.object(converter.assets_manager, "get_full_css_content", return_value="css"),
            patch.object(converter.assets_manager, "get_full_js_content", return_value="js"),
        ):
            converter._generate_static_assets()

        written_filenames = [c.args[0] for c in mock_write.call_args_list]
        assert any("style.css" in f for f in written_filenames)
        assert any("script.js" in f for f in written_filenames)


# ---------------------------------------------------------------------------
# main() function - CLI integration
# ---------------------------------------------------------------------------

class TestMainFunction:
    def test_main_exits_on_missing_file(self, tmp_path, capsys):
        from main import main
        with patch("sys.argv", ["main.py", str(tmp_path / "nonexistent.docx"), str(tmp_path / "out")]):
            main()  # Should return early (no sys.exit), but print error
        captured = capsys.readouterr()
        assert "不存在" in captured.out or "error" in captured.out.lower()

    def test_main_exits_on_bad_extension(self, tmp_path, capsys):
        from main import main
        bad = tmp_path / "book.txt"
        bad.touch()
        with patch("sys.argv", ["main.py", str(bad), str(tmp_path / "out")]):
            main()
        captured = capsys.readouterr()
        assert "格式" in captured.out or "不支持" in captured.out

    def test_main_skip_both_versions_exits(self):
        from main import main
        with patch("sys.argv", ["main.py", "in.docx", "out/", "--skip-traditional", "--skip-simplified"]):
            with pytest.raises(SystemExit):
                main()
