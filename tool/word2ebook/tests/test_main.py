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

    def test_pdf_arg(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--pdf", "answers.pdf"])
        assert args.pdf_files == ["answers.pdf"]

    def test_pdf_arg_repeatable(self):
        parser = create_argument_parser()
        args = parser.parse_args([
            "in.docx", "out/", "--pdf", "a.pdf", "--pdf", "b.pdf",
        ])
        assert args.pdf_files == ["a.pdf", "b.pdf"]

    def test_only_word_and_only_pdf_flags(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--only-word"])
        assert args.only_word is True
        assert args.only_pdf is False
        args2 = parser.parse_args(["in.docx", "out/", "--pdf", "a.pdf", "--only-pdf"])
        assert args2.only_pdf is True

    def test_only_word_and_only_pdf_mutually_exclusive(self):
        parser = create_argument_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["in.docx", "out/", "--only-word", "--only-pdf"])

    def test_pdf_start_index_default_and_custom(self):
        parser = create_argument_parser()
        assert parser.parse_args(["in.docx", "out/"]).pdf_start_index == 12
        args = parser.parse_args(["in.docx", "out/", "--pdf-start-index", "5"])
        assert args.pdf_start_index == 5

    def test_qa_arg(self):
        parser = create_argument_parser()
        args = parser.parse_args(["in.docx", "out/", "--qa", "qa/"])
        assert args.qa_folder == "qa/"

    def test_only_qa_flag(self):
        parser = create_argument_parser()
        args = parser.parse_args(["-", "out/", "--qa", "qa/", "--only-qa"])
        assert args.only_qa is True
        assert args.only_word is False
        assert args.only_pdf is False

    def test_only_qa_mutually_exclusive_with_others(self):
        parser = create_argument_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["in.docx", "out/", "--only-qa", "--only-pdf"])
        with pytest.raises(SystemExit):
            parser.parse_args(["in.docx", "out/", "--only-qa", "--only-word"])

    def test_qa_start_index_default_and_custom(self):
        parser = create_argument_parser()
        assert parser.parse_args(["in.docx", "out/"]).qa_start_index == 16
        args = parser.parse_args(["in.docx", "out/", "--qa-start-index", "20"])
        assert args.qa_start_index == 20


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

    def test_parse_chapters_concatenates_word_and_pdf(self, mock_input_file, tmp_path):
        pdf = tmp_path / "answers.pdf"
        pdf.touch()
        cfg = ConversionConfig(
            input_file=mock_input_file,
            output_folder=tmp_path / "output",
            pdf_files=[pdf],
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)
        word_chs = [Chapter(title=f"{i:02d}", filename=f"{i:02d}.html") for i in range(1, 13)]
        pdf_chs = [Chapter(title="13六月", filename="13.html")]

        with (
            patch.object(converter.document_parser, "parse_document",
                         return_value=(word_chs, {})),
            patch.object(converter.pdf_parser, "parse", return_value=pdf_chs) as mock_pdf,
        ):
            chapters = converter._parse_chapters()

        # PDF parser invoked with start_index == number of word chapters (12)
        mock_pdf.assert_called_once()
        assert mock_pdf.call_args.kwargs.get("start_index") == 12
        assert len(chapters) == 13

    def test_parse_chapters_concatenates_multiple_pdfs(self, mock_input_file, tmp_path):
        pdf1 = tmp_path / "a.pdf"
        pdf2 = tmp_path / "b.pdf"
        pdf1.touch()
        pdf2.touch()
        cfg = ConversionConfig(
            input_file=mock_input_file,
            output_folder=tmp_path / "output",
            pdf_files=[pdf1, pdf2],
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)
        word_chs = [Chapter(title=f"{i:02d}", filename=f"{i:02d}.html") for i in range(1, 13)]
        pdf1_chs = [Chapter(title=f"{i}", filename=f"{i:02d}.html") for i in range(13, 17)]
        pdf2_chs = [Chapter(title=f"{i}", filename=f"{i:02d}.html") for i in range(17, 22)]

        def parse_side_effect(path, start_index=12):
            if Path(path) == pdf1:
                assert start_index == 12
                return pdf1_chs
            assert Path(path) == pdf2
            assert start_index == 16
            return pdf2_chs

        with (
            patch.object(converter.document_parser, "parse_document",
                         return_value=(word_chs, {})),
            patch.object(converter.pdf_parser, "parse", side_effect=parse_side_effect) as mock_pdf,
        ):
            chapters = converter._parse_chapters()

        assert mock_pdf.call_count == 2
        assert len(chapters) == 21
        assert converter.html_generator.extra_source_files == [pdf1, pdf2]
        assert converter.html_generator.include_qa_source is False

    def test_parse_chapters_concatenates_word_pdf_and_qa(self, mock_input_file, tmp_path):
        pdf = tmp_path / "answers.pdf"
        pdf.touch()
        qa_dir = tmp_path / "qa"
        qa_dir.mkdir()
        cfg = ConversionConfig(
            input_file=mock_input_file,
            output_folder=tmp_path / "output",
            pdf_files=[pdf],
            qa_folder=qa_dir,
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)
        word_chs = [Chapter(title=f"{i:02d}", filename=f"{i:02d}.html") for i in range(1, 13)]
        pdf_chs = [Chapter(title=f"{i}月", filename=f"{i}.html") for i in range(13, 17)]
        qa_chs = [Chapter(title="17十一月", filename="17.html", is_qa=True)]

        with (
            patch.object(converter.document_parser, "parse_document",
                         return_value=(word_chs, {})),
            patch.object(converter.pdf_parser, "parse", return_value=pdf_chs) as mock_pdf,
            patch.object(converter.qa_parser, "parse_folder", return_value=qa_chs) as mock_qa,
        ):
            chapters = converter._parse_chapters()

        # QA parser chained after Word(12) + PDF(4) → start_index == 16
        mock_pdf.assert_called_once()
        assert mock_pdf.call_args.kwargs.get("start_index") == 12
        mock_qa.assert_called_once()
        assert mock_qa.call_args.kwargs.get("start_index") == 16
        assert len(chapters) == 17

    def test_only_qa_partial_uses_start_index_and_skips_word_pdf(self, tmp_path):
        qa_dir = tmp_path / "qa"
        qa_dir.mkdir()
        cfg = ConversionConfig(
            input_file=Path("-"),
            output_folder=tmp_path / "output",
            qa_folder=qa_dir,
            only_qa=True,
            generate_search=False,
            qa_start_index=16,
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)
        qa_chs = [Chapter(title="17十一月", filename="17.html", is_qa=True)]

        with (
            patch.object(converter, "_setup_output_directory"),
            patch.object(converter.html_generator, "copy_favicon_after_setup"),
            patch.object(converter.document_parser, "parse_document") as mock_word,
            patch.object(converter.pdf_parser, "parse") as mock_pdf,
            patch.object(converter.qa_parser, "parse_folder", return_value=qa_chs) as mock_qa,
            patch.object(converter.html_generator, "generate_chapter_pages") as mock_pages,
            patch.object(converter.html_generator, "generate_index_pages") as mock_index,
            patch.object(converter.search_generator, "generate_search_indexes") as mock_search,
            patch.object(converter.search_generator, "ensure_search_index_files") as mock_ensure,
            patch.object(converter, "_generate_static_assets"),
            patch.object(converter, "_show_completion_info"),
        ):
            converter.convert()

        mock_word.assert_not_called()           # only-qa does not parse docx
        mock_pdf.assert_not_called()             # only-qa does not parse pdf
        mock_qa.assert_called_once()
        assert mock_qa.call_args.kwargs.get("start_index") == 16
        mock_pages.assert_called_once()
        mock_index.assert_not_called()           # partial mode: index preserved
        mock_search.assert_not_called()          # partial mode: search preserved
        mock_ensure.assert_not_called()

    def test_only_pdf_partial_skips_index_and_search(self, mock_input_file, tmp_path):
        pdf = tmp_path / "answers.pdf"
        pdf.touch()
        cfg = ConversionConfig(
            input_file=mock_input_file,
            output_folder=tmp_path / "output",
            pdf_files=[pdf],
            only_pdf=True,
            generate_search=False,
            pdf_start_index=12,
        )
        converter = Word2EBookConverter(cfg, DEFAULT_SETTINGS)
        pdf_chs = [Chapter(title="13六月", filename="13.html")]

        with (
            patch.object(converter, "_setup_output_directory"),
            patch.object(converter.html_generator, "copy_favicon_after_setup"),
            patch.object(converter.document_parser, "parse_document") as mock_word,
            patch.object(converter.pdf_parser, "parse", return_value=pdf_chs) as mock_pdf,
            patch.object(converter.html_generator, "generate_chapter_pages") as mock_pages,
            patch.object(converter.html_generator, "generate_index_pages") as mock_index,
            patch.object(converter.search_generator, "generate_search_indexes") as mock_search,
            patch.object(converter.search_generator, "ensure_search_index_files") as mock_ensure,
            patch.object(converter, "_generate_static_assets"),
            patch.object(converter, "_show_completion_info"),
        ):
            converter.convert()

        mock_word.assert_not_called()          # only-pdf does not parse docx
        mock_pdf.assert_called_once()
        assert mock_pdf.call_args.kwargs.get("start_index") == 12
        mock_pages.assert_called_once()
        mock_index.assert_not_called()         # partial mode: index preserved
        mock_search.assert_not_called()        # partial mode: search preserved
        mock_ensure.assert_not_called()

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

    def test_main_only_pdf_without_pdf_exits(self):
        from main import main
        with patch("sys.argv", ["main.py", "in.docx", "out/", "--only-pdf"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_only_qa_without_qa_exits(self):
        from main import main
        with patch("sys.argv", ["main.py", "-", "out/", "--only-qa"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_missing_qa_folder_returns(self, tmp_path, capsys):
        from main import main
        docx = tmp_path / "book.docx"
        docx.touch()
        with patch("sys.argv", ["main.py", str(docx), str(tmp_path / "out"),
                                "--qa", str(tmp_path / "no_such_qa")]):
            main()
        captured = capsys.readouterr()
        assert "QA" in captured.out and "不存在" in captured.out

    def test_main_missing_pdf_file_returns(self, tmp_path, capsys):
        from main import main
        docx = tmp_path / "book.docx"
        docx.touch()
        with patch("sys.argv", ["main.py", str(docx), str(tmp_path / "out"),
                                "--pdf", str(tmp_path / "nope.pdf")]):
            main()
        captured = capsys.readouterr()
        assert "PDF" in captured.out and "不存在" in captured.out
