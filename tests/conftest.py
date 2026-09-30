import functools
import http.server
import shutil
import subprocess
import threading
import time

import pytest


@pytest.fixture
def local_audio_server(tmp_path):
    """Serve a generated 2s tone over HTTP so yt-dlp can be exercised offline."""
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg not installed')
    served = tmp_path / 'served'
    served.mkdir()
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                    str(served / 'tone.mp3')], check=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(served))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()


class _SlowAudioHandler(http.server.BaseHTTPRequestHandler):
    """Streams ~60s worth of bytes so a download can be cancelled mid-flight."""

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Content-Length', str(1024 * 300))
        self.end_headers()
        try:
            for _ in range(300):
                self.wfile.write(b'\0' * 1024)
                self.wfile.flush()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


@pytest.fixture
def slow_audio_server():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _SlowAudioHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()


class _HangingHandler(http.server.BaseHTTPRequestHandler):
    """Sends headers, then goes silent: simulates a stalled download."""

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Content-Length', str(1024 * 1024))
        self.end_headers()
        self.wfile.write(b'\0' * 1024)
        self.wfile.flush()
        time.sleep(60)

    def log_message(self, *args):
        pass


@pytest.fixture
def hanging_audio_server():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _HangingHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()
