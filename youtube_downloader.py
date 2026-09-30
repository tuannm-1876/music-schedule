"""YouTube download helpers.

yt-dlp runs as a child process (not in-process) so that:
- the eventlet hub is never blocked by yt-dlp's CPU-heavy extraction,
- a download can be cancelled by killing the process,
- memory is fully released after each job (Pi 3B+ only has 1GB RAM),
- an upgraded yt-dlp is picked up on the next download without a restart.
"""
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
from importlib import metadata
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, 'music')
INCOMING_DIR = os.path.join(MUSIC_DIR, '.incoming')

AUDIO_QUALITY = os.getenv('YTDLP_AUDIO_QUALITY', '128K')
MAX_PLAYLIST_ITEMS = int(os.getenv('YTDLP_MAX_PLAYLIST_ITEMS', '200'))
UPDATE_TIMEOUT = 600  # pip on a Pi 3B+ is slow
# Kill yt-dlp if it prints nothing for this long (hung network/ffmpeg). ffmpeg on a
# Pi 3B+ can stay silent for minutes while converting a long mix, so keep it generous.
STALL_TIMEOUT = int(os.getenv('YTDLP_STALL_TIMEOUT', '900'))
TERMINATE_GRACE = 5  # seconds between SIGTERM and SIGKILL

# Only YouTube hosts are accepted: yt-dlp's generic extractor would otherwise fetch
# any URL, including addresses on the Pi's LAN
ALLOWED_HOSTS = ('youtube.com', 'youtu.be', 'youtube-nocookie.com')

# Markers printed by yt-dlp so stdout can be parsed line by line
START_MARK, PROGRESS_MARK, DONE_MARK = '@@S ', '@@P ', '@@D '

# Known yt-dlp error fragments -> user-facing hint
ERROR_HINTS = [
    ('javascript runtime', 'Thiếu JS runtime (Deno/Node) trên máy chủ, xem README mục yt-dlp'),
    ('not a bot', 'YouTube chặn vì nghi là bot, cần cấu hình YTDLP_COOKIES_FILE'),
    ('confirm your age', 'Video giới hạn độ tuổi, cần cookies của tài khoản đã xác minh'),
    ('private video', 'Video ở chế độ riêng tư'),
    ('video unavailable', 'Video không tồn tại hoặc đã bị xóa'),
    ('requested format is not available', 'Không lấy được định dạng âm thanh, thử cập nhật yt-dlp'),
    ('ffmpeg not found', 'Thiếu ffmpeg trên máy chủ'),
]


def is_allowed_url(url):
    parsed = urlparse(url.strip())
    host = (parsed.hostname or '').lower()
    return parsed.scheme in ('http', 'https') and any(
        host == allowed or host.endswith('.' + allowed) for allowed in ALLOWED_HOSTS)


def classify_url(url):
    """Return 'playlist' or 'single'.

    A watch URL carrying an auto-generated mix (list=RD...) is treated as a
    single video, otherwise yt-dlp would pull an almost endless radio mix.
    """
    parsed = urlparse(url.strip())
    list_id = parse_qs(parsed.query).get('list', [''])[0]
    if not list_id:
        return 'single'
    has_video = 'v' in parse_qs(parsed.query) or parsed.netloc.endswith('youtu.be')
    if has_video and list_id.startswith('RD'):
        return 'single'
    return 'playlist'


def friendly_error(raw):
    lowered = (raw or '').lower()
    for fragment, hint in ERROR_HINTS:
        if fragment in lowered:
            return hint
    return (raw or 'Lỗi không xác định').replace('ERROR: ', '')[:300]


def build_command(url, is_playlist):
    cmd = [
        sys.executable, '-m', 'yt_dlp',
        '--no-update', '--newline', '--progress', '--progress-delta', '1',
        '-f', 'bestaudio[ext=m4a]/bestaudio/best',
        '-x', '--audio-format', 'mp3', '--audio-quality', AUDIO_QUALITY,
        '--restrict-filenames', '--no-overwrites',
        '-o', '%(title).80B_%(id)s.%(ext)s',
        '-P', f'home:{MUSIC_DIR}', '-P', f'temp:{INCOMING_DIR}',
        '--socket-timeout', '30', '--retries', '5',
        '--fragment-retries', '5', '--extractor-retries', '3',
        '--progress-template', f'download:{PROGRESS_MARK}%(progress._percent_str)s',
        '--print', f'before_dl:{START_MARK}%(.{{id,title,playlist_index,n_entries}})j',
        '--print', f'after_move:{DONE_MARK}%(.{{id,title,duration,filepath}})j',
    ]
    if is_playlist:
        cmd += ['--yes-playlist', '--ignore-errors', '--playlist-end', str(MAX_PLAYLIST_ITEMS)]
    else:
        cmd.append('--no-playlist')

    runtime = os.getenv('YTDLP_JS_RUNTIME', '').strip()
    if runtime:
        runtime_path = os.getenv('YTDLP_JS_RUNTIME_PATH', '').strip()
        cmd += ['--js-runtimes', f'{runtime}:{runtime_path}' if runtime_path else runtime]
    cookies = os.getenv('YTDLP_COOKIES_FILE', '').strip()
    if cookies:
        cmd += ['--cookies', cookies]

    # Low CPU/IO priority keeps audio playback free of underruns
    if shutil.which('nice'):
        cmd = ['nice', '-n', '15'] + cmd
    return cmd + ['--', url]


class DownloadJob:
    """One yt-dlp run. Iterate `events()` from a greenlet; call `cancel()` from anywhere."""

    def __init__(self, url):
        self.url = url.strip()
        self.is_playlist = classify_url(self.url) == 'playlist'
        self.process = None
        self.cancelled = False

    def events(self):
        """Yield dict events: start, progress, done, error, finished."""
        if self.cancelled:  # cancelled before the job even started
            yield {'type': 'finished', 'returncode': None, 'cancelled': True, 'error': None}
            return
        os.makedirs(INCOMING_DIR, exist_ok=True)
        # stderr is merged into stdout: two separate pipes can deadlock when
        # yt-dlp fills the unread one with warnings. A new session lets us signal
        # the whole group, so ffmpeg children never outlive a cancelled job.
        self.process = subprocess.Popen(
            build_command(self.url, self.is_playlist),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1,
            start_new_session=True,
        )
        last_error = None
        missing_js_runtime = False
        watchdog = None
        try:
            for line in self.process.stdout:
                watchdog = self._rearm_watchdog(watchdog)
                if self.cancelled:
                    self._stop_process()
                line = line.rstrip('\n')
                if 'javascript runtime' in line.lower():
                    missing_js_runtime = True
                if line.startswith('ERROR:'):
                    logger.warning(f"yt-dlp: {line}")
                    last_error = friendly_error(line)
                    yield {'type': 'error', 'message': last_error}
                    continue
                event = self._parse_line(line)
                if event:
                    yield event
            self.process.wait()
        finally:
            if watchdog:
                watchdog.cancel()
            self._stop_process()
            self._cleanup_incoming()

        if last_error and missing_js_runtime:
            last_error = friendly_error('javascript runtime')
        yield {
            'type': 'finished',
            'returncode': self.process.returncode,
            'cancelled': self.cancelled,
            'error': last_error,
        }

    def cancel(self):
        self.cancelled = True
        self._signal_group(signal.SIGTERM)

    def _rearm_watchdog(self, watchdog):
        if watchdog:
            watchdog.cancel()
        watchdog = threading.Timer(STALL_TIMEOUT, self._on_stall)
        watchdog.daemon = True
        watchdog.start()
        return watchdog

    def _on_stall(self):
        logger.error(f"yt-dlp printed nothing for {STALL_TIMEOUT}s, killing it: {self.url}")
        self._signal_group(signal.SIGKILL)

    def _signal_group(self, sig):
        if self.process and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, sig)
            except ProcessLookupError:
                pass

    def _stop_process(self):
        """SIGTERM the process group, escalate to SIGKILL if it does not exit."""
        if not self.process or self.process.poll() is not None:
            return
        self._signal_group(signal.SIGTERM)
        try:
            self.process.wait(timeout=TERMINATE_GRACE)
        except subprocess.TimeoutExpired:
            self._signal_group(signal.SIGKILL)
            self.process.wait()

    @staticmethod
    def _parse_line(line):
        try:
            if line.startswith(START_MARK):
                return {'type': 'start', **json.loads(line[len(START_MARK):])}
            if line.startswith(DONE_MARK):
                return {'type': 'done', **json.loads(line[len(DONE_MARK):])}
            if line.startswith(PROGRESS_MARK):
                percent = float(line[len(PROGRESS_MARK):].strip().rstrip('%') or 0)
                return {'type': 'progress', 'percent': percent}
        except ValueError:
            logger.debug(f"Unparsable yt-dlp line: {line}")
        return None

    @staticmethod
    def _cleanup_incoming():
        shutil.rmtree(INCOMING_DIR, ignore_errors=True)


def get_ytdlp_version():
    try:
        return metadata.version('yt-dlp')
    except metadata.PackageNotFoundError:
        return 'Unknown'


def update_ytdlp():
    """Upgrade yt-dlp (with the EJS challenge solver) in the running interpreter's env."""
    cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp[default]']
    logger.info(f"Updating yt-dlp: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=UPDATE_TIMEOUT)
    if result.returncode != 0:
        logger.error(f"yt-dlp update failed: {result.stderr[-500:]}")
        raise RuntimeError('pip install failed')
    version = get_ytdlp_version()
    logger.info(f"yt-dlp is now {version}")
    return version
