# Phase 4 — Tối ưu hiệu năng Pi 3B+

**Ưu tiên:** P1 · **Trạng thái:** todo (song song Phase 3)

| # | Vấn đề | Vị trí | Sửa |
|---|---|---|---|
| 1 | Broadcast mỗi 0.5s, lần nào cũng query DB lấy title | `app.py:173`, `app.py:316` | Cache title khi `play_music`; interval 1s; không emit khi không phát và state không đổi |
| 2 | Job APScheduler + `start_background_task` tạo mới mỗi 0.5s | `app.py:337` | Một greenlet chạy vòng lặp `socketio.sleep(1)` thay cho job interval |
| 3 | ffmpeg mp3 192k chiếm hết 4 nhân, tranh CPU với audio | opts ở Phase 2 | 128k (đủ cho loa phát thanh); ffmpeg `-threads 1`, chạy với `nice` |
| 4 | Buffer pygame 4096 vẫn underrun khi CPU cao | `app.py:109` | Giữ 4096, thêm `Nice=-5` cho service; ffmpeg chạy nice thấp hơn |
| 5 | Cron update yt-dlp lúc 1:00 bằng pip (nặng, có thể trùng lịch phát) | `app.py:174` | Dời sang 3:00 và bỏ qua nếu đang phát hoặc đang tải |
| 6 | Log INFO toàn bộ `download_state` mỗi lần cập nhật, ghi thẻ SD liên tục | `app.py:132` | Hạ xuống DEBUG; giới hạn journald `SystemMaxUse=50M` |
| 7 | SQLite trên thẻ SD | config | `PRAGMA journal_mode=WAL` khi khởi động |

## Service (`music-scheduler-venv.service`)
```
Environment=PATH=/home/<user>/.deno/bin:/home/<user>/schedule-music/venv/bin:/usr/bin:/bin
ExecStart=... gunicorn --worker-class eventlet -w 1 --timeout 120 --bind 0.0.0.0:5000 wsgi:application
Nice=-5
MemoryHigh=600M
```
Đồng bộ luôn `music-scheduler.service` (bản cũ user `pi`) hoặc xóa nếu không dùng nữa.

## Done khi
- `top` khi phát nhạc bình thường: CPU gunicorn < 5%.
- Trong lúc tải: journal không có "ALSA underrun".
