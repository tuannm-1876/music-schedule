"""/add-music runs under the real eventlet hub, with yt-dlp fetching from a local HTTP server."""
import pytest

import app as app_module  # conftest.py points DATABASE_URL at a temp DB first
import youtube_downloader as ytd


@pytest.fixture
def client(tmp_path, monkeypatch):
    music_dir = tmp_path / 'music'
    monkeypatch.setattr(ytd, 'MUSIC_DIR', str(music_dir))
    monkeypatch.setattr(ytd, 'INCOMING_DIR', str(music_dir / '.incoming'))
    monkeypatch.setattr(ytd, 'ALLOWED_HOSTS', ytd.ALLOWED_HOSTS + ('127.0.0.1',))
    emitted = []
    monkeypatch.setattr(app_module.socketio, 'emit', lambda name, data=None, **kw: emitted.append((name, data)))
    app_module.app.config['WTF_CSRF_ENABLED'] = False
    with app_module.app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 1
        c.emitted = emitted
        yield c
    app_module.download_job = None


def wait_for_job(timeout=60):
    waited = 0.0
    while app_module.download_job is not None and waited < timeout:
        app_module.eventlet.sleep(0.1)
        waited += 0.1
    assert app_module.download_job is None, 'download job did not finish'


def test_add_music_queues_and_persists_song(client, local_audio_server):
    resp = client.post('/add-music', json={'url': f'{local_audio_server}/tone.mp3'})
    assert resp.status_code == 202 and resp.get_json()['queued'] is True

    wait_for_job()

    statuses = [data['status'] for name, data in client.emitted if name == 'download_progress']
    assert statuses[0] == 'starting' and statuses[-1] == 'completed'
    added = [data for name, data in client.emitted if name == 'song_added']
    assert len(added) == 1 and any(s['title'] == 'tone' for s in added[0]['songs'])
    with app_module.app.app_context():
        song = app_module.Song.query.filter_by(title='tone').one()
        assert song.source == 'youtube' and song.duration >= 1


def test_add_music_rejects_second_job(client):
    app_module.download_job = object()
    resp = client.post('/add-music', json={'url': 'https://youtu.be/abc'})
    assert resp.status_code == 409


@pytest.mark.parametrize('url', ['not a url', 'http://192.168.1.1/router', 'https://example.com/a.mp3'])
def test_add_music_rejects_non_youtube_url(client, url):
    assert client.post('/add-music', json={'url': url}).status_code == 400


def test_add_music_rejected_while_updating_ytdlp(client, monkeypatch):
    monkeypatch.setattr(app_module, 'ytdlp_updating', True)
    assert client.post('/add-music', json={'url': 'https://youtu.be/abc'}).status_code == 409


def test_add_music_reports_error(client, local_audio_server):
    resp = client.post('/add-music', json={'url': f'{local_audio_server}/missing.mp3'})
    assert resp.status_code == 202

    wait_for_job()

    last = [data for name, data in client.emitted if name == 'download_progress'][-1]
    assert last['status'] == 'error' and last['message'] and last['active'] is False
