"""Long-lived login: 30-day sliding session + one 365-day refresh token per device."""
from datetime import datetime, timedelta

import pytest

import app as app_module

PASSWORD = 'correct horse battery staple'


@pytest.fixture(autouse=True)
def admin_user():
    with app_module.app.app_context():
        app_module.AuthToken.query.delete()
        user = app_module.User.query.filter_by(username='admin').first()
        user.set_password(PASSWORD)
        user.remember_token = None
        app_module.db.session.commit()
        yield user.id


def new_client():
    return app_module.app.test_client()


def login(client):
    resp = client.post('/api/login', json={'username': 'admin', 'password': PASSWORD})
    assert resp.status_code == 200
    return client.get_cookie(app_module.REFRESH_COOKIE).value


def is_authenticated(client):
    return client.get('/api/initial-state').get_json()['is_authenticated']


def device_with_only_refresh_cookie(raw_token):
    """A device whose session cookie is gone (expired, new SECRET_KEY, cleared)."""
    client = new_client()
    client.set_cookie(app_module.REFRESH_COOKIE, raw_token)
    return client


def test_session_lifetime_is_long_and_sliding():
    assert app_module.app.permanent_session_lifetime >= timedelta(days=30)
    assert app_module.app.config['SESSION_REFRESH_EACH_REQUEST'] is True


def test_login_sets_long_refresh_cookie():
    client = new_client()
    resp = client.post('/api/login', json={'username': 'admin', 'password': PASSWORD})
    cookie_header = [h for h in resp.headers.getlist('Set-Cookie') if h.startswith(app_module.REFRESH_COOKIE)][0]
    assert 'HttpOnly' in cookie_header
    assert f'Max-Age={365 * 24 * 3600}' in cookie_header


def test_refresh_token_restores_session():
    raw = login(new_client())
    assert is_authenticated(device_with_only_refresh_cookie(raw))


def test_refresh_token_is_stored_hashed():
    raw = login(new_client())
    with app_module.app.app_context():
        stored = [t.token_hash for t in app_module.AuthToken.query.all()]
    assert raw not in stored and len(stored) == 1


def test_two_devices_stay_logged_in():
    phone = login(new_client())
    laptop = login(new_client())
    assert is_authenticated(device_with_only_refresh_cookie(phone))
    assert is_authenticated(device_with_only_refresh_cookie(laptop))


def test_logout_only_revokes_that_device():
    phone_client = new_client()
    phone = login(phone_client)
    laptop = login(new_client())

    phone_client.get('/api/logout')

    assert not is_authenticated(device_with_only_refresh_cookie(phone))
    assert is_authenticated(device_with_only_refresh_cookie(laptop))


def test_expired_refresh_token_is_rejected():
    raw = login(new_client())
    with app_module.app.app_context():
        token = app_module.AuthToken.query.one()
        token.expires_at = datetime.utcnow() - timedelta(seconds=1)
        app_module.db.session.commit()
    assert not is_authenticated(device_with_only_refresh_cookie(raw))


def test_using_refresh_token_extends_its_expiry():
    raw = login(new_client())
    with app_module.app.app_context():
        token = app_module.AuthToken.query.one()
        token.last_used_at = datetime.utcnow() - timedelta(days=100)
        token.expires_at = datetime.utcnow() + timedelta(days=265)
        app_module.db.session.commit()

    client = device_with_only_refresh_cookie(raw)
    assert is_authenticated(client)

    with app_module.app.app_context():
        token = app_module.AuthToken.query.one()
        assert token.expires_at > datetime.utcnow() + timedelta(days=364)


def test_legacy_remember_token_is_migrated(admin_user):
    with app_module.app.app_context():
        user = app_module.db.session.get(app_module.User, admin_user)
        legacy = user.generate_remember_token()
        app_module.db.session.commit()

    client = new_client()
    client.set_cookie('remember_token', legacy)
    assert is_authenticated(client)

    new_raw = client.get_cookie(app_module.REFRESH_COOKIE)
    assert new_raw is not None
    assert client.get_cookie('remember_token') is None
    assert is_authenticated(device_with_only_refresh_cookie(new_raw.value))


def test_wrong_password_sets_no_cookie():
    client = new_client()
    resp = client.post('/api/login', json={'username': 'admin', 'password': 'nope'})
    assert resp.status_code == 401
    assert client.get_cookie(app_module.REFRESH_COOKIE) is None


def test_admin_password_never_logged(tmp_path, monkeypatch, caplog, capsys):
    monkeypatch.setattr(app_module.app, 'instance_path', str(tmp_path))
    with app_module.app.app_context():
        app_module.User.query.filter_by(username='admin').delete()
        app_module.db.session.commit()
        app_module.init_admin_user()

    password = (tmp_path / 'initial-admin-password.txt').read_text().strip()
    assert len(password) >= 16
    assert (tmp_path / 'initial-admin-password.txt').stat().st_mode & 0o777 == 0o600
    assert password not in caplog.text
    assert password not in capsys.readouterr().out
