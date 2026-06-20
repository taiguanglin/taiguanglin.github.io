"""gen_all_and_push.py 測試。"""

from gen_all import REPO_ROOT, TOOL_DIR
from gen_all_and_push import DEFAULT_COMMIT_MESSAGE, create_argument_parser


def test_gen_all_and_push_repo_layout():
    assert TOOL_DIR.name == "word2ebook"
    assert REPO_ROOT == TOOL_DIR.parent.parent


def test_default_commit_message():
    assert DEFAULT_COMMIT_MESSAGE == "New txt changes to new wenda2ebook"


def test_custom_commit_message_arg():
    parser = create_argument_parser()
    args = parser.parse_args(["-m", "更新 QA 校稿"])
    assert args.message == "更新 QA 校稿"
