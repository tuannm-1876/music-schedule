# Phase 3 — Tải chạy nền, không chặn phát nhạc

**Ưu tiên:** P0 · **Trạng thái:** todo

## Vấn đề
`add_music()` (`app.py:1824`) chạy yt-dlp ngay trong request. yt-dlp tốn CPU (parse JSON/regex) ngay trong hub eventlet, nên `broadcast_playback_state`, fade và socket bị đứng; request playlist treo tới khi xong; gunicorn không nhận được heartbeat nên có thể kill worker giữa bài.

## Thiết kế
- Chạy các hàm của `youtube_downloader` trong **thread OS thật** qua `eventlet.tpool.execute(...)`, gọi từ một `socketio.start_background_task`, để hub được rảnh.
- Mỗi lúc chỉ 1 job (Pi 1GB RAM): nếu `download_state['active']` thì trả `409 {"message": "Đang có bài đang tải"}`.
- `POST /add-music` trả ngay `202 {"success": true, "queued": true}`; kết quả báo qua `download_progress` (frontend đã lắng nghe ở `SocketContext.tsx:135`) và `song_added`.
- Tải 1 bài cũng phát `download_progress` (hiện chỉ playlist có), dùng `progress_hooks` của yt-dlp, emit tối đa 1 lần/giây.
- Không gọi `socketio.emit` từ thread tpool; đẩy sự kiện qua `eventlet.queue` rồi emit ở greenlet.
- Hủy: progress hook kiểm tra `download_state['cancelled']` và raise `yt_dlp.utils.DownloadCancelled`, nên hủy được cả giữa bài chứ không chỉ giữa các bài. Dọn file `.part` sau khi hủy.
- Ghi DB trong greenlet với `app.app_context()`, không ghi trong tpool.

## File
- Sửa: `app.py` (`add_music`, các hàm download state).
- Sửa: `frontend/src/lib/api.ts` và component gọi `addFromYoutube`: xử lý 202/409, không chờ kết quả qua HTTP.

## Done khi
- Đang phát nhạc và tải playlist 10 bài: nhạc không giật, thanh tiến độ vẫn cập nhật, UI vẫn thao tác được.
- Hủy giữa bài thì dừng trong ≤3s, không để lại file `.part`.

## Rủi ro
- Hai tab bấm tải cùng lúc gây race: khóa bằng `eventlet.semaphore.Semaphore`.
