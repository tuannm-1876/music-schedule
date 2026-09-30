"""Flask SECRET_KEY from the project's dotenv file, generated once if missing."""
import logging
import os
import re
import secrets

logger = logging.getLogger(__name__)

EMPTY_KEY_LINE = re.compile(r'^\s*(export\s+)?SECRET_KEY\s*=\s*(["\']{2})?\s*$')


def load_secret_key(env_path):
    """Return SECRET_KEY from the environment.

    When it is missing, generate a random key and store it in `env_path` so the
    same key is reused after a restart (otherwise every restart would log
    everybody out and invalidate CSRF tokens). An existing empty `SECRET_KEY=`
    line (as copied from .env.example) is filled in rather than duplicated.
    """
    key = os.getenv('SECRET_KEY', '').strip()
    if key:
        return key

    key = secrets.token_hex(32)
    _write_key(env_path, key)
    os.environ['SECRET_KEY'] = key
    logger.warning(f"SECRET_KEY was not set; generated a new one and saved it to {env_path}")
    return key


def _write_key(env_path, key):
    entry = f'SECRET_KEY={key}\n'
    lines = []
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            lines = f.readlines()

    for i, line in enumerate(lines):
        if EMPTY_KEY_LINE.match(line):
            lines[i] = entry
            break
    else:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        lines.append(entry)

    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.writelines(lines)
