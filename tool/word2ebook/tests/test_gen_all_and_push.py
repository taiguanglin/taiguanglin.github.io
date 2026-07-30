"""gen_all_and_push.py 測試。"""

from unittest.mock import patch

from gen_all import REPO_ROOT, TOOL_DIR
from gen_all_and_push import (
    DEFAULT_COMMIT_MESSAGE,
    create_argument_parser,
    main,
    sync_to_local,
)


def test_gen_all_and_push_repo_layout():
    assert TOOL_DIR.name == "word2ebook"
    assert REPO_ROOT == TOOL_DIR.parent.parent


def test_default_commit_message():
    assert DEFAULT_COMMIT_MESSAGE == "Rebuild wenda2_ebook from Word + PDFs"


def test_custom_commit_message_arg():
    parser = create_argument_parser()
    args = parser.parse_args(["-m", "更新 QA 校稿"])
    assert args.message == "更新 QA 校稿"


def test_sync_to_local_runs_git_pull():
    with patch("gen_all_and_push._run_git") as run_git:
        run_git.return_value.returncode = 0
        run_git.return_value.stdout = "Already up to date."
        run_git.return_value.stderr = ""
        assert sync_to_local() == 0
        run_git.assert_called_once_with(["pull"], check=False)


def test_main_skips_build_when_pull_fails():
    with patch("sys.argv", ["gen_all_and_push.py"]):
        with patch("gen_all_and_push.sync_to_local", return_value=1) as sync:
            with patch("gen_all_and_push.gen_all_main") as gen_all:
                assert main() == 1
                sync.assert_called_once()
                gen_all.assert_not_called()
