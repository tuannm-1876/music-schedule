---
title: Sửa lỗi tải YouTube + tối ưu cho Raspberry Pi 3B+
status: in-progress
created: 2026-09-30
---

# Sửa lỗi tải YouTube + chạy mượt trên Pi 3B+

## Nguyên nhân gốc (đã xác minh)
1. **Thiếu JS runtime** — từ bản 2025.11, yt-dlp cần Deno/Node/QuickJS + gói `yt-dlp-ejs` để giải challenge của YouTube. Pi không có runtime nào nên không lấy được format.
2. **Python quá cũ** — yt-dlp ≥2025.10.22 yêu cầu Python ≥3.10 (bản 2026.07 khuyến nghị 3.11). Pi OS Bullseye (3.9) thì `pip install -U` bị kẹt ở bản cũ, dù cron update vẫn báo "thành công".
3. **Deno không có bản armv7** — Pi OS 32-bit phải dùng Node ≥22 (armv7l) hoặc QuickJS-NG ≥0.12. Pi OS 64-bit dùng được Deno aarch64.
4. **Tải chạy đồng bộ trong request** (`app.py:1845`) — chặn hub eventlet: nhạc đang phát bị giật, gunicorn có thể kill worker, request playlist treo hàng chục phút.
5. **Extract 2 lần mỗi bài** (`app.py:979`, `app.py:1102`) — trên Pi mỗi lần giải JS tốn vài giây, thời gian bị nhân đôi.
6. **URL `watch?v=..&list=RD..`** bị coi là playlist (`app.py:965`), nên tải cả mix gần như vô hạn.
7. `update_ytdlp()` chỉ nâng `yt-dlp`, không nâng `yt-dlp-ejs`; `importlib.reload` không nạp lại submodule nên bản mới chưa có hiệu lực.

## Phases
| # | Phase | Ưu tiên | Trạng thái |
|---|-------|---------|------------|
| 0 | [Chốt code đang dở](phase-00-commit-pending-work.md) | P0 | done (b78d98e) |
| 1 | [Môi trường Pi: OS/Python/JS runtime](phase-01-pi-environment.md) | P0 | code done; cần làm trên Pi |
| 2 | [Sửa module tải YouTube](phase-02-youtube-downloader-module.md) | P0 | done |
| 3 | [Tải chạy nền, không chặn phát nhạc](phase-03-background-download-job.md) | P0 | done |
| 4 | [Tối ưu hiệu năng Pi 3B+](phase-04-pi-performance.md) | P1 | done (trừ journald/zram: cấu hình trên Pi) |
| 5 | [Kiểm thử + tài liệu](phase-05-tests-and-docs.md) | P1 | pytest xong; smoke test Pi còn chờ |

## Phụ thuộc
- 1 → 2 (cần runtime để kiểm thử thật); 2 → 3; phase 4 chạy song song với 3 (khác vùng code: player/broadcast).
- Không đổi schema DB. API giữ `POST /add-music` và event `download_progress`; chỉ đổi mã trả về sang 202/409 (frontend sửa theo trong phase 3).

## Thay đổi so với thiết kế ban đầu
- Phase 2/3: chạy yt-dlp bằng **tiến trình con** (`python -m yt_dlp`) thay cho gọi in-process + `eventlet.tpool`. Lý do: không đụng monkey-patch, hủy bằng kill, RAM được trả lại sau mỗi job, update yt-dlp có hiệu lực ngay (khỏi restart, khỏi `importlib.reload`).
- Tên file mới: `<title>_<videoId>.mp3` (`--restrict-filenames`); file tạm nằm ở `music/.incoming/`.

## Nguồn
- https://github.com/yt-dlp/yt-dlp/wiki/EJS
- https://newreleases.io/project/pypi/yt-dlp/release/2025.10.22
