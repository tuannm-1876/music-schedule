# Phase 5 — Kiểm thử + tài liệu

**Ưu tiên:** P1 · **Trạng thái:** todo

## Test (pytest, thêm `requirements-dev.txt`)
- `tests/test_classify_url.py` — bảng URL ở Phase 2.
- `tests/test_build_opts.py` — env sinh ra đúng `js_runtimes`, `cookiefile`, `noplaylist`.
- `tests/test_add_music_api.py` — trả 202 khi rảnh, 409 khi đang tải (chỉ stub `youtube_downloader.download_one` ở tầng API).
- Smoke test thật trên Pi (làm tay, ghi kết quả vào `plans/reports/`): 1 video, playlist 5 bài, link mix RD, hủy giữa bài, tải trong lúc đang phát.

## Tài liệu
- `README.md`: yêu cầu Python ≥3.10 (khuyên 3.11), JS runtime theo kiến trúc CPU, `yt-dlp[default]`, cookies, bảng lỗi thường gặp.
- `docs/project-changelog.md`, `docs/system-architecture.md` (tạo nếu chưa có): luồng tải nền.

## Done khi
- `pytest` xanh; smoke test trên Pi đạt 5/5.
