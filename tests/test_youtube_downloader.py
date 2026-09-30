import os
import time

import pytest

import youtube_downloader as ytd


@pytest.mark.parametrize('url, expected', [
    ('https://www.youtube.com/watch?v=abc123', 'single'),
    ('https://youtu.be/abc123', 'single'),
    ('https://www.youtube.com/shorts/abc123', 'single'),
    ('https://www.youtube.com/watch?v=abc123&list=RDabc123&start_radio=1', 'single'),
    ('https://youtu.be/abc123?list=RDabc123', 'single'),
    ('https://www.youtube.com/watch?v=abc123&list=PLxyz', 'playlist'),
    ('https://www.youtube.com/playlist?list=PLxyz', 'playlist'),
    ('https://music.youtube.com/playlist?list=OLAK5uy_x', 'playlist'),
    ('  https://www.youtube.com/playlist?list=PLxyz  ', 'playlist'),
])
def test_classify_url(url, expected):
    assert ytd.classify_url(url) == expected


@pytest.mark.parametrize('url, allowed', [
    ('https://www.youtube.com/watch?v=abc', True),
    ('https://m.youtube.com/watch?v=abc', True),
    ('https://music.youtube.com/playlist?list=PL1', True),
    ('https://youtu.be/abc', True),
    ('http://192.168.1.1/admin', False),
    ('https://evilyoutube.com/watch?v=abc', False),
    ('https://youtube.com.evil.io/watch?v=abc', False),
    ('file:///etc/passwd', False),
    ('youtube.com/watch?v=abc', False),
])
def test_is_allowed_url(url, allowed):
    assert ytd.is_allowed_url(url) is allowed


@pytest.mark.parametrize('raw, fragment', [
    ("ERROR: [youtube] x: Sign in to confirm you’re not a bot", 'bot'),
    ('ERROR: [youtube] x: Sign in to confirm your age', 'độ tuổi'),
    ('ERROR: [youtube] x: Private video', 'riêng tư'),
    ('ERROR: [youtube] x: Unable to download API page: [SSL: CERTIFICATE_VERIFY_FAILED] certificate '
     'verify failed: unable to get local issuer certificate', 'tường lửa'),
    ('ERROR: [youtube] x: Unable to download webpage: HTTP Error 403', 'Unable to download webpage'),
])
def test_friendly_error(raw, fragment):
    assert fragment in ytd.friendly_error(raw)


def test_parse_line():
    assert ytd.DownloadJob._parse_line('@@P  42.5%') == {'type': 'progress', 'percent': 42.5}
    assert ytd.DownloadJob._parse_line('@@S {"id": "a", "title": "T"}') == {'type': 'start', 'id': 'a', 'title': 'T'}
    assert ytd.DownloadJob._parse_line('@@P N/A') is None
    assert ytd.DownloadJob._parse_line('[download] random') is None


def test_build_command_single_uses_env(monkeypatch):
    monkeypatch.setenv('YTDLP_JS_RUNTIME', 'node')
    monkeypatch.setenv('YTDLP_JS_RUNTIME_PATH', '/usr/bin/node')
    monkeypatch.setenv('YTDLP_COOKIES_FILE', '/tmp/cookies.txt')
    cmd = ytd.build_command('https://youtu.be/x', is_playlist=False)
    assert '--no-playlist' in cmd
    assert cmd[cmd.index('--js-runtimes') + 1] == 'node:/usr/bin/node'
    assert cmd[cmd.index('--cookies') + 1] == '/tmp/cookies.txt'
    assert cmd[-2:] == ['--', 'https://youtu.be/x']


def test_build_command_playlist_without_env(monkeypatch):
    for name in ('YTDLP_JS_RUNTIME', 'YTDLP_COOKIES_FILE'):
        monkeypatch.delenv(name, raising=False)
    cmd = ytd.build_command('https://www.youtube.com/playlist?list=PL1', is_playlist=True)
    assert '--yes-playlist' in cmd and '--ignore-errors' in cmd
    assert '--js-runtimes' not in cmd and '--cookies' not in cmd


def test_download_job_end_to_end(tmp_path, monkeypatch, local_audio_server):
    music_dir = tmp_path / 'music'
    monkeypatch.setattr(ytd, 'MUSIC_DIR', str(music_dir))
    monkeypatch.setattr(ytd, 'INCOMING_DIR', str(music_dir / '.incoming'))

    events = list(ytd.DownloadJob(f'{local_audio_server}/tone.mp3').events())

    done = [e for e in events if e['type'] == 'done']
    assert len(done) == 1 and os.path.isfile(done[0]['filepath'])
    assert done[0]['filepath'].endswith('.mp3')
    assert events[-1] == {'type': 'finished', 'returncode': 0, 'cancelled': False, 'error': None}
    assert not (music_dir / '.incoming').exists()


def test_download_job_reports_error(tmp_path, monkeypatch, local_audio_server):
    monkeypatch.setattr(ytd, 'MUSIC_DIR', str(tmp_path / 'music'))
    monkeypatch.setattr(ytd, 'INCOMING_DIR', str(tmp_path / 'music' / '.incoming'))

    events = list(ytd.DownloadJob(f'{local_audio_server}/missing.mp3').events())

    assert events[-1]['type'] == 'finished'
    assert events[-1]['returncode'] != 0 and events[-1]['error']


def test_download_job_cancel_mid_download(tmp_path, monkeypatch, slow_audio_server):
    monkeypatch.setattr(ytd, 'MUSIC_DIR', str(tmp_path / 'music'))
    monkeypatch.setattr(ytd, 'INCOMING_DIR', str(tmp_path / 'music' / '.incoming'))
    job = ytd.DownloadJob(f'{slow_audio_server}/slow.mp3')

    started = time.monotonic()
    events = []
    for event in job.events():
        events.append(event)
        if event['type'] == 'progress':
            job.cancel()

    assert time.monotonic() - started < 15
    assert events[-1]['type'] == 'finished' and events[-1]['cancelled'] is True
    assert not (tmp_path / 'music' / '.incoming').exists()
    assert not list((tmp_path / 'music').glob('*.mp3'))


def test_download_job_cancel_before_start(tmp_path, monkeypatch):
    monkeypatch.setattr(ytd, 'INCOMING_DIR', str(tmp_path / '.incoming'))
    job = ytd.DownloadJob('https://youtu.be/abc')
    job.cancel()
    events = list(job.events())
    assert events == [{'type': 'finished', 'returncode': None, 'cancelled': True, 'error': None}]
    assert job.process is None


def test_download_job_watchdog_kills_stalled_download(tmp_path, monkeypatch, hanging_audio_server):
    monkeypatch.setattr(ytd, 'MUSIC_DIR', str(tmp_path / 'music'))
    monkeypatch.setattr(ytd, 'INCOMING_DIR', str(tmp_path / 'music' / '.incoming'))
    monkeypatch.setattr(ytd, 'STALL_TIMEOUT', 3)

    started = time.monotonic()
    events = list(ytd.DownloadJob(f'{hanging_audio_server}/hang.mp3').events())

    assert time.monotonic() - started < 25
    assert events[-1]['type'] == 'finished' and events[-1]['returncode'] != 0
