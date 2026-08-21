from pathlib import Path

from app.internal_token import clean_token, token_from_host_env_file


def test_clean_token_strips_quotes_and_cr():
    assert clean_token(' "abc" \r') == "abc"
    assert clean_token("'xyz'") == "xyz"


def test_token_from_host_env_file(tmp_path: Path):
    p = tmp_path / "host.env"
    p.write_text("FOO=1\nINTERNAL_API_TOKEN=from-file\nBAR=2\n", encoding="utf-8")
    assert token_from_host_env_file(p) == "from-file"


def test_token_from_host_env_missing(tmp_path: Path):
    assert token_from_host_env_file(tmp_path / "nope") == ""
