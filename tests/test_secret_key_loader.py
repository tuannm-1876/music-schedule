import os
import stat

from secret_key_loader import load_secret_key


def test_uses_existing_env_value(tmp_path, monkeypatch):
    env_file = tmp_path / 'dotenv'
    monkeypatch.setenv('SECRET_KEY', 'from-env')
    assert load_secret_key(str(env_file)) == 'from-env'
    assert not env_file.exists()


def test_generates_and_persists_when_missing(tmp_path, monkeypatch):
    env_file = tmp_path / 'dotenv'
    env_file.write_text('YTDLP_JS_RUNTIME=node')  # no trailing newline on purpose
    monkeypatch.delenv('SECRET_KEY', raising=False)

    key = load_secret_key(str(env_file))

    assert len(key) >= 64
    assert env_file.read_text() == f'YTDLP_JS_RUNTIME=node\nSECRET_KEY={key}\n'
    assert os.environ['SECRET_KEY'] == key
    # Same key on the next start: sessions survive restarts
    monkeypatch.delenv('SECRET_KEY')
    from dotenv import dotenv_values
    assert dotenv_values(str(env_file))['SECRET_KEY'] == key


def test_fills_empty_line_copied_from_example(tmp_path, monkeypatch):
    env_file = tmp_path / 'dotenv'
    env_file.write_text('# comment\nSECRET_KEY=\nYTDLP_JS_RUNTIME=node\n')
    monkeypatch.setenv('SECRET_KEY', '')  # what load_dotenv sets for an empty value

    key = load_secret_key(str(env_file))

    assert env_file.read_text() == f'# comment\nSECRET_KEY={key}\nYTDLP_JS_RUNTIME=node\n'


def test_created_file_is_private(tmp_path, monkeypatch):
    env_file = tmp_path / 'dotenv'
    monkeypatch.delenv('SECRET_KEY', raising=False)
    load_secret_key(str(env_file))
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


def test_blank_value_is_treated_as_missing(tmp_path, monkeypatch):
    env_file = tmp_path / 'dotenv'
    monkeypatch.setenv('SECRET_KEY', '   ')
    assert load_secret_key(str(env_file)).strip() != ''
