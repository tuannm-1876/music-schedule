# Phase 2 — Tách và sửa module tải YouTube

**Ưu tiên:** P0 · **Trạng thái:** todo

## File
- Tạo: `youtube_downloader.py` (~150 dòng), chứa toàn bộ logic yt-dlp.
- Sửa: `app.py` — xóa `update_ytdlp`, `get_ytdlp_version` (dòng 518–581) và `normalize_filename`, `is_playlist_url`, `download_single_track`, `download_playlist`, `download_music` (dòng 955–1218), thay bằng import từ module mới.
- Sửa: `requirements.txt`.

## Thiết kế
```python
def build_base_opts(progress_hook=None) -> dict:
    # format 'bestaudio[ext=m4a]/bestaudio/best'
    # js_runtimes lấy từ env, cookiefile nếu có
    # socket_timeout=30, retries=5, fragment_retries=5, extractor_retries=3
    # quiet=True, noprogress=True, noplaylist=True
    # FFmpegExtractAudio mp3 128k
    # progress_hooks=[progress_hook]; cachedir trong BASE_DIR để dùng lại kết quả giải player JS

def classify_url(url) -> 'single' | 'playlist'
    # urllib.parse: có v= thì là single (bỏ qua list=RD... là mix);
    # chỉ /playlist?list= (không phải RD*) mới là playlist

def download_one(url, hook) -> {'title', 'filename', 'duration'}
    # MỘT lần extract_info(url, download=True); title/duration lấy từ info
    # đường dẫn thật lấy từ info['requested_downloads'][0]['filepath']

def list_playlist(url) -> (title, entries)   # extract_flat='in_playlist'
def update_ytdlp() -> str                     # venv pip install -U "yt-dlp[default]", trả version mới
```

## Các bước
1. Viết `classify_url` + test bảng URL (watch, watch&list=PL, watch&list=RD, youtu.be, music.youtube.com/playlist, shorts).
2. Viết `build_base_opts`, đọc env qua `python-dotenv` (đã có trong requirements).
3. `download_one`: một lần extract, bỏ bước `extract_flat` trước đó. Kiểm tra trùng theo video `id` (tên file dạng `<normalized_title>_<id>.mp3`) thay vì chỉ theo tiêu đề.
4. Playlist: `list_playlist` rồi gọi `download_one` từng bài; bỏ lần `ydl_detail.extract_info` thứ hai.
5. `update_ytdlp`: chỉ dùng pip của venv, `timeout=300`; bỏ nhánh `sudo apt-get` và `--break-system-packages`. Vì reload module không có tác dụng, endpoint `/update-ytdlp` trả `restart_required: true`; restart service (`Restart=always` + thoát tiến trình) chỉ khi không có bài đang phát.
6. Map lỗi yt-dlp sang thông báo dễ hiểu: thiếu JS runtime, bị chặn bot (gợi ý cookies), video riêng tư/giới hạn tuổi.

## Done khi
- Trên Pi tải được: 1 video, 1 playlist 5 bài, 1 link `watch?v=..&list=RD..` (chỉ tải đúng 1 bài).
- Log mỗi bài chỉ có 1 lần extract.

## Rủi ro
- Đổi quy tắc tên file chỉ áp cho bài mới; bài cũ vẫn tìm qua `find_actual_file` như hiện tại.
